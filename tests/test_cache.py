# SPDX-License-Identifier: MIT OR Apache-2.0
import os
import time
from unittest.mock import MagicMock, patch
import pytest

from scloud_player.cache import SongCacheManager, resolve_stream_url


def test_cache_store_and_retrieve(tmp_path):
    with patch("scloud_player.cache.CACHE_DIR", str(tmp_path)), \
         patch("scloud_player.cache.DISK_CACHE_FILE", str(tmp_path / "stream_cache.json")):

        mgr = SongCacheManager(cache_size=30)
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

        mgr = SongCacheManager(cache_size=30)
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

        mgr = SongCacheManager(cache_size=30)
        mgr.store_stream_url("123", "https://example.com/stream.mp3", {})
        assert mgr.has_stream_url({"id": "123"})

        mgr.clear()
        assert not mgr.has_stream_url({"id": "123"})
