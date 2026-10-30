# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2026 Kiwi Akio

"""
Live audio visualizer integration for scloud-player.
Interfaces with CAVA (Console-based Audio Visualizer for ALSA/Pulse/PipeWire)
via raw stdout streaming, rendering dynamic unicode spectrum bars with
vibrant color gradients in real-time.
"""

import math
import os
import random
import subprocess
import tempfile
import threading
import time
from typing import List, Optional
from rich.text import Text
from scloud_player.config import get_cava_executable

UNICODE_BLOCKS = [" ", " ", "▂", "▃", "▄", "▅", "▆", "▇", "█"]


class CavaRunner:
    """Spawns and streams frequency bars from cava in background."""

    def __init__(self, num_bars: int = 24, framerate: int = 30):
        self.num_bars = num_bars
        self.framerate = framerate
        self.cava_path = get_cava_executable()
        self._proc: Optional[subprocess.Popen] = None
        self._cfg_file: Optional[str] = None
        self._running = False
        self._lock = threading.Lock()
        self._bars = [0] * num_bars
        self._last_active_time = 0.0

        if self.cava_path:
            self._start_cava()

    def _create_temp_cava_config(self) -> str:
        """Generates temporary CAVA configuration for raw stdout output."""
        cfg = f"""
[general]
bars = {self.num_bars}
framerate = {self.framerate}
autosens = 1

[input]
method = pulse
source = auto

[output]
method = raw
raw_target = /dev/stdout
data_format = ascii
ascii_max_range = 100
bar_delimiter = 59
"""
        fd, path = tempfile.mkstemp(prefix="scloud_cava_", suffix=".conf")
        with os.fdopen(fd, "w") as f:
            f.write(cfg.strip())
        return path

    def _start_cava(self):
        """Starts cava process in raw stdout mode."""
        if not self.cava_path:
            return

        try:
            self._cfg_file = self._create_temp_cava_config()
            self._proc = subprocess.Popen(
                [self.cava_path, "-p", self._cfg_file],
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                stdin=subprocess.DEVNULL,
                text=True,
                bufsize=1,
            )
            self._running = True
            threading.Thread(target=self._read_cava_stdout, daemon=True).start()
        except Exception:
            self._running = False

    def _read_cava_stdout(self):
        """Continuously reads frequency bar data from cava's stdout."""
        while self._running and self._proc and self._proc.stdout:
            try:
                line = self._proc.stdout.readline()
                if not line:
                    break
                line = line.strip()
                if not line:
                    continue

                parts = [p for p in line.split(";") if p.isdigit()]
                if parts:
                    vals = [min(max(int(p), 0), 100) for p in parts[:self.num_bars]]
                    while len(vals) < self.num_bars:
                        vals.append(0)

                    with self._lock:
                        self._bars = vals
                        if any(v > 0 for v in vals):
                            self._last_active_time = time.time()
            except Exception:
                break
        self._running = False

    def get_bars(self) -> List[int]:
        """Returns the current raw frequency bar values (0-100)."""
        with self._lock:
            return list(self._bars)

    def is_active(self) -> bool:
        """Returns True if cava has received non-zero audio input recently."""
        return (time.time() - self._last_active_time) < 1.0

    def is_running(self) -> bool:
        """Returns True if the cava process is running."""
        return self._running and self._proc is not None and self._proc.poll() is None

    def stop(self):
        """Stops cava process and removes temp configuration."""
        self._running = False
        if self._proc:
            try:
                self._proc.terminate()
                self._proc.wait(timeout=0.5)
            except Exception:
                try:
                    self._proc.kill()
                except Exception:
                    pass
            self._proc = None

        if self._cfg_file and os.path.exists(self._cfg_file):
            try:
                os.remove(self._cfg_file)
            except OSError:
                pass


class VisualizerEngine:
    """
    Renders live frequency bars onto text grids with color gradients.
    Provides dynamic rhythm physics simulation when cava is inactive.
    """

    def __init__(self, num_bars: int = 24):
        self.num_bars = num_bars
        self.cava = CavaRunner(num_bars=num_bars)
        self._sim_bars = [0.0] * num_bars
        self._sim_phase = 0.0

    def stop(self):
        self.cava.stop()

    def get_bar_values(self, is_playing: bool, is_paused: bool, mode: str = "cava") -> List[int]:
        """Calculates current bar heights for the visualizer."""
        if mode == "off":
            return [0] * self.num_bars

        # If cava is active, use cava readings
        if mode == "cava" and self.cava.is_active():
            return self.cava.get_bars()

        # If playback is stopped or paused, smoothly decay bars to zero
        if not is_playing or is_paused:
            for i in range(self.num_bars):
                self._sim_bars[i] = max(0.0, self._sim_bars[i] - 12.0)
            return [int(v) for v in self._sim_bars]

        # Dynamic simulation fallback (musical spectrum curves + rhythmic bounce)
        self._sim_phase += 0.25
        t = self._sim_phase
        for i in range(self.num_bars):
            # Frequency curve: higher bass on left, resonant mids, rolling highs on right
            rel_idx = i / float(self.num_bars)
            freq_bias = math.exp(-2.5 * rel_idx) * 75.0 + 15.0

            # Sine harmonics simulating drum beats and melody
            beat = math.sin(t * 1.5) * 20.0 + math.cos(t * 3.0 + i * 0.5) * 15.0
            noise = random.uniform(-8.0, 12.0)
            target = max(5.0, min(98.0, freq_bias + beat + noise))

            # Exponential decay & smoothing
            self._sim_bars[i] = self._sim_bars[i] * 0.65 + target * 0.35

        return [int(v) for v in self._sim_bars]

    def render_grid(
        self,
        values: List[int],
        height: int = 8,
        bar_width: int = 1,
        bar_spacing: int = 1
    ) -> List[Text]:
        """
        Renders a 2D grid of colored Text lines representing the audio spectrum.
        Gradient: Red/Magenta at peak -> Yellow/Cyan in mid -> Green/Blue at base.
        """
        if height < 1:
            height = 1

        rows = []
        for row in range(height - 1, -1, -1):
            row_ratio = row / float(height)

            # Determine color style based on row height
            if row_ratio > 0.8:
                style = "bold magenta"
            elif row_ratio > 0.6:
                style = "bold red"
            elif row_ratio > 0.4:
                style = "bold yellow"
            elif row_ratio > 0.2:
                style = "bright_cyan"
            else:
                style = "bright_blue"

            line_text = Text()
            for idx, val in enumerate(values):
                val = max(0, min(100, val))
                h = (val / 100.0) * height

                if h >= row + 1:
                    char = "█"
                elif h <= row:
                    char = " "
                else:
                    step = int((h - row) * 8)
                    char = UNICODE_BLOCKS[min(max(step, 1), 8)]

                # Add bar block repeated by bar_width
                line_text.append(char * bar_width, style=style if char != " " else "dim")
                if bar_spacing > 0 and idx < len(values) - 1:
                    line_text.append(" " * bar_spacing)

            rows.append(line_text)

        return rows
