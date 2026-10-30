# SPDX-License-Identifier: MIT OR Apache-2.0
from unittest.mock import MagicMock, patch
import pytest

from scloud_player.visualizer import CavaRunner, VisualizerEngine, UNICODE_BLOCKS


def test_visualizer_engine_simulated_bars():
    engine = VisualizerEngine(num_bars=16)

    # When playing, should return dynamic values
    bars_playing = engine.get_bar_values(is_playing=True, is_paused=False, mode="spectrum")
    assert len(bars_playing) == 16
    assert any(b > 0 for b in bars_playing)

    # When mode is off, should return all zeros
    bars_off = engine.get_bar_values(is_playing=True, is_paused=False, mode="off")
    assert bars_off == [0] * 16

    # When paused, should decay towards zero
    bars_paused = engine.get_bar_values(is_playing=True, is_paused=True, mode="spectrum")
    assert len(bars_paused) == 16


def test_visualizer_render_grid():
    engine = VisualizerEngine(num_bars=8)
    values = [0, 20, 50, 80, 100, 60, 30, 10]
    grid = engine.render_grid(values, height=6, bar_width=1, bar_spacing=1)

    assert len(grid) == 6
    for row in grid:
        assert len(row.plain) > 0


def test_cava_runner_config_generation():
    runner = CavaRunner(num_bars=24, framerate=30)
    cfg_path = runner._create_temp_cava_config()

    try:
        with open(cfg_path, "r") as f:
            content = f.read()
        assert "bars = 24" in content
        assert "framerate = 30" in content
        assert "data_format = ascii" in content
    finally:
        import os
        if os.path.exists(cfg_path):
            os.remove(cfg_path)
