# SPDX-License-Identifier: MIT OR Apache-2.0
import json
from unittest.mock import MagicMock, patch
import pytest

from scloud_player.api import fetch_track_page, format_duration, get_track_data


def test_format_duration_edge_cases():
    assert format_duration(None) == "N/A"
    assert format_duration("invalid") == "N/A"
    assert format_duration(0) == "00:00"
    assert format_duration(59) == "00:59"
    assert format_duration(60) == "01:00"
    assert format_duration(3600) == "01:00:00"


@patch("subprocess.run")
def test_paginated_track_data(mock_run):
    # Mock yt-dlp returning 3 tracks for page 1
    mock_out = (
        '{"id": "1", "title": "Track 1", "uploader": "Artist 1", "duration": 120}\n'
        '{"id": "2", "title": "Track 2", "uploader": "Artist 2", "duration": 180}\n'
    )
    mock_run.return_value = MagicMock(stdout=mock_out)

    tracks = get_track_data("https://soundcloud.com/test", page=2, page_size=40)
    assert tracks is not None
    assert len(tracks) == 2

    # Check playlist-items parameter in yt-dlp command line
    cmd = mock_run.call_args[0][0]
    # Page 2 with size 40 means items 41:80
    assert "41:80" in cmd
