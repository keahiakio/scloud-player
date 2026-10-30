# SPDX-License-Identifier: MIT OR Apache-2.0
from unittest.mock import MagicMock, patch
import pytest

from scloud_player.player import PlaybackState, get_visualizer_args


def test_playback_state_progress():
    state = PlaybackState()
    assert state.progress_pct == 0.0

    state.duration = 200.0
    state.time_pos = 50.0
    assert state.progress_pct == 0.25

    # Clamping
    state.time_pos = 300.0
    assert state.progress_pct == 1.0


def test_visualizer_args_variations():
    # Waves mode
    waves_args = get_visualizer_args("waves", "Song A", "Artist B", fullscreen=False)
    assert any("showwaves" in a for a in waves_args)
    assert "--fs" not in waves_args

    # Vectorscope mode
    vec_args = get_visualizer_args("vectorscope", "Song A", "Artist B", fullscreen=True)
    assert any("avectorscope" in a for a in vec_args)
    assert "--fs" in vec_args

    # Caca mode
    caca_args = get_visualizer_args("caca", "Song", "Artist")
    assert "--vo=caca" in caca_args
