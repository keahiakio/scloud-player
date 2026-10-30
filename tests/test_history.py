# SPDX-License-Identifier: MIT OR Apache-2.0
import asyncio
import os
from unittest.mock import MagicMock, patch
import pytest

from scloud_player.config import add_url_to_history, load_url_history
from scloud_player.tui import UrlModal, ScloudPlayerApp
from textual.widgets import Input


def test_url_history_add_and_deduplicate(tmp_path):
    url_hist_file = str(tmp_path / "url_history.txt")
    hist_file = str(tmp_path / "cli_history.txt")

    with patch("scloud_player.config.URL_HISTORY_FILE", url_hist_file), \
         patch("scloud_player.config.HISTORY_FILE", hist_file):

        # Initially empty
        assert load_url_history() == []

        # Add URLs
        add_url_to_history("https://soundcloud.com/artist1")
        add_url_to_history("https://soundcloud.com/artist2")
        add_url_to_history("https://soundcloud.com/artist3")

        history = load_url_history()
        assert history == [
            "https://soundcloud.com/artist1",
            "https://soundcloud.com/artist2",
            "https://soundcloud.com/artist3",
        ]

        # Re-adding artist1 moves it to the most recent spot
        add_url_to_history("https://soundcloud.com/artist1")
        history2 = load_url_history()
        assert history2 == [
            "https://soundcloud.com/artist2",
            "https://soundcloud.com/artist3",
            "https://soundcloud.com/artist1",
        ]


def test_url_modal_up_down_navigation(tmp_path):
    async def _async_run():
        with patch("scloud_player.tui.load_url_history", return_value=[
            "https://soundcloud.com/first",
            "https://soundcloud.com/second",
            "https://soundcloud.com/third",
        ]):
            modal = UrlModal()
            app = ScloudPlayerApp()

            # Push modal and test actions directly
            modal.history = [
                "https://soundcloud.com/first",
                "https://soundcloud.com/second",
                "https://soundcloud.com/third",
            ]
            modal.history_index = 3

            async with app.run_test() as pilot:
                app.push_screen(modal)
                await pilot.pause()

                inp = modal.query_one("#url-input", Input)
                inp.value = "my-custom-typed-text"

                # Press Up -> should recall latest history ("third")
                modal.action_history_prev()
                assert inp.value == "https://soundcloud.com/third"

                # Press Up -> should recall "second"
                modal.action_history_prev()
                assert inp.value == "https://soundcloud.com/second"

                # Press Up -> should recall "first"
                modal.action_history_prev()
                assert inp.value == "https://soundcloud.com/first"

                # Press Up at beginning stays at "first"
                modal.action_history_prev()
                assert inp.value == "https://soundcloud.com/first"

                # Press Down -> moves forward to "second"
                modal.action_history_next()
                assert inp.value == "https://soundcloud.com/second"

                # Press Down -> moves forward to "third"
                modal.action_history_next()
                assert inp.value == "https://soundcloud.com/third"

                # Press Down at end -> restores original typed text!
                modal.action_history_next()
                assert inp.value == "my-custom-typed-text"

    asyncio.run(_async_run())
