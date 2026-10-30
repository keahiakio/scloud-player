#!/usr/bin/env python3
# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2026 Kiwi Akio

import os
import sys

# Auto re-exec with local virtualenv python if current python lacks dependencies
_venv_python = os.path.join(os.path.dirname(os.path.abspath(__file__)), "venv", "bin", "python")
if os.path.isfile(_venv_python) and sys.executable != _venv_python:
    try:
        import textual
        import rich
    except ImportError:
        os.execv(_venv_python, [_venv_python] + sys.argv)

"""
SoundCloud Player (scloud-player)
A responsive terminal audio player inspired by musikcube, with live CAVA visualizer,
30-track pagination, and background stream caching.
"""

import argparse

# Import modular components
from scloud_player import __version__
from scloud_player.api import (
    _get_soundcloud_ie,
    enrich_tracks_metadata,
    fetch_track_page,
    format_duration,
    get_full_track_info,
    get_stream_url,
    get_track_data,
)
from scloud_player.cache import SongCacheManager, resolve_stream_url
from scloud_player.cli import (
    ansi_to_readline,
    clear_terminal,
    display_tracks,
    get_user_input,
    intermission,
    play_track,
    run_cli,
    setup_readline,
)
from scloud_player.config import (
    CONFIG_FILE,
    DEFAULT_CONFIG,
    HISTORY_FILE,
    load_config,
    save_config,
)
from scloud_player.player import (
    MpvPlayer,
    get_visualizer_args,
)
from scloud_player.tui import run_tui
from scloud_player.visualizer import CavaRunner, VisualizerEngine

# Ensure backward compatibility for imports from main
__all__ = [
    "format_duration",
    "load_config",
    "save_config",
    "DEFAULT_CONFIG",
    "CONFIG_FILE",
    "HISTORY_FILE",
    "get_track_data",
    "enrich_tracks_metadata",
    "_get_soundcloud_ie",
    "get_full_track_info",
    "get_stream_url",
    "get_visualizer_args",
    "play_track",
    "intermission",
    "display_tracks",
    "setup_readline",
    "get_user_input",
    "clear_terminal",
]


def main():
    parser = argparse.ArgumentParser(
        description="scloud-player: Responsive Terminal SoundCloud Player (Musikcube Edition)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  scloud-player
  scloud-player "https://soundcloud.com/discover"
  scloud-player --cli "https://soundcloud.com/artist/sets/playlist"
        """
    )
    parser.add_argument("url", nargs="?", default=None, help="SoundCloud track, playlist, or artist URL")
    parser.add_argument("--cli", "--no-tui", action="store_true", help="Launch in classic terminal CLI mode instead of TUI")
    parser.add_argument("-v", "--version", action="version", version=f"scloud-player {__version__}")

    args = parser.parse_args()

    # Determine whether to run TUI or classic CLI
    # If stdout is not a TTY (e.g. piped), fallback to CLI
    if args.cli or not sys.stdout.isatty():
        run_cli(initial_url=args.url)
    else:
        run_tui(initial_url=args.url)


if __name__ == "__main__":
    main()
