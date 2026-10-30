# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2026 Kiwi Akio

"""
MPV audio player engine using JSON IPC over Unix domain sockets.
Provides non-blocking transport controls, seek bar status polling,
and automatic end-of-track event handling for autoplay.
"""

import json
import os
import socket
import subprocess
import tempfile
import threading
import time
from typing import Callable, Optional
from scloud_player.config import get_mpv_executable


def get_visualizer_args(vis_type, title, uploader, fullscreen=True):
    """
    Builds mpv command-line flags to render an audio visualization + track details
    onto the connected external display or terminal (for CLI or standalone mode).
    """
    if not vis_type or str(vis_type).lower() == "off":
        return []

    vis = str(vis_type).lower()
    if vis == "spectrum":
        lavfi = "[aid1]asplit[ao][v];[v]showfreqs=s=1920x1080:mode=bar:ascale=log:fscale=log:win_size=1024:colors=0x00f2fe|0x4facfe|0x00ffff[vo]"
    elif vis == "waves":
        lavfi = "[aid1]asplit[ao][v];[v]showwaves=s=1920x1080:mode=line:scale=cbrt:colors=0x00ffff|0xff007f[vo]"
    elif vis == "vectorscope":
        lavfi = "[aid1]asplit[ao][v];[v]avectorscope=s=1920x1080:m=lissajous:scale=sqrt:draw=line:rc=0:gc=242:bc=254[vo]"
    elif vis == "caca":
        return [
            "--vo=caca",
            "--lavfi-complex=[aid1]asplit[ao][v];[v]showfreqs=s=80x24:mode=bar:ascale=log[vo]",
        ]
    else:
        lavfi = "[aid1]asplit[ao][v];[v]showfreqs=s=1920x1080:mode=bar:ascale=log:fscale=log:colors=0x00f2fe|0x4facfe[vo]"

    clean_title = (title or "SoundCloud").replace("\n", " ").replace('"', '\\"')
    clean_uploader = (uploader or "").replace("\n", " ").replace('"', '\\"')
    osd_msg = f"{clean_title}\nby {clean_uploader}" if clean_uploader else clean_title

    args = [
        f"--lavfi-complex={lavfi}",
        f"--osd-playing-msg={osd_msg}",
        "--osd-font-size=42",
        "--osd-align-x=center",
        "--osd-align-y=top",
        "--osd-margin-y=55",
        "--osd-border-size=3",
        "--osd-shadow-offset=2",
        "--osd-duration=7000",
        "--keep-open=no",
    ]

    if fullscreen:
        args.append("--fs")

    return args


class PlaybackState:
    def __init__(self):
        self.is_playing: bool = False
        self.is_paused: bool = False
        self.time_pos: float = 0.0
        self.last_time_update: float = 0.0
        self.duration: float = 0.0
        self.volume: float = 80.0
        self.current_track: Optional[dict] = None
        self.idle: bool = True

    @property
    def current_time_pos(self) -> float:
        """Returns live-interpolated playback position in seconds."""
        if self.is_playing and not self.is_paused and self.last_time_update > 0:
            elapsed = time.time() - self.last_time_update
            est = self.time_pos + min(elapsed, 1.0)
            if self.duration > 0:
                return min(est, self.duration)
            return est
        return self.time_pos

    @property
    def progress_pct(self) -> float:
        dur = self.duration
        if dur > 0:
            return min(max(self.current_time_pos / dur, 0.0), 1.0)
        return 0.0


class MpvPlayer:
    """Controls mpv via Unix Domain Socket JSON IPC."""

    def __init__(self, initial_volume: int = 80):
        self.mpv_path = get_mpv_executable()
        self.sock_path = os.path.join(tempfile.gettempdir(), f"scloud_mpv_{os.getpid()}.sock")
        self._proc: Optional[subprocess.Popen] = None
        self._sock: Optional[socket.socket] = None
        self._lock = threading.Lock()
        self._running = False
        self._req_id = 1
        self._pending_requests: dict = {}
        self._state = PlaybackState()
        self._state.volume = float(initial_volume)
        self._on_track_end: Optional[Callable[[], None]] = None

        self._start_mpv()
        self._connect_ipc()

        # Background listener thread for MPV IPC events & status
        self._listener_thread = threading.Thread(target=self._ipc_listener_loop, daemon=True)
        self._listener_thread.start()

    def set_on_track_end_callback(self, cb: Callable[[], None]):
        self._on_track_end = cb

    def _start_mpv(self):
        """Starts background mpv daemon with IPC server enabled."""
        if os.path.exists(self.sock_path):
            try:
                os.remove(self.sock_path)
            except OSError:
                pass

        cmd = [
            self.mpv_path,
            "--idle=yes",
            f"--input-ipc-server={self.sock_path}",
            "--no-video",
            "--no-terminal",
            f"--volume={int(self._state.volume)}",
        ]

        self._proc = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
        )

    def _connect_ipc(self, timeout: float = 3.0):
        """Connects to the mpv IPC domain socket and sets up property observation."""
        start = time.time()
        while time.time() - start < timeout:
            if os.path.exists(self.sock_path):
                try:
                    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                    s.connect(self.sock_path)
                    s.settimeout(0.5)
                    self._sock = s
                    self._running = True
                    # Register property observers for push notifications
                    for idx, prop in enumerate(["time-pos", "duration", "pause", "volume", "idle-active"], start=1):
                        payload = json.dumps({"command": ["observe_property", idx, prop]}) + "\n"
                        self._sock.sendall(payload.encode("utf-8"))
                    return
                except (socket.error, OSError):
                    pass
            time.sleep(0.05)

    def _send_command(self, cmd_list: list, prop_name: Optional[str] = None) -> Optional[dict]:
        """Sends an IPC JSON command and returns response data if available."""
        with self._lock:
            if not self._sock or not self._running:
                return None
            self._req_id += 1
            if prop_name:
                self._pending_requests[self._req_id] = prop_name
            payload = json.dumps({"command": cmd_list, "request_id": self._req_id}) + "\n"
            try:
                self._sock.sendall(payload.encode("utf-8"))
            except Exception:
                return None
            return None

    def _query_property(self, prop_name: str):
        """Queries an mpv property synchronously."""
        self._send_command(["get_property", prop_name], prop_name=prop_name)

    def _ipc_listener_loop(self):
        """Continuously listens to mpv IPC events and status updates."""
        buffer = ""
        last_poll = 0
        while self._running:
            try:
                # Periodic property poll (every 250ms)
                now = time.time()
                if now - last_poll >= 0.25:
                    last_poll = now
                    self._send_command(["get_property", "time-pos"], prop_name="time-pos")
                    self._send_command(["get_property", "duration"], prop_name="duration")
                    self._send_command(["get_property", "pause"], prop_name="pause")
                    self._send_command(["get_property", "volume"], prop_name="volume")
                    self._send_command(["get_property", "idle-active"], prop_name="idle-active")

                if not self._sock:
                    time.sleep(0.1)
                    continue

                try:
                    data = self._sock.recv(4096)
                    if not data:
                        time.sleep(0.05)
                        continue
                    buffer += data.decode("utf-8", errors="ignore")
                except (socket.timeout, BlockingIOError):
                    continue

                while "\n" in buffer:
                    line, buffer = buffer.split("\n", 1)
                    line = line.strip()
                    if not line:
                        continue
                    self._handle_ipc_message(line)

            except Exception:
                time.sleep(0.1)

    def _handle_ipc_message(self, message_str: str):
        """Handles parsed JSON responses and events from mpv."""
        try:
            msg = json.loads(message_str)
        except Exception:
            return

        event = msg.get("event")
        if event == "property-change":
            name = msg.get("name")
            data = msg.get("data")
            if name == "time-pos" and data is not None:
                self._state.time_pos = float(data)
                self._state.last_time_update = time.time()
            elif name == "duration" and data is not None:
                d = float(data)
                if d > 0:
                    self._state.duration = d
            elif name == "pause" and data is not None:
                self._state.is_paused = bool(data)
            elif name == "volume" and data is not None:
                self._state.volume = float(data)
            elif name == "idle-active" and data is not None:
                self._state.idle = bool(data)
                if self._state.idle:
                    self._state.is_playing = False

        elif event == "end-file":
            reason = msg.get("reason")
            # If track finished naturally (eof), notify listener for autoplay
            if reason == "eof":
                self._state.is_playing = False
                self._state.idle = True
                if self._on_track_end:
                    threading.Thread(target=self._on_track_end, daemon=True).start()
            elif reason in ("quit", "error"):
                self._state.is_playing = False
                self._state.idle = True

        elif event == "playback-restart":
            self._state.is_playing = True
            self._state.idle = False
            self._state.last_time_update = time.time()

        # Property reply handling via request_id
        req_id = msg.get("request_id")
        if req_id and req_id in self._pending_requests:
            prop = self._pending_requests.pop(req_id)
            data = msg.get("data")
            if data is not None:
                if prop == "time-pos":
                    self._state.time_pos = float(data)
                    self._state.last_time_update = time.time()
                elif prop == "duration":
                    d = float(data)
                    if d > 0:
                        self._state.duration = d
                elif prop == "pause":
                    self._state.is_paused = bool(data)
                elif prop == "volume":
                    self._state.volume = float(data)
                elif prop == "idle-active":
                    self._state.idle = bool(data)
                    if self._state.idle:
                        self._state.is_playing = False

    def play(self, stream_url: str, track_metadata: Optional[dict] = None):
        """Loads and starts playing a stream URL."""
        self._state.current_track = track_metadata
        self._state.is_playing = True
        self._state.is_paused = False
        self._state.time_pos = 0.0
        self._state.last_time_update = time.time()
        self._state.duration = float(track_metadata.get("duration") or 0.0) if track_metadata else 0.0
        self._state.idle = False

        self._send_command(["loadfile", stream_url, "replace"])

    def pause(self):
        """Pauses playback."""
        self._state.is_paused = True
        self._send_command(["set_property", "pause", True])

    def resume(self):
        """Resumes playback."""
        self._state.is_paused = False
        self._state.last_time_update = time.time()
        self._send_command(["set_property", "pause", False])

    def toggle_pause(self):
        """Toggles play/pause state."""
        self._state.is_paused = not self._state.is_paused
        if not self._state.is_paused:
            self._state.last_time_update = time.time()
        self._send_command(["cycle", "pause"])

    def stop(self):
        """Stops audio playback."""
        self._state.is_playing = False
        self._state.is_paused = False
        self._state.time_pos = 0.0
        self._state.idle = True
        self._send_command(["stop"])

    def seek(self, seconds: float):
        """Seeks relative to current position."""
        self._send_command(["seek", seconds, "relative"])
        self._state.time_pos = max(0.0, self._state.current_time_pos + seconds)
        self._state.last_time_update = time.time()

    def seek_percent(self, pct: float):
        """Seeks to absolute percentage (0-100)."""
        self._send_command(["seek", pct, "absolute-percent"])
        if self._state.duration > 0:
            self._state.time_pos = (pct / 100.0) * self._state.duration
            self._state.last_time_update = time.time()

    def set_volume(self, volume: float):
        """Sets playback volume (0 to 100)."""
        vol = max(0.0, min(100.0, volume))
        self._state.volume = vol
        self._send_command(["set_property", "volume", vol])

    def add_volume(self, delta: float):
        """Increases or decreases playback volume."""
        new_vol = max(0.0, min(100.0, self._state.volume + delta))
        self.set_volume(new_vol)

    def get_state(self) -> PlaybackState:
        """Returns the current playback state snapshot."""
        return self._state

    def shutdown(self):
        """Shuts down mpv process and cleans up IPC domain socket."""
        self._running = False
        try:
            self._send_command(["quit"])
        except Exception:
            pass
        if self._sock:
            try:
                self._sock.close()
            except Exception:
                pass
            self._sock = None
        if self._proc:
            try:
                self._proc.terminate()
                self._proc.wait(timeout=1.0)
            except Exception:
                try:
                    self._proc.kill()
                except Exception:
                    pass
            self._proc = None
        if os.path.exists(self.sock_path):
            try:
                os.remove(self.sock_path)
            except OSError:
                pass
