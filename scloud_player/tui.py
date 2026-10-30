# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2026 Kiwi Akio

"""
Responsive Musikcube-inspired Terminal User Interface for scloud-player.
Built with Textual, featuring multi-panel layout, live CAVA spectrum visualizer,
paginated track browsing (30 max), 30-song background stream cache,
and interactive transport controls.
"""

import asyncio
import math
import os
import random
import shutil
import subprocess
import threading
from typing import List, Optional

from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from textual import events
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import (
    Button,
    DataTable,
    Footer,
    Header,
    Input,
    Label,
    ProgressBar,
    Static,
)

from scloud_player.api import (
    TrackPage,
    fetch_track_page,
    format_duration,
    get_stream_url,
)
from scloud_player.cache import SongCacheManager
from scloud_player.config import add_url_to_history, load_config, load_url_history, save_config
from scloud_player.player import MpvPlayer
from scloud_player.visualizer import VisualizerEngine


class UrlModal(ModalScreen[Optional[str]]):
    """Modal dialog for entering a new SoundCloud URL with Up/Down history navigation."""

    DEFAULT_CSS = """
    UrlModal {
        align: center middle;
        background: rgba(0, 0, 0, 0.7);
    }

    #url-dialog {
        padding: 1 2;
        width: 90%;
        max-width: 76;
        height: auto;
        border: thick $primary;
        background: $surface;
    }

    #url-history-hint {
        margin-top: 1;
        color: $text-muted;
    }

    #url-buttons {
        margin-top: 1;
        align: right middle;
    }

    Button {
        margin-left: 1;
    }
    """

    BINDINGS = [
        Binding("up", "history_prev", "Previous History URL", priority=True),
        Binding("down", "history_next", "Next History URL", priority=True),
        Binding("escape", "cancel", "Cancel", priority=True),
    ]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.history: List[str] = load_url_history()
        self.history_index: int = len(self.history)
        self._temp_input: str = ""

    def compose(self) -> ComposeResult:
        with Vertical(id="url-dialog"):
            yield Label("[bold cyan]Enter SoundCloud URL or Playlist:[/bold cyan]")
            yield Input(
                placeholder="https://soundcloud.com/artist or track/set URL",
                id="url-input"
            )
            count = len(self.history)
            hint = f"↑ / ↓ scroll history ({count} saved) | Enter load | Esc cancel"
            yield Label(f"[dim]{hint}[/dim]", id="url-history-hint")
            with Horizontal(id="url-buttons"):
                yield Button("Load", variant="primary", id="btn-load")
                yield Button("Cancel", variant="default", id="btn-cancel")

    def on_mount(self) -> None:
        self.query_one("#url-input", Input).focus()

    def action_history_prev(self) -> None:
        """Navigates to previous URL in history (older)."""
        if not self.history:
            return
        inp = self.query_one("#url-input", Input)
        if self.history_index == len(self.history):
            self._temp_input = inp.value

        if self.history_index > 0:
            self.history_index -= 1
            inp.value = self.history[self.history_index]
            inp.cursor_position = len(inp.value)

    def action_history_next(self) -> None:
        """Navigates to next URL in history (newer)."""
        if not self.history:
            return
        inp = self.query_one("#url-input", Input)
        if self.history_index < len(self.history) - 1:
            self.history_index += 1
            inp.value = self.history[self.history_index]
            inp.cursor_position = len(inp.value)
        elif self.history_index == len(self.history) - 1:
            self.history_index = len(self.history)
            inp.value = self._temp_input
            inp.cursor_position = len(inp.value)

    def action_cancel(self) -> None:
        self.dismiss(None)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-load":
            val = self.query_one("#url-input", Input).value.strip()
            if val:
                add_url_to_history(val)
            self.dismiss(val if val else None)
        else:
            self.dismiss(None)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        val = event.value.strip()
        if val:
            add_url_to_history(val)
        self.dismiss(val if val else None)


class CreditsModal(ModalScreen):
    """Modal dialog displaying credits and acknowledgements for open source projects."""

    DEFAULT_CSS = """
    CreditsModal {
        align: center middle;
        background: rgba(0, 0, 0, 0.75);
    }

    #credits-dialog {
        padding: 1 2;
        width: 92%;
        max-width: 78;
        max-height: 90%;
        height: auto;
        border: thick $primary;
        background: $surface;
    }

    #credits-title {
        text-align: center;
        margin-bottom: 1;
    }

    #credits-body {
        margin-bottom: 1;
    }

    #credits-buttons {
        align: right middle;
    }
    """

    BINDINGS = [
        Binding("escape", "dismiss", "Close", priority=True),
        Binding("enter", "dismiss", "Close", priority=True),
        Binding("space", "dismiss", "Close", priority=True),
        Binding("q", "dismiss", "Close", priority=True),
    ]

    def compose(self) -> ComposeResult:
        with Vertical(id="credits-dialog"):
            yield Label("[bold magenta]♫ SoundCloud Player — Credits ♫[/bold magenta]", id="credits-title")
            t = Table.grid(padding=(0, 1))
            t.add_column(width=13)
            t.add_column()

            t.add_row(Text("musikcube", style="bold cyan"), Text("Terminal audio UX, split layout & keyboard navigation inspiration (clangen)", style="white"))
            t.add_row(Text("CAVA", style="bold cyan"), Text("Audio spectrum visualizer backend for PulseAudio / PipeWire (Karl Stavestrand)", style="white"))
            t.add_row(Text("mpv", style="bold cyan"), Text("High-performance audio engine & JSON IPC daemon (mpv project)", style="white"))
            t.add_row(Text("Textual", style="bold cyan"), Text("Reactive terminal user interface framework (Will McGugan & Textualize)", style="white"))
            t.add_row(Text("Rich", style="bold cyan"), Text("Terminal styling, tables & renderables (Textualize)", style="white"))
            t.add_row(Text("yt-dlp", style="bold cyan"), Text("SoundCloud stream URL & metadata extractor (yt-dlp team)", style="white"))
            t.add_row(Text("FFmpeg", style="bold cyan"), Text("Multimedia audio decoding toolkit (FFmpeg team)", style="white"))
            t.add_row(Text("requests", style="bold cyan"), Text("HTTP library for SoundCloud API v2 batch enrichment (PSF)", style="white"))

            yield Static(Panel(t, title="[bold yellow]Open Source Credits[/bold yellow]", border_style="dim cyan"), id="credits-body")
            with Horizontal(id="credits-buttons"):
                yield Button("Close (Esc)", variant="primary", id="btn-close-credits")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss()


class VisualizerWidget(Static):
    """Widget displaying the live CAVA spectrum analyzer with color gradients."""

    def __init__(self, visualizer_engine: VisualizerEngine, **kwargs):
        super().__init__(**kwargs)
        self.engine = visualizer_engine
        self.vis_mode = "cava"
        self.is_playing = False
        self.is_paused = False

    def update_state(self, is_playing: bool, is_paused: bool, mode: str, width: Optional[int] = None, height: Optional[int] = None):
        self.is_playing = is_playing
        self.is_paused = is_paused
        self.vis_mode = mode
        self.refresh_bars(width=width, height=height)

    def refresh_bars(self, width: Optional[int] = None, height: Optional[int] = None):
        w = width if width is not None else self.size.width
        h = height if height is not None else self.size.height

        if w <= 0:
            w = 40
        if h <= 0:
            h = 8

        usable_w = max(8, w - 2)

        if usable_w < 20:
            bar_spacing = 0
            num_bars = max(6, min(16, usable_w))
        elif usable_w < 40:
            bar_spacing = 1
            num_bars = max(8, min(20, (usable_w + 1) // 2))
        else:
            bar_spacing = 1
            num_bars = max(12, min(36, (usable_w + 1) // 2))

        # Dynamic height calculation
        grid_height = max(3, min(7, h - 2))

        raw_values = self.engine.get_bar_values(
            is_playing=self.is_playing,
            is_paused=self.is_paused,
            mode=self.vis_mode
        )

        if len(raw_values) == num_bars:
            values = raw_values
        elif raw_values:
            values = []
            step = len(raw_values) / float(num_bars)
            for i in range(num_bars):
                idx = min(int(i * step), len(raw_values) - 1)
                values.append(raw_values[idx])
        else:
            values = [0] * num_bars

        lines = self.engine.render_grid(values, height=grid_height, bar_width=1, bar_spacing=bar_spacing)

        if usable_w < 24:
            header = Text(" ▃▅ CAVA ▅▃", style="bold cyan")
        elif usable_w < 36:
            header = Text(" ▃▅ LIVE CAVA ▅▃", style="bold cyan")
        else:
            header = Text(" ▃▅▇ LIVE CAVA VISUALIZER ▇▅▃", style="bold cyan")

        if self.vis_mode == "cava":
            status = " [LIVE]" if usable_w < 36 else (" [LIVE CAVA]" if self.engine.cava.is_active() else " [SPECTRUM]")
        elif self.vis_mode == "off":
            status = " [OFF]"
        else:
            status = f" [{self.vis_mode.upper()}]"

        if usable_w >= 28:
            header.append(status, style="dim yellow")

        full = Text()
        full.append_text(header)
        full.append("\n")
        for line in lines:
            full.append_text(line)
            full.append("\n")

        self.update(full)


class NowPlayingCard(Static):
    """Widget showing detailed metadata for the active track."""

    def update_track(self, track: Optional[dict], is_playing: bool, is_paused: bool, width: Optional[int] = None):
        w = width if width is not None else self.size.width
        if w <= 0:
            w = 32

        if not track:
            msg = "No track playing" if w < 36 else "\nNo track playing.\nSelect a track to start playback.\n"
            self.update(Panel(
                Text(msg, justify="center", style="dim white"),
                title="[bold magenta]♫ NOW PLAYING ♫[/bold magenta]" if w >= 30 else "♫ PLAYING",
                border_style="dim blue"
            ))
            return

        title = track.get("title") or "Unknown Title"
        artist = track.get("uploader") or track.get("artist") or "Unknown Artist"
        duration = format_duration(track.get("duration"))
        status_text = "⏸ PAUSED" if is_paused else ("▶ PLAYING" if is_playing else "⏹ STOPPED")
        status_style = "bold yellow" if is_paused else ("bold green" if is_playing else "dim")

        inner_w = max(10, w - 4)

        if w < 36:
            card_text = Text()
            card_text.append("🎵 ", style="cyan")
            card_text.append(f"{title[:max(8, inner_w - 4)]}\n", style="bold white")
            card_text.append("👤 ", style="dim cyan")
            card_text.append(f"{artist[:max(8, inner_w - 12)]} ", style="white")
            card_text.append(f"• {duration}\n", style="dim cyan")
            card_text.append("Status: ", style="dim")
            card_text.append(status_text, style=status_style)

            self.update(Panel(
                card_text,
                title="[bold magenta]♫ NOW PLAYING[/bold magenta]" if w >= 24 else "♫ NOW",
                border_style="bright_blue"
            ))
        else:
            t = Table.grid(padding=(0, 1))
            t.add_column(width=9)
            t.add_column()

            val_w = max(12, inner_w - 11)
            t.add_row(Text("Track:", style="bold cyan"), Text(title[:val_w], style="bold white"))
            t.add_row(Text("Artist:", style="bold cyan"), Text(artist[:val_w], style="bold white"))
            t.add_row(Text("Duration:", style="bold cyan"), Text(duration, style="bold white"))
            t.add_row(Text("Status:", style="bold cyan"), Text(status_text, style=status_style))

            genre = track.get("genre")
            if genre and inner_w > 40:
                t.add_row(Text("Genre:", style="bold cyan"), Text(str(genre)[:val_w], style="bold white"))

            self.update(Panel(
                t,
                title="[bold magenta]♫ NOW PLAYING ♫[/bold magenta]",
                border_style="bright_blue"
            ))


class TransportBar(Static):
    """Bottom playback transport bar with live seek bar and status badges."""

    def update_transport(
        self,
        title: str,
        artist: str,
        time_pos: float,
        duration: float,
        volume: float,
        is_playing: bool,
        is_paused: bool,
        autoplay: bool,
        shuffle: bool,
        repeat: str,
        cached_count: int,
        total_in_page: int,
        width: Optional[int] = None
    ):
        w = width if width is not None else self.size.width
        if w <= 0 and self.app:
            w = self.app.size.width
        if w <= 0:
            w = 80

        elapsed_str = format_duration(time_pos)
        total_str = format_duration(duration)
        icon = "⏸" if is_paused else ("▶" if is_playing else "⏹")
        icon_style = "bold yellow" if is_paused else ("bold green" if is_playing else "dim")

        bar_text = Text()

        if w >= 115:
            bar_len = 20
            if duration > 0:
                pct = min(max(time_pos / duration, 0.0), 1.0)
                filled = int(pct * bar_len)
            else:
                pct = 0.0
                filled = 0
            seek_line = "━" * filled + ("●" if filled < bar_len else "") + "─" * max(0, bar_len - filled - 1)

            track_label = f"{title[:26]} - {artist[:18]}" if title else "Ready"
            vol_len = 5
            vol_filled = int((volume / 100.0) * vol_len)
            vol_bar = "=" * vol_filled + "-" * (vol_len - vol_filled)

            bar_text.append(f" {icon} ", style=icon_style)
            bar_text.append(f"{track_label:<46} ", style="bold white")
            bar_text.append(f"{elapsed_str} ", style="bold cyan")
            bar_text.append(f"[{seek_line}]", style="bright_magenta")
            bar_text.append(f" {total_str}  ", style="bold cyan")
            bar_text.append(f"Vol:{int(volume):>3}% [{vol_bar}]  ", style="bright_blue")
            bar_text.append("[AUTO]", style="bold green" if autoplay else "dim")
            bar_text.append(" ")
            bar_text.append("[SHUF]", style="bold green" if shuffle else "dim")
            bar_text.append(" ")
            bar_text.append(f"[REP:{repeat.upper()}]", style="bold green" if repeat != "off" else "dim")
            bar_text.append(" ")
            bar_text.append(f"[CACHE:{cached_count}/{total_in_page} ⚡]", style="bold green" if cached_count > 0 else "dim")

        elif w >= 85:
            bar_len = 12
            if duration > 0:
                pct = min(max(time_pos / duration, 0.0), 1.0)
                filled = int(pct * bar_len)
            else:
                pct = 0.0
                filled = 0
            seek_line = "━" * filled + ("●" if filled < bar_len else "") + "─" * max(0, bar_len - filled - 1)

            track_label = f"{title[:20]} - {artist[:12]}" if title else "Ready"

            bar_text.append(f" {icon} ", style=icon_style)
            bar_text.append(f"{track_label:<34} ", style="bold white")
            bar_text.append(f"{elapsed_str} ", style="bold cyan")
            bar_text.append(f"[{seek_line}]", style="bright_magenta")
            bar_text.append(f" {total_str} ", style="bold cyan")
            bar_text.append(f"Vol:{int(volume)}% ", style="bright_blue")
            bar_text.append("[A]", style="bold green" if autoplay else "dim")
            bar_text.append(" ")
            bar_text.append("[S]", style="bold green" if shuffle else "dim")
            bar_text.append(" ")
            rep_lbl = f"[R:{repeat[0].upper()}]" if repeat != "off" else "[R]"
            bar_text.append(rep_lbl, style="bold green" if repeat != "off" else "dim")
            bar_text.append(" ")
            bar_text.append(f"[⚡{cached_count}/{total_in_page}]", style="bold green" if cached_count > 0 else "dim")

        elif w >= 65:
            bar_len = 8
            if duration > 0:
                pct = min(max(time_pos / duration, 0.0), 1.0)
                filled = int(pct * bar_len)
            else:
                pct = 0.0
                filled = 0
            seek_line = "━" * filled + ("●" if filled < bar_len else "") + "─" * max(0, bar_len - filled - 1)

            track_label = f"{title[:14]} - {artist[:8]}" if title else "Ready"

            bar_text.append(f"{icon} ", style=icon_style)
            bar_text.append(f"{track_label:<24} ", style="bold white")
            bar_text.append(f"{elapsed_str}/{total_str} ", style="bold cyan")
            bar_text.append(f"[{seek_line}] ", style="bright_magenta")
            bar_text.append(f"V:{int(volume)}% ", style="bright_blue")
            bar_text.append("[A]" if autoplay else "·", style="bold green" if autoplay else "dim")
            bar_text.append("[S]" if shuffle else "·", style="bold green" if shuffle else "dim")
            bar_text.append(f"[{repeat[0].upper()}]" if repeat != "off" else "·", style="bold green" if repeat != "off" else "dim")
            bar_text.append(f"[⚡{cached_count}]", style="bold green" if cached_count > 0 else "dim")

        else:
            track_label = f"{title[:12]}" if title else "Ready"
            bar_text.append(f"{icon} ", style=icon_style)
            bar_text.append(f"{track_label} ", style="bold white")
            bar_text.append(f"{elapsed_str}/{total_str} ", style="bold cyan")
            bar_text.append(f"V:{int(volume)}% ", style="bright_blue")
            if autoplay:
                bar_text.append("A ", style="bold green")
            if shuffle:
                bar_text.append("S ", style="bold green")
            if repeat != "off":
                bar_text.append(f"R:{repeat[0].upper()} ", style="bold green")
            if cached_count > 0:
                bar_text.append(f"⚡{cached_count}", style="bold green")

        self.update(bar_text)


class ScloudPlayerApp(App):
    """Musikcube-style responsive Terminal Audio Player application."""

    TITLE = "SoundCloud Player"
    SUB_TITLE = "Musikcube Edition"

    CSS = """
    Screen {
        background: #11141c;
        color: #dce3f0;
    }

    #app-container {
        height: 100%;
        width: 100%;
    }

    #top-bar {
        dock: top;
        height: 1;
        background: #1b202e;
        color: #4facfe;
        padding: 0 1;
    }

    #main-split {
        height: 1fr;
        width: 100%;
    }

    #left-panel {
        width: 62%;
        height: 100%;
        border-right: solid #2c3549;
        padding: 0 1;
    }

    #right-panel {
        width: 38%;
        height: 100%;
        padding: 0 1;
    }

    #search-box {
        height: 3;
        margin-bottom: 0;
    }

    #tracks-table {
        height: 1fr;
        border: solid #22293a;
        background: #131722;
    }

    #pagination-bar {
        height: 1;
        dock: bottom;
        background: #1b202e;
        color: #00f2fe;
        padding: 0 1;
    }

    #now-playing-card {
        height: 7;
        margin-top: 0;
    }

    #visualizer-card {
        height: 9;
        border: solid #22293a;
        margin-top: 1;
        background: #131722;
    }

    #info-card {
        height: 1fr;
        min-height: 4;
        margin-top: 1;
        border: solid #22293a;
        background: #131722;
        padding: 0 1;
    }

    #transport-container {
        dock: bottom;
        height: auto;
        min-height: 1;
        max-height: 2;
        background: #181d2a;
        border-top: solid #4facfe;
        padding: 0 1;
    }

    /* ==================== VIEW MODES ==================== */
    /* Tracks view: keep sidebar if room allows (width >= 85), collapse to full width on narrow */
    .-view-tracks #left-panel {
        width: 62%;
        border-right: solid #2c3549;
        display: block;
    }
    .-view-tracks #right-panel {
        width: 38%;
        display: block;
    }

    .-narrow.-view-tracks #left-panel,
    .-view-tracks.-narrow #left-panel,
    Screen.-narrow.-view-tracks #left-panel,
    Screen.-view-tracks.-narrow #left-panel {
        width: 100%;
        border-right: none;
        display: block;
    }
    .-narrow.-view-tracks #right-panel,
    .-view-tracks.-narrow #right-panel,
    Screen.-narrow.-view-tracks #right-panel,
    Screen.-view-tracks.-narrow #right-panel {
        display: none;
    }

    /* Visualizer view: full width visualizer, hide tracklist */
    .-view-visualizer #left-panel {
        display: none;
    }
    .-view-visualizer #right-panel {
        width: 100%;
        display: block;
    }

    /* Split view: dual column layout */
    .-view-split #left-panel {
        width: 60%;
        border-right: solid #2c3549;
        display: block;
    }
    .-view-split #right-panel {
        width: 40%;
        display: block;
    }
    .-narrow.-view-split #left-panel,
    .-view-split.-narrow #left-panel,
    Screen.-narrow.-view-split #left-panel,
    Screen.-view-split.-narrow #left-panel {
        width: 100%;
        border-right: none;
        display: block;
    }
    .-narrow.-view-split #right-panel,
    .-view-split.-narrow #right-panel,
    Screen.-narrow.-view-split #right-panel,
    Screen.-view-split.-narrow #right-panel {
        display: none;
    }

    /* ==================== RESPONSIVE BREAKPOINTS ==================== */

    /* Narrow width (width < 85) */
    .-narrow #left-panel {
        padding: 0;
    }
    .-narrow #right-panel {
        padding: 0;
    }

    /* Short height (height < 26) */
    .-short #info-card {
        display: none;
    }
    .-short #visualizer-card {
        height: 6;
        margin-top: 0;
    }
    .-short #now-playing-card {
        height: 6;
    }

    /* Ultra-short height (height < 18) */
    .-ultra-short #top-bar {
        display: none;
    }
    .-ultra-short #info-card {
        display: none;
    }
    .-ultra-short #visualizer-card {
        display: none;
    }
    .-ultra-short #now-playing-card {
        height: 5;
        margin-top: 0;
    }
    .-ultra-short #search-box {
        display: none;
    }
    """

    BINDINGS = [
        Binding("space", "toggle_play", "Play/Pause", priority=True),
        Binding("enter", "play_selected", "Play Selected"),
        Binding("tab", "cycle_view", "Switch View", priority=True),
        Binding("m", "cycle_view", "Switch View"),
        Binding("bracket_right", "next_track", "Next Track"),
        Binding("bracket_left", "prev_track", "Prev Track"),
        Binding("N", "next_track", "Next Track"),
        Binding("P", "prev_track", "Prev Track"),
        Binding("n", "next_page", "Next Page"),
        Binding("p", "prev_page", "Prev Page"),
        Binding("right", "seek_forward", "Seek +5s"),
        Binding("left", "seek_backward", "Seek -5s"),
        Binding("plus", "volume_up", "Vol +5%"),
        Binding("equals", "volume_up", "Vol +5%"),
        Binding("minus", "volume_down", "Vol -5%"),
        Binding("a", "toggle_autoplay", "Autoplay"),
        Binding("s", "toggle_shuffle", "Shuffle"),
        Binding("r", "cycle_repeat", "Repeat"),
        Binding("v", "cycle_visualizer", "Visualizer Mode"),
        Binding("c", "toggle_cava_external", "External CAVA"),
        Binding("l", "load_url", "Load URL"),
        Binding("u", "load_url", "Load URL"),
        Binding("slash", "focus_filter", "Search/Filter"),
        Binding("escape", "clear_filter", "Clear Filter"),
        Binding("question_mark", "show_credits", "Credits & Help"),
        Binding("f1", "show_credits", "Credits & Help"),
        Binding("q", "quit_app", "Quit"),
    ]

    def __init__(self, initial_url: Optional[str] = None):
        super().__init__()
        self.config = load_config()
        self.initial_url = initial_url or "https://soundcloud.com/discover"
        self.current_url = self.initial_url
        if self.initial_url and "discover" not in self.initial_url:
            add_url_to_history(self.initial_url)

        self.current_page = 1
        self.page_size = 40
        self.track_page: Optional[TrackPage] = None
        self.filtered_tracks: List[dict] = []
        self.selected_track_index: int = 0

        self.cache_manager = SongCacheManager(cache_size=40)
        self.cache_manager.set_on_cached_callback(self._on_track_cached_bg)

        self.player = MpvPlayer(initial_volume=self.config.get("volume", 80))
        self.player.set_on_track_end_callback(self._on_mpv_track_end)

        self.visualizer_engine = VisualizerEngine(num_bars=self.config.get("visualizer_bars", 24))
        self.vis_mode = self.config.get("visualizer", "cava")

        self.autoplay = bool(self.config.get("autoplay", False))
        self.shuffle = bool(self.config.get("shuffle", False))
        self.repeat_mode = str(self.config.get("repeat", "off"))

        self.view_mode = "auto"
        self._term_width = 100
        self._term_height = 30
        self._tick_timer = None

    @property
    def effective_view_mode(self) -> str:
        if self.view_mode == "auto":
            return "tracks" if self._term_width < 85 else "split"
        return self.view_mode

    def _apply_view_layout(self, width: Optional[int] = None) -> None:
        if width is not None:
            self._term_width = width
        mode = self.effective_view_mode

        for c in ["-view-tracks", "-view-visualizer", "-view-split"]:
            self.remove_class(c)
            if self.screen:
                self.screen.remove_class(c)

        cls = f"-view-{mode}"
        self.add_class(cls)
        if self.screen:
            self.screen.add_class(cls)

        try:
            base = self.screen_stack[0] if self.screen_stack else self.screen
            if mode == "tracks":
                table = base.query_one("#tracks-table", DataTable)
                if not table.has_focus:
                    table.focus()
        except Exception:
            pass

    def _update_top_bar(self, width: Optional[int] = None) -> None:
        w = width if width is not None else self._term_width
        mode_str = self.effective_view_mode.capitalize()
        if w < 60:
            txt = f" ♫ SCloud | [Tab] {mode_str}"
        elif w < 85:
            txt = f" ♫ SoundCloud Player | [Tab] View: {mode_str} | [l] URL"
        else:
            txt = f" ♫ SoundCloud Player [Musikcube] | [Tab] View: {mode_str} | [l] Load URL | [?] Help"

        base = self.screen_stack[0] if self.screen_stack else self.screen
        try:
            top_bar = base.query_one("#top-bar", Static)
            top_bar.update(Text(txt, style="bold cyan"))
        except Exception:
            pass

    def action_cycle_view(self) -> None:
        """Cycles between view modes: Tracks -> Visualizer -> Split."""
        modes = ["tracks", "visualizer", "split"]
        curr = self.effective_view_mode
        idx = (modes.index(curr) + 1) % len(modes) if curr in modes else 0
        self.view_mode = modes[idx]
        self._apply_view_layout(self._term_width)
        self._update_top_bar(self._term_width)
        self.notify(f"View mode: {self.view_mode.upper()}", timeout=1.5)

    def on_resize(self, event: events.Resize) -> None:
        """Dynamically handles terminal window resize."""
        w = event.size.width
        h = event.size.height
        self._term_width = w
        self._term_height = h

        breakpoints = [
            ("-narrow", w < 85),
            ("-ultra-narrow", w < 65),
            ("-short", h < 26),
            ("-ultra-short", h < 18),
        ]
        for cls, active in breakpoints:
            self.set_class(active, cls)
            if self.screen:
                self.screen.set_class(active, cls)

        self._apply_view_layout(w)
        self._update_top_bar(w)

    def compose(self) -> ComposeResult:
        with Container(id="app-container"):
            yield Static(Text(" SoundCloud Player [Musikcube] | Press [l] to Load URL | [?] Help", style="bold cyan"), id="top-bar")

            with Horizontal(id="main-split"):
                with Vertical(id="left-panel"):
                    yield Input(placeholder="Type to filter tracks on page... (Press '/' to search, Esc to clear)", id="search-box")
                    yield DataTable(id="tracks-table")
                    yield Static(" Page 1 | Loading...", id="pagination-bar")

                with Vertical(id="right-panel"):
                    yield NowPlayingCard(id="now-playing-card")
                    yield VisualizerWidget(self.visualizer_engine, id="visualizer-card")
                    yield Static(self._build_shortcuts_cheatsheet(), id="info-card")

            with Container(id="transport-container"):
                yield TransportBar(id="transport-bar")

        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#tracks-table", DataTable)
        table.cursor_type = "row"
        table.add_columns(" ", "#", "Title", "Artist", "Time", "⚡")

        self._term_width = self.size.width if self.size.width > 0 else 100
        self._term_height = self.size.height if self.size.height > 0 else 30

        self.set_class(self._term_width < 85, "-narrow")
        self.set_class(self._term_width < 65, "-ultra-narrow")
        self.set_class(self._term_height < 26, "-short")
        self.set_class(self._term_height < 18, "-ultra-short")

        if self.screen:
            self.screen.set_class(self._term_width < 85, "-narrow")
            self.screen.set_class(self._term_width < 65, "-ultra-narrow")
            self.screen.set_class(self._term_height < 26, "-short")
            self.screen.set_class(self._term_height < 18, "-ultra-short")

        self._apply_view_layout(self._term_width)
        self._update_top_bar(self._term_width)

        # Start periodic UI update tick (20 FPS for smooth progress and visualizer)
        self._tick_timer = self.set_interval(0.05, self._on_ui_tick)

        # Load initial URL in background worker
        self.run_worker(self._load_tracks_page_worker(self.current_url, page=1), exclusive=True)

    def _build_shortcuts_cheatsheet(self) -> Panel:
        t = Table.grid(padding=(0, 2))
        t.add_column(width=14)
        t.add_column()

        shortcuts = [
            ("[Space]", "Play / Pause"),
            ("[Enter]", "Play Selected Track"),
            ("[Tab] / [m]", "Switch View (Split/Tracks/Vis)"),
            ("[N] / []]", "Next Track"),
            ("[P] / [[]", "Previous Track"),
            ("[n] / [p]", "Next / Prev Page (40 Tracks)"),
            ("[<] / [>]", "Seek -5s / +5s"),
            ("[-] / [+]", "Volume Down / Up"),
            ("[a]", "Toggle Autoplay"),
            ("[s]", "Toggle Shuffle"),
            ("[r]", "Cycle Repeat (Off/One/All)"),
            ("[v]", "Cycle Visualizer Mode"),
            ("[l]", "Load SoundCloud URL"),
            ("[/]", "Quick Search Filter"),
            ("[?]", "Credits & Help"),
            ("[q]", "Quit Player"),
        ]
        for key, desc in shortcuts:
            t.add_row(Text(key, style="bold cyan"), Text(desc, style="white"))

        return Panel(t, title="[bold yellow]⚡ KEYBOARD SHORTCUTS ⚡[/bold yellow]", border_style="dim cyan")

    async def _load_tracks_page_worker(self, url: str, page: int):
        """Asynchronously fetches a page of 40 tracks, updates table, and starts preloading."""
        base = self.screen_stack[0] if self.screen_stack else self.screen
        try:
            base.query_one("#pagination-bar", Static).update(f" Loading page {page} (max 40 tracks)...")
        except Exception:
            pass

        page_data = await asyncio.to_thread(
            fetch_track_page, url, page, self.page_size
        )
        self.track_page = page_data
        self.current_page = page
        self.current_url = url

        if self.shuffle and self.track_page.tracks:
            random.shuffle(self.track_page.tracks)

        self.filtered_tracks = list(self.track_page.tracks)
        self._populate_table()

        # Kick off background pre-cache for the 40 songs
        self.cache_manager.preload_tracks(self.filtered_tracks, priority_index=self.selected_track_index)

    def _populate_table(self):
        """Fills DataTable with current tracks."""
        base = self.screen_stack[0] if self.screen_stack else self.screen
        try:
            table = base.query_one("#tracks-table", DataTable)
        except Exception:
            return

        table.clear()

        start_num = (self.current_page - 1) * self.page_size + 1
        active_track = self.player.get_state().current_track

        table_w = table.size.width if table.size.width > 0 else self._term_width
        if table_w < 45:
            max_title = 16
            max_artist = 8
        elif table_w < 65:
            max_title = 24
            max_artist = 14
        elif table_w < 90:
            max_title = 38
            max_artist = 20
        else:
            max_title = 50
            max_artist = 28

        for idx, track in enumerate(self.filtered_tracks):
            is_active = (
                active_track and (
                    str(track.get("id") or "") == str(active_track.get("id") or "")
                    or track.get("url") == active_track.get("url")
                )
            )
            status_icon = "▶" if is_active else " "
            has_cache = "⚡" if self.cache_manager.has_stream_url(track) else "·"

            title = track.get("title") or "Unknown Title"
            artist = track.get("uploader") or track.get("artist") or "N/A"
            dur = format_duration(track.get("duration"))

            table.add_row(
                status_icon,
                str(start_num + idx),
                title[:max_title],
                artist[:max_artist],
                dur,
                has_cache,
                key=str(idx)
            )

        total_txt = f" of {self.track_page.total_tracks}" if self.track_page and self.track_page.total_tracks else ""
        source_title = self.track_page.playlist_title if self.track_page and self.track_page.playlist_title else self.current_url

        try:
            pagination = base.query_one("#pagination-bar", Static)
            if self._term_width < 70:
                p_text = f" P.{self.current_page}{total_txt} ({len(self.filtered_tracks)}) | [p]/[n]"
            elif self._term_width < 95:
                p_text = f" Page {self.current_page}{total_txt} ({len(self.filtered_tracks)} tracks) | [p] Prev | [n] Next"
            else:
                p_text = f" Page {self.current_page}{total_txt} ({len(self.filtered_tracks)} tracks) | [p] Prev Page | [n] Next Page | Source: {source_title[:28]}"
            pagination.update(Text(p_text))
        except Exception:
            pass

    def _on_track_cached_bg(self, key: str, stream_url: str):
        """Called when a stream URL has been pre-cached in background."""
        self.call_from_thread(self._refresh_table_cache_icons)

    def _refresh_table_cache_icons(self):
        """Updates table cache icons when background preload resolves URLs."""
        base = self.screen_stack[0] if self.screen_stack else self.screen
        try:
            table = base.query_one("#tracks-table", DataTable)
            for idx, track in enumerate(self.filtered_tracks):
                if self.cache_manager.has_stream_url(track):
                    try:
                        table.update_cell_at((idx, 5), "⚡")
                    except Exception:
                        pass
        except Exception:
            pass

    def _on_ui_tick(self):
        """Periodic UI refresh callback for live visualizer and transport bar."""
        state = self.player.get_state()
        base = self.screen_stack[0] if self.screen_stack else self.screen

        # Update Visualizer
        try:
            vis_widget = base.query_one("#visualizer-card", VisualizerWidget)
            vis_widget.update_state(state.is_playing, state.is_paused, self.vis_mode)
        except Exception:
            pass

        # Update Now Playing Card
        try:
            np_card = base.query_one("#now-playing-card", NowPlayingCard)
            np_card.update_track(state.current_track, state.is_playing, state.is_paused)
        except Exception:
            pass

        # Update Transport Bar
        try:
            curr = state.current_track or {}
            cached_count = self.cache_manager.cached_count(self.filtered_tracks)
            base.query_one("#transport-bar", TransportBar).update_transport(
                title=curr.get("title", ""),
                artist=curr.get("uploader", ""),
                time_pos=state.current_time_pos,
                duration=state.duration,
                volume=state.volume,
                is_playing=state.is_playing,
                is_paused=state.is_paused,
                autoplay=self.autoplay,
                shuffle=self.shuffle,
                repeat=self.repeat_mode,
                cached_count=cached_count,
                total_in_page=len(self.filtered_tracks)
            )
        except Exception:
            pass

    def _on_mpv_track_end(self):
        """Callback when MPV finishes a track naturally."""
        if self.repeat_mode == "one":
            self.call_from_thread(self.action_play_selected)
            return

        if self.autoplay or self.repeat_mode == "all":
            self.call_from_thread(self._advance_to_next_track)

    def _advance_to_next_track(self):
        """Advances playback to next track in queue."""
        if not self.filtered_tracks:
            return

        next_index = self.selected_track_index + 1
        if next_index < len(self.filtered_tracks):
            self.selected_track_index = next_index
            self._play_track_at_index(next_index)
        elif self.repeat_mode == "all":
            self.selected_track_index = 0
            self._play_track_at_index(0)
        elif self.track_page and self.track_page.has_next:
            # Advance to next page of 30 tracks
            self.action_next_page()
            self.selected_track_index = 0
            self._play_track_at_index(0)

    def _play_track_at_index(self, index: int):
        """Plays track at specific index using cached stream URL."""
        if not self.filtered_tracks or index >= len(self.filtered_tracks):
            return

        track = self.filtered_tracks[index]
        self.selected_track_index = index

        # Highlight in table
        base = self.screen_stack[0] if self.screen_stack else self.screen
        try:
            table = base.query_one("#tracks-table", DataTable)
            table.move_cursor(row=index)
        except Exception:
            pass

        # Check pre-cache
        stream_url = self.cache_manager.get_stream_url(track, fallback_resolve=False)
        if stream_url:
            self.player.play(stream_url, track)
            self._populate_table()
        else:
            # Resolve synchronously in background thread
            def do_resolve_and_play():
                url = self.cache_manager.get_stream_url(track, fallback_resolve=True)
                if url:
                    self.player.play(url, track)
                    self.call_from_thread(self._populate_table)

            threading.Thread(target=do_resolve_and_play, daemon=True).start()

    def action_toggle_play(self) -> None:
        state = self.player.get_state()
        if not state.is_playing:
            self.action_play_selected()
        else:
            self.player.toggle_pause()

    def action_play_selected(self) -> None:
        base = self.screen_stack[0] if self.screen_stack else self.screen
        try:
            table = base.query_one("#tracks-table", DataTable)
            if table.cursor_row is not None and table.cursor_row < len(self.filtered_tracks):
                self.selected_track_index = table.cursor_row
                self._play_track_at_index(self.selected_track_index)
        except Exception:
            pass

    def action_next_track(self) -> None:
        """Skips immediately to the next track."""
        if not self.filtered_tracks:
            return
        next_index = self.selected_track_index + 1
        if next_index < len(self.filtered_tracks):
            self.selected_track_index = next_index
            self._play_track_at_index(next_index)
        elif self.track_page and self.track_page.has_next:
            self.action_next_page()
            self.selected_track_index = 0
            self._play_track_at_index(0)
        elif self.repeat_mode == "all":
            self.selected_track_index = 0
            self._play_track_at_index(0)

    def action_prev_track(self) -> None:
        """Returns to previous track (or restarts current track if >3s elapsed)."""
        if not self.filtered_tracks:
            return
        state = self.player.get_state()
        if state.current_time_pos > 3.0:
            self.player.seek_percent(0.0)
            return

        if self.selected_track_index > 0:
            self.selected_track_index -= 1
            self._play_track_at_index(self.selected_track_index)
        elif self.current_page > 1:
            self.action_prev_page()

    def action_next_page(self) -> None:
        if self.track_page and self.track_page.has_next:
            next_p = self.current_page + 1
            self.run_worker(self._load_tracks_page_worker(self.current_url, page=next_p), exclusive=True)

    def action_prev_page(self) -> None:
        if self.current_page > 1:
            prev_p = self.current_page - 1
            self.run_worker(self._load_tracks_page_worker(self.current_url, page=prev_p), exclusive=True)

    def action_seek_forward(self) -> None:
        self.player.seek(5.0)

    def action_seek_backward(self) -> None:
        self.player.seek(-5.0)

    def action_volume_up(self) -> None:
        self.player.add_volume(5.0)
        self.config["volume"] = int(self.player.get_state().volume)
        save_config(self.config)

    def action_volume_down(self) -> None:
        self.player.add_volume(-5.0)
        self.config["volume"] = int(self.player.get_state().volume)
        save_config(self.config)

    def action_toggle_autoplay(self) -> None:
        self.autoplay = not self.autoplay
        self.config["autoplay"] = self.autoplay
        save_config(self.config)

    def action_toggle_shuffle(self) -> None:
        self.shuffle = not self.shuffle
        self.config["shuffle"] = self.shuffle
        save_config(self.config)
        if self.shuffle and self.filtered_tracks:
            random.shuffle(self.filtered_tracks)
            self._populate_table()

    def action_cycle_repeat(self) -> None:
        modes = ["off", "one", "all"]
        idx = (modes.index(self.repeat_mode) + 1) % len(modes) if self.repeat_mode in modes else 0
        self.repeat_mode = modes[idx]
        self.config["repeat"] = self.repeat_mode
        save_config(self.config)

    def action_cycle_visualizer(self) -> None:
        modes = ["cava", "spectrum", "off"]
        idx = (modes.index(self.vis_mode) + 1) % len(modes) if self.vis_mode in modes else 0
        self.vis_mode = modes[idx]
        self.config["visualizer"] = self.vis_mode
        save_config(self.config)

    def action_toggle_cava_external(self) -> None:
        """Launches external CAVA window in a new terminal if available."""
        cava_path = shutil.which("cava") or os.path.expanduser("~/.local/bin/cava")
        if not os.path.isfile(cava_path):
            self.notify("CAVA binary not found. Install cava for external visualizer.", severity="warning")
            return

        terminals = ["x-terminal-emulator", "kitty", "alacritty", "gnome-terminal", "konsole", "xterm"]
        for term in terminals:
            term_bin = shutil.which(term)
            if term_bin:
                try:
                    subprocess.Popen([term_bin, "-e", cava_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    self.notify(f"Spawned external CAVA window via {term}.")
                    return
                except Exception:
                    pass
        self.notify("Could not find a terminal emulator to launch external CAVA.", severity="error")

    def action_load_url(self) -> None:
        """Opens interactive modal dialog to load a new SoundCloud URL."""
        def handle_url_result(url: Optional[str]):
            if url:
                add_url_to_history(url)
                self.run_worker(self._load_tracks_page_worker(url, page=1), exclusive=True)

        self.push_screen(UrlModal(), handle_url_result)

    def action_focus_filter(self) -> None:
        base = self.screen_stack[0] if self.screen_stack else self.screen
        try:
            if self.effective_view_mode == "visualizer":
                self.view_mode = "tracks"
                self._apply_view_layout()
            base.query_one("#search-box", Input).focus()
        except Exception:
            pass

    def action_clear_filter(self) -> None:
        base = self.screen_stack[0] if self.screen_stack else self.screen
        try:
            search_box = base.query_one("#search-box", Input)
            search_box.value = ""
            if self.track_page:
                self.filtered_tracks = list(self.track_page.tracks)
                self._populate_table()
            base.query_one("#tracks-table", DataTable).focus()
        except Exception:
            pass

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "search-box" and self.track_page:
            query = event.value.strip().lower()
            if not query:
                self.filtered_tracks = list(self.track_page.tracks)
            else:
                self.filtered_tracks = [
                    t for t in self.track_page.tracks
                    if query in (t.get("title") or "").lower() or query in (t.get("uploader") or "").lower()
                ]
            self._populate_table()

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        try:
            row_idx = int(event.row_key.value)
            self.selected_track_index = row_idx
            self._play_track_at_index(row_idx)
        except Exception:
            pass

    def action_show_credits(self) -> None:
        """Opens modal displaying open source credits and acknowledgements."""
        self.push_screen(CreditsModal())

    def action_quit_app(self) -> None:
        self.player.shutdown()
        self.visualizer_engine.stop()
        self.exit(0)


def run_tui(initial_url: Optional[str] = None):
    """Entry point to launch the Musikcube-style TUI."""
    app = ScloudPlayerApp(initial_url=initial_url)
    app.run()
