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
