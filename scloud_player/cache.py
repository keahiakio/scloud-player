# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2026 Kiwi Akio

"""
In-memory and disk stream URL & metadata cache manager.
Preloads and caches up to 30 songs concurrently in the background so
transitions between tracks are instantaneous with zero delay.
"""

import base64
import json
import os
import subprocess
import threading
import time
import urllib.parse
from concurrent.futures import ThreadPoolExecutor
from typing import Callable, Dict, List, Optional
from scloud_player.config import CACHE_DIR

DISK_CACHE_FILE = os.path.join(CACHE_DIR, "stream_cache.json")
# SoundCloud streaming links expire in ~5-6 minutes (300-360 seconds).
# We use a conservative default TTL of 4 minutes (240s) and a safety buffer of 30 seconds
# before signed URL expiration to prevent mid-request 403s.
STREAM_TTL_SECONDS = 240
EXPIRY_BUFFER_SECONDS = 30


def extract_url_expiry(stream_url: str) -> Optional[float]:
    """
    Extracts the epoch expiration timestamp from a signed stream URL if available
    (e.g., CloudFront signed URLs with Policy or Expires parameters).
    """
    if not stream_url:
        return None
    try:
        parsed = urllib.parse.urlparse(stream_url)
        params = urllib.parse.parse_qs(parsed.query)

        # Check canned policy 'Expires' / 'expires' query parameter
        for key in ("Expires", "expires"):
            if key in params:
                val = float(params[key][0])
                if val > 1.5e9:
                    return val

        # Check CloudFront custom 'Policy'
        if "Policy" in params:
            policy_b64 = params["Policy"][0]
            # AWS CloudFront URL-safe base64: '-' -> '+', '_' -> '=', '~' -> '/'
            std_b64 = policy_b64.replace("-", "+").replace("_", "=").replace("~", "/")
            padding = len(std_b64) % 4
            if padding:
                std_b64 += "=" * (4 - padding)
            decoded = base64.b64decode(std_b64).decode("utf-8", errors="ignore")
            data = json.loads(decoded)
            for stmt in data.get("Statement", []):
                epoch = stmt.get("Condition", {}).get("DateLessThan", {}).get("AWS:EpochTime")
                if epoch and float(epoch) > 1.5e9:
                    return float(epoch)
    except Exception:
        pass
    return None


def resolve_stream_url(track_url: str, yt_dlp_path: Optional[str] = None) -> Optional[str]:
    """
    Directly resolves a SoundCloud track URL into an audio stream URL using yt-dlp.
    """
    if not yt_dlp_path:
        yt_dlp_path = "yt-dlp"

    try:
        cmd = [yt_dlp_path, "-g", "--no-update", track_url]
        res = subprocess.run(cmd, capture_output=True, text=True, check=True)
        out = res.stdout.strip()
        if out:
            # yt-dlp might return multiple stream URLs separated by newline; the first audio stream is best
            return out.split("\n")[0].strip()
    except Exception:
        pass
    return None


class SongCacheManager:
    """
    Manages in-memory and persistent caching of stream URLs and metadata for tracks.
    Runs asynchronous pre-fetching for batches of up to 40 songs.
    """

    def __init__(self, cache_size: int = 40, yt_dlp_path: Optional[str] = None):
        self.cache_size = cache_size
        self.yt_dlp_path = yt_dlp_path or "yt-dlp"
        self._lock = threading.Lock()
        self._memory_cache: Dict[str, dict] = {}
        self._executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="ScloudPreloader")
        self._active_tasks: Dict[str, bool] = {}
        self._on_cached_callback: Optional[Callable[[str, str], None]] = None

        self._load_disk_cache()

    def set_on_cached_callback(self, callback: Callable[[str, str], None]):
        """Sets a callback function called when a track stream URL is cached."""
        self._on_cached_callback = callback

    def _get_key(self, track: dict) -> str:
        """Determines cache key for a track (prefers track ID, then permalink/url)."""
        if track.get("id"):
            return str(track["id"])
        return track.get("webpage_url") or track.get("url") or ""

    def _is_entry_valid(self, entry: Optional[dict], now: Optional[float] = None) -> bool:
        """Determines whether a cache entry contains an active, unexpired stream URL."""
        if not entry or not entry.get("stream_url"):
            return False
        if now is None:
            now = time.time()

        expires_at = entry.get("expires_at")
        if expires_at is not None:
            return (expires_at - now) > EXPIRY_BUFFER_SECONDS

        cached_at = entry.get("cached_at", 0)
        return (now - cached_at) < STREAM_TTL_SECONDS

    def _load_disk_cache(self):
        """Loads cached stream URLs from disk, pruning expired entries."""
        if not os.path.exists(DISK_CACHE_FILE):
            return
        try:
            with open(DISK_CACHE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            now = time.time()
            with self._lock:
                for k, v in data.items():
                    if isinstance(v, dict) and self._is_entry_valid(v, now):
                        self._memory_cache[k] = v
        except Exception:
            pass

    def _save_disk_cache(self):
        """Persists valid in-memory cache entries to disk."""
        try:
            os.makedirs(CACHE_DIR, exist_ok=True)
            now = time.time()
            with self._lock:
                valid = {
                    k: v for k, v in self._memory_cache.items()
                    if self._is_entry_valid(v, now)
                }
            with open(DISK_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(valid, f)
        except Exception:
            pass

    def has_stream_url(self, track: dict) -> bool:
        """Checks if a track's stream URL is pre-cached in memory and still valid."""
        key = self._get_key(track)
        if not key:
            return False
        with self._lock:
            entry = self._memory_cache.get(key)
            if entry and self._is_entry_valid(entry):
                return True
            if entry:
                self._memory_cache.pop(key, None)
        return False

    def get_stream_url(self, track: dict, fallback_resolve: bool = True) -> Optional[str]:
        """
        Retrieves the stream URL from cache. If missing or expired and fallback_resolve is True,
        resolves it synchronously and stores it in cache.
        """
        key = self._get_key(track)
        if not key:
            return None

        with self._lock:
            entry = self._memory_cache.get(key)
            if entry and self._is_entry_valid(entry):
                return entry.get("stream_url")
            if entry:
                self._memory_cache.pop(key, None)

        if not fallback_resolve:
            return None

        # Resolve synchronously on demand
        target_url = track.get("webpage_url") or track.get("url")
        if not target_url:
            return None

        stream_url = resolve_stream_url(target_url, self.yt_dlp_path)
        if stream_url:
            self.store_stream_url(key, stream_url, track)
        return stream_url

    def store_stream_url(self, key: str, stream_url: str, metadata: Optional[dict] = None):
        """Stores a resolved stream URL into memory and persistent cache."""
        now = time.time()
        url_expiry = extract_url_expiry(stream_url)
        expires_at = url_expiry if url_expiry else (now + STREAM_TTL_SECONDS)

        with self._lock:
            # Enforce max memory cache size (prune oldest if needed)
            if len(self._memory_cache) >= self.cache_size * 2:
                oldest_key = min(self._memory_cache.keys(), key=lambda k: self._memory_cache[k].get("cached_at", 0))
                self._memory_cache.pop(oldest_key, None)

            self._memory_cache[key] = {
                "stream_url": stream_url,
                "cached_at": now,
                "expires_at": expires_at,
                "metadata": metadata or {}
            }

        self._save_disk_cache()
        if self._on_cached_callback:
            try:
                self._on_cached_callback(key, stream_url)
            except Exception:
                pass

    def invalidate(self, track_or_key):
        """Invalidates and removes a track's cached stream URL from memory and disk."""
        if isinstance(track_or_key, dict):
            key = self._get_key(track_or_key)
        else:
            key = str(track_or_key)
        if not key:
            return
        with self._lock:
            self._memory_cache.pop(key, None)
        self._save_disk_cache()

    def preload_tracks(self, tracks: List[dict], priority_index: int = 0, preload_ahead: Optional[int] = 5):
        """
        Preloads upcoming songs into memory in the background.
        Prioritizes the track at `priority_index` and subsequent upcoming tracks.
        """
        if not tracks:
            return

        total = len(tracks)
        if preload_ahead is not None:
            limit = min(preload_ahead, total, self.cache_size)
            indices = [(priority_index + i) % total for i in range(limit)]
            ordered = [tracks[i] for i in indices]
        else:
            batch = tracks[:self.cache_size]
            ordered = batch[priority_index:] + batch[:priority_index]

        for track in ordered:
            key = self._get_key(track)
            if not key or self.has_stream_url(track):
                continue

            with self._lock:
                if self._active_tasks.get(key):
                    continue
                self._active_tasks[key] = True

            target_url = track.get("webpage_url") or track.get("url")
            if target_url:
                self._executor.submit(self._worker_resolve, key, target_url, track)

    def _worker_resolve(self, key: str, target_url: str, track: dict):
        """Worker task executed in thread pool."""
        try:
            stream_url = resolve_stream_url(target_url, self.yt_dlp_path)
            if stream_url:
                self.store_stream_url(key, stream_url, track)
        finally:
            with self._lock:
                self._active_tasks.pop(key, None)

    def cached_count(self, tracks: List[dict]) -> int:
        """Returns the number of tracks currently pre-cached in the given list."""
        return sum(1 for t in tracks if self.has_stream_url(t))

    def clear(self):
        """Clears memory and disk cache."""
        with self._lock:
            self._memory_cache.clear()
        if os.path.exists(DISK_CACHE_FILE):
            try:
                os.remove(DISK_CACHE_FILE)
            except Exception:
                pass
