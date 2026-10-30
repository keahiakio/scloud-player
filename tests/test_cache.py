# SPDX-License-Identifier: MIT OR Apache-2.0
import os
import time
from unittest.mock import MagicMock, patch
import pytest

from scloud_player.cache import SongCacheManager, resolve_stream_url


def test_cache_store_and_retrieve(tmp_path):
    with patch("scloud_player.cache.CACHE_DIR", str(tmp_path)), \
         patch("scloud_player.cache.DISK_CACHE_FILE", str(tmp_path / "stream_cache.json")):

        mgr = SongCacheManager(cache_size=40)
        track = {"id": "12345", "title": "Test Song", "webpage_url": "https://soundcloud.com/test/song"}

        assert not mgr.has_stream_url(track)
        assert mgr.get_stream_url(track, fallback_resolve=False) is None

        # Store stream URL
        mgr.store_stream_url("12345", "https://stream.soundcloud.com/media/test.mp3", track)

        assert mgr.has_stream_url(track)
        assert mgr.get_stream_url(track, fallback_resolve=False) == "https://stream.soundcloud.com/media/test.mp3"


@patch("subprocess.run")
def test_resolve_stream_url_success(mock_run):
    mock_run.return_value = MagicMock(stdout="https://cf-media.sndcdn.com/test.mp3\nhttps://cf-media2.sndcdn.com/other.mp3\n")
    url = resolve_stream_url("https://soundcloud.com/test/track")
    assert url == "https://cf-media.sndcdn.com/test.mp3"


def test_preload_tracks_triggers_workers(tmp_path):
    with patch("scloud_player.cache.CACHE_DIR", str(tmp_path)), \
         patch("scloud_player.cache.DISK_CACHE_FILE", str(tmp_path / "stream_cache.json")), \
         patch("scloud_player.cache.resolve_stream_url") as mock_resolve:

        mock_resolve.return_value = "https://stream.sndcdn.com/audio.mp3"

        mgr = SongCacheManager(cache_size=40)
        tracks = [
            {"id": f"t_{i}", "title": f"Song {i}", "webpage_url": f"https://soundcloud.com/test/song{i}"}
            for i in range(5)
        ]

        mgr.preload_tracks(tracks)
        # Give threads a fraction of a second to run
        time.sleep(0.3)

        assert mgr.has_stream_url(tracks[0])
        assert mgr.cached_count(tracks) > 0


def test_cache_clear(tmp_path):
    with patch("scloud_player.cache.CACHE_DIR", str(tmp_path)), \
         patch("scloud_player.cache.DISK_CACHE_FILE", str(tmp_path / "stream_cache.json")):

        mgr = SongCacheManager(cache_size=40)
        mgr.store_stream_url("123", "https://example.com/stream.mp3", {})
        assert mgr.has_stream_url({"id": "123"})

        mgr.clear()
        assert not mgr.has_stream_url({"id": "123"})


def test_extract_url_expiry():
    from scloud_player.cache import extract_url_expiry
    import json
    import base64

    # None / empty
    assert extract_url_expiry("") is None
    assert extract_url_expiry("https://example.com/stream.mp3") is None

    # Canned policy with Expires
    canned_url = "https://example.com/stream.mp3?Expires=1800000000&Signature=abc"
    assert extract_url_expiry(canned_url) == 1800000000.0

    # Custom policy with base64 Statement
    policy_json = json.dumps({"Statement": [{"Resource": "*", "Condition": {"DateLessThan": {"AWS:EpochTime": 1800000500}}}]})
    policy_b64 = base64.b64encode(policy_json.encode()).decode().replace('+', '-').replace('=', '_').replace('/', '~')
    custom_url = f"https://playback.media-streaming.soundcloud.cloud/test/playlist.m3u8?Policy={policy_b64}"
    assert extract_url_expiry(custom_url) == 1800000500.0


def test_cache_expiration(tmp_path):
    from scloud_player.cache import EXPIRY_BUFFER_SECONDS
    with patch("scloud_player.cache.CACHE_DIR", str(tmp_path)), \
         patch("scloud_player.cache.DISK_CACHE_FILE", str(tmp_path / "stream_cache.json")):

        mgr = SongCacheManager(cache_size=40)
        track = {"id": "song_exp", "title": "Exp Song", "webpage_url": "https://soundcloud.com/test/song"}

        # Store with custom epoch expiry in the future
        future_epoch = time.time() + 100
        mgr.store_stream_url("song_exp", f"https://example.com/audio.mp3?Expires={future_epoch}", track)
        assert mgr.has_stream_url(track)

        # But if expiry is within buffer window (e.g. now + 10s < buffer of 30s)
        near_expiry = time.time() + (EXPIRY_BUFFER_SECONDS - 5)
        mgr.store_stream_url("song_exp", f"https://example.com/audio.mp3?Expires={near_expiry}", track)
        assert not mgr.has_stream_url(track)
        # Entry should have been removed
        assert mgr.get_stream_url(track, fallback_resolve=False) is None


def test_cache_invalidation(tmp_path):
    with patch("scloud_player.cache.CACHE_DIR", str(tmp_path)), \
         patch("scloud_player.cache.DISK_CACHE_FILE", str(tmp_path / "stream_cache.json")):

        mgr = SongCacheManager(cache_size=40)
        track = {"id": "song_inv", "title": "Inv Song", "webpage_url": "https://soundcloud.com/test/song"}

        mgr.store_stream_url("song_inv", "https://example.com/stream.mp3", track)
        assert mgr.has_stream_url(track)

        mgr.invalidate(track)
        assert not mgr.has_stream_url(track)
        assert mgr.get_stream_url(track, fallback_resolve=False) is None


def test_disk_cache_prunes_expired(tmp_path):
    import json
    cache_file = tmp_path / "stream_cache.json"
    now = time.time()
    # Write one expired and one valid entry
    data = {
        "expired_song": {
            "stream_url": "https://example.com/old.mp3",
            "cached_at": now - 1000,
            "expires_at": now - 500,
        },
        "valid_song": {
            "stream_url": "https://example.com/valid.mp3",
            "cached_at": now,
            "expires_at": now + 500,
        }
    }
    with open(cache_file, "w") as f:
        json.dump(data, f)

    with patch("scloud_player.cache.CACHE_DIR", str(tmp_path)), \
         patch("scloud_player.cache.DISK_CACHE_FILE", str(cache_file)):

        mgr = SongCacheManager(cache_size=40)
        assert not mgr.has_stream_url({"id": "expired_song"})
        assert mgr.has_stream_url({"id": "valid_song"})
