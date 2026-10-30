import pytest
import os
import json
from unittest.mock import patch, MagicMock
from main import format_duration, load_config, DEFAULT_CONFIG

def test_format_duration():
    # Test MM:SS
    assert format_duration(65) == "01:05"
    # Test HH:MM:SS
    assert format_duration(3665) == "01:01:05"
    # Test None/N/A
    assert format_duration(None) == "N/A"
    # Test zero
    assert format_duration(0) == "00:00"

def test_load_config_defaults(tmp_path):
    # Test that it returns defaults when file doesn't exist
    with patch("main.CONFIG_FILE", str(tmp_path / "nonexistent.json")):
        config = load_config()
        assert config == DEFAULT_CONFIG

def test_load_config_existing(tmp_path):
    # Test that it loads existing config correctly
    custom_config = {"player": "vlc", "autoplay": True}
    config_file = tmp_path / "config.json"
    config_file.write_text(json.dumps(custom_config))
    
    with patch("main.CONFIG_FILE", str(config_file)):
        config = load_config()
        assert config["player"] == "vlc"
        assert config["autoplay"] == True
        # Verify defaults for missing keys
        assert config["shuffle"] == DEFAULT_CONFIG["shuffle"]

@patch("subprocess.run")
def test_get_track_data_command(mock_run):
    # Verify that get_track_data calls yt-dlp with the right args
    from main import get_track_data
    
    mock_run.return_value = MagicMock(stdout='{"title": "Track 1", "url": "url1"}\n', check=True)
    
    url = "https://soundcloud.com/test"
    get_track_data(url)
    
    # Check that it called subprocess.run with yt-dlp and the url
    args, kwargs = mock_run.call_args
    command = args[0]
    assert "yt-dlp" in command[0]
    assert "--flat-playlist" in command
    assert url in command

@patch("main._get_soundcloud_ie")
def test_enrich_tracks_metadata(mock_get_ie):
    from main import enrich_tracks_metadata

    mock_ie = MagicMock()
    mock_ie._API_V2_BASE = "https://api-v2.soundcloud.com/"
    mock_ie._HEADERS = {}
    mock_ie._call_api.return_value = [
        {
            "id": 2193979815,
            "title": "Return To You",
            "user": {"username": "fubuki"},
            "duration": 137488,
            "permalink_url": "https://soundcloud.com/holoshirakami/return-to-you",
        },
        {
            "id": 2419427934,
            "title": "Korekara",
            "user": {},
            "publisher_metadata": {"artist": "xaev"},
            "duration": 173314,
            "permalink_url": "https://soundcloud.com/xaev/korekara",
        },
    ]
    mock_get_ie.return_value = mock_ie

    tracks = [
        {"id": "2193979815", "title": "Return To You", "url": "https://soundcloud.com/holoshirakami/return-to-you"},
        {"id": "2419427934", "url": "https://api-v2.soundcloud.com/tracks/2419427934"},
    ]

    enrich_tracks_metadata(tracks)

    assert tracks[0]["uploader"] == "fubuki"
    assert tracks[0]["duration"] == 137.488
    assert tracks[1]["title"] == "Korekara"
    assert tracks[1]["uploader"] == "xaev"
    assert tracks[1]["duration"] == 173.314
    assert tracks[1]["webpage_url"] == "https://soundcloud.com/xaev/korekara"

    # Calling a second time on already-enriched tracks should not trigger another API call
    mock_ie._call_api.reset_mock()
    enrich_tracks_metadata(tracks)
    mock_ie._call_api.assert_not_called()

def test_get_visualizer_args():
    from main import get_visualizer_args
    
    # Spectrum mode
    args = get_visualizer_args("spectrum", "Song Title", "Artist Name", fullscreen=True)
    assert any("--lavfi-complex=" in a for a in args)
    assert "--fs" in args
    assert any("Song Title" in a for a in args)
    assert any("Artist Name" in a for a in args)

    # Off mode
    assert get_visualizer_args("off", "Title", "Artist") == []

    # Caca mode
    caca_args = get_visualizer_args("caca", "Title", "Artist")
    assert "--vo=caca" in caca_args


@patch("subprocess.run")
def test_play_track_retry_on_expired_cache(mock_run):
    from scloud_player.cli import play_track
    from scloud_player.cache import SongCacheManager

    mock_cache = MagicMock(spec=SongCacheManager)
    # First get_stream_url returns expired url
    mock_cache.get_stream_url.side_effect = ["https://example.com/expired.m3u8", "https://example.com/fresh.m3u8"]

    # First mpv run fails with returncode 1, second mpv run succeeds with returncode 0
    mock_run.side_effect = [
        MagicMock(returncode=1),
        MagicMock(returncode=0),
    ]

    track_info = {
        "id": "123",
        "title": "Test Song",
        "uploader": "Artist",
        "duration": 180,
        "webpage_url": "https://soundcloud.com/artist/test-song",
    }

    result = play_track(track_info, player="mpv", config={"visualizer": "off", "fullscreen": False}, cache_mgr=mock_cache)
    assert result == 0
    mock_cache.invalidate.assert_called_once_with(track_info)
    assert mock_run.call_count == 2

