# SPDX-License-Identifier: MIT OR Apache-2.0
import asyncio
from unittest.mock import MagicMock, patch
import pytest

from scloud_player.tui import ScloudPlayerApp


@patch("scloud_player.player.subprocess.Popen")
@patch("scloud_player.visualizer.subprocess.Popen")
def test_tui_app_init(mock_vis_popen, mock_player_popen):
    with patch("scloud_player.tui.load_config", return_value={"volume": 80, "visualizer": "cava", "autoplay": False, "shuffle": False, "repeat": "off"}):
        app = ScloudPlayerApp(initial_url="https://soundcloud.com/test")
        assert app.current_url == "https://soundcloud.com/test"
        assert app.page_size == 40
        assert app.cache_manager.cache_size == 40


def test_tui_app_lifecycle():
    async def _async_run():
        with patch("scloud_player.player.subprocess.Popen"), \
             patch("scloud_player.visualizer.subprocess.Popen"), \
             patch("scloud_player.tui.load_config", return_value={"volume": 80, "visualizer": "cava", "autoplay": False, "shuffle": False, "repeat": "off"}), \
             patch("scloud_player.tui.fetch_track_page") as mock_fetch:

            mock_fetch.return_value = MagicMock(
                tracks=[
                    {"id": "1", "title": "Track 1", "uploader": "Artist", "duration": 150},
                    {"id": "2", "title": "Track 2", "uploader": "Artist", "duration": 200},
                ],
                page=1,
                page_size=40,
                has_next=False,
                playlist_title="Test",
                total_tracks=2
            )
            app = ScloudPlayerApp(initial_url="https://soundcloud.com/test")
            app.autoplay = False
            app.shuffle = False

            async with app.run_test() as pilot:
                assert app.current_url == "https://soundcloud.com/test"
                app._on_ui_tick()
                app.action_toggle_autoplay()
                assert app.autoplay is True
                app.action_toggle_shuffle()
                assert app.shuffle is True
                app.action_cycle_repeat()
                assert app.repeat_mode == "one"
                app.action_cycle_visualizer()
                assert app.vis_mode in ("spectrum", "off", "cava")

                # Test next/prev track actions
                with patch.object(app, "_play_track_at_index") as mock_play:
                    app.action_next_track()
                    mock_play.assert_called_with(1)
                    app.action_prev_track()
                    mock_play.assert_called_with(0)

    asyncio.run(_async_run())
