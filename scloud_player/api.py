# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2026 Kiwi Akio

"""
SoundCloud API and metadata resolution module.
Provides paginated track fetching (max 30 songs at a time) using yt-dlp
and fast batch metadata enrichment via SoundCloud API v2.
"""

import json
import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from typing import Dict, List, Optional


def find_yt_dlp() -> str:
    """Finds yt-dlp binary, checking virtual environment and PATH."""
    venv_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "venv", "bin", "yt-dlp")
    if os.path.isfile(venv_path) and os.access(venv_path, os.X_OK):
        return venv_path
    path = shutil.which("yt-dlp")
    if path:
        return path
    for candidate in [
        "/home/keahiakio/scloud-player/venv/bin/yt-dlp",
        os.path.expanduser("~/.local/bin/yt-dlp"),
        "/usr/local/bin/yt-dlp",
        "/usr/bin/yt-dlp",
    ]:
        if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
            return candidate
    return "yt-dlp"


def format_duration(seconds) -> str:
    """Formats duration in seconds to MM:SS or HH:MM:SS."""
    if seconds is None:
        return "N/A"
    try:
        seconds = int(seconds)
    except (ValueError, TypeError):
        return "N/A"
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    seconds = seconds % 60
    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    return f"{minutes:02d}:{seconds:02d}"


_SOUNDCLOUD_IE = None


def _get_soundcloud_ie():
    """Lazily initializes and returns a SoundcloudIE instance with a valid client_id."""
    global _SOUNDCLOUD_IE
    if _SOUNDCLOUD_IE is None:
        import yt_dlp
        from yt_dlp.extractor.soundcloud import SoundcloudIE

        ydl = yt_dlp.YoutubeDL({"quiet": True, "no_warnings": True})
        ie = SoundcloudIE(ydl)
        ie._initialize_pre_login()
        _SOUNDCLOUD_IE = ie
    return _SOUNDCLOUD_IE


def enrich_tracks_metadata(tracks_slice: List[dict]) -> List[dict]:
    """
    Populates missing 'title', 'uploader', 'duration', and 'webpage_url' fields
    in-place for a slice of tracks using SoundCloud's API v2 batch endpoint.
    """
    if not tracks_slice:
        return tracks_slice

    missing_by_id = {}
    for track in tracks_slice:
        needs_enrichment = (
            not track.get("title")
            or track.get("title") == "N/A"
            or not track.get("uploader")
            or track.get("uploader") == "N/A"
            or track.get("duration") is None
        )
        if not needs_enrichment:
            continue

        track_id = str(track.get("id") or "")
        if not track_id.isdigit():
            m = re.search(r"/tracks/(\d+)", str(track.get("url") or track.get("webpage_url") or ""))
            if m:
                track_id = m.group(1)
        if track_id.isdigit():
            missing_by_id.setdefault(track_id, []).append(track)

    if not missing_by_id:
        return tracks_slice

    try:
        import sys
        main_mod = sys.modules.get("main")
        get_ie_fn = getattr(main_mod, "_get_soundcloud_ie", _get_soundcloud_ie)
        ie = get_ie_fn()
        all_ids = list(missing_by_id.keys())
        # SoundCloud API v2 /tracks endpoint accepts up to 50 IDs per batch request
        for idx in range(0, len(all_ids), 50):
            chunk_ids = all_ids[idx : idx + 50]
            api_tracks = ie._call_api(
                f"{ie._API_V2_BASE}tracks",
                "batch",
                query={"ids": ",".join(chunk_ids)},
                headers=ie._HEADERS,
                note=False,
                fatal=False,
            )
            if not isinstance(api_tracks, list):
                continue

            for item in api_tracks:
                if not isinstance(item, dict):
                    continue
                tid = str(item.get("id") or "")
                if tid not in missing_by_id:
                    continue

                user = item.get("user") or {}
                pub_meta = item.get("publisher_metadata") or {}
                title = item.get("title")
                uploader = user.get("username") or pub_meta.get("artist")
                duration_ms = item.get("duration")
                duration = (
                    duration_ms / 1000.0
                    if isinstance(duration_ms, (int, float))
                    else None
                )
                permalink_url = item.get("permalink_url")

                for target in missing_by_id[tid]:
                    if title and (not target.get("title") or target.get("title") == "N/A"):
                        target["title"] = title
                    if uploader and (not target.get("uploader") or target.get("uploader") == "N/A"):
                        target["uploader"] = uploader
                    if duration is not None and target.get("duration") is None:
                        target["duration"] = duration
                    if permalink_url:
                        target["webpage_url"] = permalink_url
    except Exception:
        # Fail gracefully so table rendering still works even if enrichment fails
        pass

    return tracks_slice


@dataclass
class TrackPage:
    tracks: List[dict]
    page: int
    page_size: int
    has_next: bool
    playlist_title: str = ""
    total_tracks: Optional[int] = None


def get_track_data(
    url: str,
    page: int = 1,
    page_size: int = 40,
    yt_dlp_path: Optional[str] = None
) -> Optional[List[dict]]:
    """
    Fetches up to `page_size` (max 40) tracks from a SoundCloud URL using yt-dlp.
    Uses --playlist-items for fast paginated retrieval without loading the full playlist at once.
    """
    if not yt_dlp_path:
        yt_dlp_path = find_yt_dlp()

    start_idx = (page - 1) * page_size + 1
    end_idx = page * page_size

    try:
        command = [
            yt_dlp_path,
            "--flat-playlist",
            "-j",
            "--no-update",
            "--playlist-items",
            f"{start_idx}:{end_idx}",
            url,
        ]
        result = subprocess.run(command, capture_output=True, text=True, check=True)

        tracks = []
        for line in result.stdout.strip().split("\n"):
            if line.strip():
                try:
                    track_info = json.loads(line)
                    tracks.append(track_info)
                except json.JSONDecodeError:
                    continue

        if tracks:
            enrich_tracks_metadata(tracks)
        return tracks
    except subprocess.CalledProcessError as e:
        return None
    except FileNotFoundError:
        return None


def fetch_track_page(
    url: str,
    page: int = 1,
    page_size: int = 40,
    yt_dlp_path: Optional[str] = None
) -> TrackPage:
    """
    Fetches a page of tracks and returns a structured TrackPage result.
    """
    tracks = get_track_data(url, page=page, page_size=page_size, yt_dlp_path=yt_dlp_path) or []
    playlist_title = ""
    total_count = None
    if tracks:
        playlist_title = tracks[0].get("playlist_title") or tracks[0].get("playlist") or ""
        total_count = tracks[0].get("playlist_count") or tracks[0].get("n_entries")

    has_next = len(tracks) >= page_size
    return TrackPage(
        tracks=tracks,
        page=page,
        page_size=page_size,
        has_next=has_next,
        playlist_title=playlist_title,
        total_tracks=total_count
    )


def get_full_track_info(track_url: str, yt_dlp_path: Optional[str] = None) -> Optional[dict]:
    """Fetches full metadata for a single track using yt-dlp."""
    if not yt_dlp_path:
        yt_dlp_path = find_yt_dlp()

    try:
        command = [yt_dlp_path, "-j", "--no-update", track_url]
        result = subprocess.run(command, capture_output=True, text=True, check=True)
        return json.loads(result.stdout.strip())
    except Exception:
        return None


def get_stream_url(track_url: str, yt_dlp_path: Optional[str] = None) -> Optional[str]:
    """Gets the direct stream URL for a track using yt-dlp."""
    from scloud_player.cache import resolve_stream_url
    if not yt_dlp_path:
        yt_dlp_path = find_yt_dlp()
    return resolve_stream_url(track_url, yt_dlp_path)
