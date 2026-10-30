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


def test_playback_state_live_interpolation():
    import time
    state = PlaybackState()
    state.is_playing = True
    state.is_paused = False
    state.duration = 180.0
    state.time_pos = 10.0
    state.last_time_update = time.time()

    time.sleep(0.1)
    assert state.current_time_pos >= 10.08
    assert state.progress_pct > (10.0 / 180.0)

    # When paused, interpolation stops
    state.is_paused = True
    paused_pos = state.current_time_pos
    time.sleep(0.05)
    assert state.current_time_pos == paused_pos


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


def test_player_error_callback():
    from scloud_player.player import MpvPlayer
    import json
    import time
    with patch("scloud_player.player.subprocess.Popen"), \
         patch("scloud_player.player.socket.socket"):
        player = MpvPlayer()
        player._running = False
        track = {"id": "123", "title": "Fail Song"}
        player._state.current_track = track

        error_called = []
        player.set_on_track_error_callback(lambda trk: error_called.append(trk))

        player._handle_ipc_message(json.dumps({"event": "end-file", "reason": "error"}))
        time.sleep(0.1)
        assert len(error_called) == 1
        assert error_called[0] == track
