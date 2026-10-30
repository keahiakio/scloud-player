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

                # Test credits modal action
                app.action_show_credits()

    asyncio.run(_async_run())


def test_tui_responsive_resizing_and_breakpoints():
    async def _async_run():
        with patch("scloud_player.player.subprocess.Popen"), \
             patch("scloud_player.visualizer.subprocess.Popen"), \
             patch("scloud_player.tui.load_config", return_value={"volume": 80, "visualizer": "cava"}), \
             patch("scloud_player.tui.fetch_track_page") as mock_fetch:

            mock_fetch.return_value = MagicMock(
                tracks=[{"id": "1", "title": "Track 1", "uploader": "Artist", "duration": 150}],
                page=1,
                page_size=40,
                has_next=False,
                playlist_title="Test",
                total_tracks=1
            )
            app = ScloudPlayerApp()

            async with app.run_test(size=(120, 35)) as pilot:
                await pilot.pause()
                # Large terminal: split layout active
                assert app.effective_view_mode == "split"
                assert "-narrow" not in app.classes
                assert "-short" not in app.classes
                assert app.query_one("#info-card").display is True

                # Resize to standard 80x24 terminal
                await pilot.resize_terminal(80, 24)
                await pilot.pause()
                assert app._term_width == 80
                assert app._term_height == 24
                assert "-narrow" in app.classes
                assert "-short" in app.classes
                # In auto mode under 85 columns, defaults to full tracks view
                assert app.effective_view_mode == "tracks"
                assert app.query_one("#right-panel").display is False
                assert app.query_one("#left-panel").display is True
                assert app.query_one("#info-card").display is False

                # Resize to ultra-small window (60x16)
                await pilot.resize_terminal(60, 16)
                await pilot.pause()
                assert "-ultra-narrow" in app.classes
                assert "-ultra-short" in app.classes
                assert app.query_one("#visualizer-card").display is False
                assert app.query_one("#top-bar").display is False

    asyncio.run(_async_run())


def test_tui_view_mode_cycling():
    async def _async_run():
        with patch("scloud_player.player.subprocess.Popen"), \
             patch("scloud_player.visualizer.subprocess.Popen"), \
             patch("scloud_player.tui.load_config", return_value={"volume": 80, "visualizer": "cava"}), \
             patch("scloud_player.tui.fetch_track_page") as mock_fetch:

            mock_fetch.return_value = MagicMock(
                tracks=[{"id": "1", "title": "Track 1", "uploader": "Artist", "duration": 150}],
                page=1,
                page_size=40,
                has_next=False,
                playlist_title="Test",
                total_tracks=1
            )
            app = ScloudPlayerApp()

            async with app.run_test(size=(100, 30)) as pilot:
                await pilot.pause()
                assert app.view_mode == "auto"
                assert app.effective_view_mode == "split"

                # Cycle: split -> tracks
                app.action_cycle_view()
                assert app.view_mode == "tracks"
                await pilot.pause()
                # On tracks tab: if room allows (size 100x30), sidebar is KEPT!
                assert app.query_one("#left-panel").display is True
                assert app.query_one("#right-panel").display is True

                # When resized to narrow (80x24), room does not allow, so sidebar hides:
                await pilot.resize_terminal(80, 24)
                await pilot.pause()
                assert app.query_one("#left-panel").display is True
                assert app.query_one("#right-panel").display is False

                # Restore size to 100x30: sidebar reappears
                await pilot.resize_terminal(100, 30)
                await pilot.pause()
                assert app.query_one("#left-panel").display is True
                assert app.query_one("#right-panel").display is True

                # Cycle: tracks -> visualizer
                app.action_cycle_view()
                assert app.view_mode == "visualizer"
                await pilot.pause()
                assert app.query_one("#left-panel").display is False
                assert app.query_one("#right-panel").display is True

                # Cycle: visualizer -> split
                app.action_cycle_view()
                assert app.view_mode == "split"
                await pilot.pause()
                assert app.query_one("#left-panel").display is True
                assert app.query_one("#right-panel").display is True

    asyncio.run(_async_run())


def test_transport_bar_responsive_tiers():
    async def _async_run():
        from scloud_player.tui import TransportBar
        with patch("scloud_player.player.subprocess.Popen"), \
             patch("scloud_player.visualizer.subprocess.Popen"), \
             patch("scloud_player.tui.load_config", return_value={"volume": 80, "visualizer": "cava"}), \
             patch("scloud_player.tui.fetch_track_page"):
            app = ScloudPlayerApp()
            async with app.run_test() as pilot:
                tbar = app.query_one("#transport-bar", TransportBar)
                # Test all width tiers
                for test_width in [140, 100, 75, 50]:
                    tbar.update_transport(
                        title="A very long song title that might overflow",
                        artist="Producer / DJ Artist Name",
                        time_pos=45.0,
                        duration=180.0,
                        volume=85.0,
                        is_playing=True,
                        is_paused=False,
                        autoplay=True,
                        shuffle=False,
                        repeat="one",
                        cached_count=20,
                        total_in_page=40,
                        width=test_width
                    )
                    assert tbar.render() is not None

    asyncio.run(_async_run())


def test_visualizer_and_now_playing_responsive():
    async def _async_run():
        from scloud_player.tui import VisualizerWidget, NowPlayingCard
        with patch("scloud_player.player.subprocess.Popen"), \
             patch("scloud_player.visualizer.subprocess.Popen"), \
             patch("scloud_player.tui.load_config", return_value={"volume": 80, "visualizer": "cava"}), \
             patch("scloud_player.tui.fetch_track_page"):
            app = ScloudPlayerApp()
            async with app.run_test() as pilot:
                vis = app.query_one("#visualizer-card", VisualizerWidget)
                np_card = app.query_one("#now-playing-card", NowPlayingCard)

                # Narrow width (< 30)
                vis.update_state(is_playing=True, is_paused=False, mode="cava", width=22, height=6)
                assert vis.render() is not None

                np_card.update_track({"title": "Test Title", "uploader": "Artist", "duration": 120}, True, False, width=22)
                assert np_card.render() is not None

                # Wide width (>= 80)
                vis.update_state(is_playing=True, is_paused=False, mode="cava", width=90, height=8)
                assert vis.render() is not None

                np_card.update_track({"title": "Test Title", "uploader": "Artist", "duration": 120}, True, False, width=90)
                assert np_card.render() is not None

    asyncio.run(_async_run())
