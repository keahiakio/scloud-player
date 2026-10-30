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
from scloud_player.config import load_config, save_config
from scloud_player.player import MpvPlayer
from scloud_player.visualizer import VisualizerEngine


class UrlModal(ModalScreen[Optional[str]]):
    """Modal dialog for entering a new SoundCloud URL."""

    DEFAULT_CSS = """
    UrlModal {
        align: center middle;
        background: rgba(0, 0, 0, 0.7);
    }

    #url-dialog {
        padding: 1 2;
        width: 75;
        height: auto;
        border: thick $primary;
        background: $surface;
    }

    #url-buttons {
        margin-top: 1;
        align: right middle;
    }

    Button {
        margin-left: 1;
    }
    """

    def compose(self) -> ComposeResult:
        with Vertical(id="url-dialog"):
            yield Label("[bold cyan]Enter SoundCloud URL or Playlist:[/bold cyan]")
            yield Input(
                placeholder="https://soundcloud.com/artist or track/set URL",
                id="url-input"
            )
            with Horizontal(id="url-buttons"):
                yield Button("Load", variant="primary", id="btn-load")
                yield Button("Cancel", variant="default", id="btn-cancel")

    def on_mount(self) -> None:
        self.query_one("#url-input", Input).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-load":
            val = self.query_one("#url-input", Input).value.strip()
            self.dismiss(val if val else None)
        else:
            self.dismiss(None)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        val = event.value.strip()
        self.dismiss(val if val else None)


class VisualizerWidget(Static):
    """Widget displaying the live CAVA spectrum analyzer with color gradients."""

    def __init__(self, visualizer_engine: VisualizerEngine, **kwargs):
        super().__init__(**kwargs)
        self.engine = visualizer_engine
        self.vis_mode = "cava"
        self.is_playing = False
        self.is_paused = False

    def update_state(self, is_playing: bool, is_paused: bool, mode: str):
        self.is_playing = is_playing
        self.is_paused = is_paused
        self.vis_mode = mode
        self.refresh_bars()

    def refresh_bars(self):
        values = self.engine.get_bar_values(
            is_playing=self.is_playing,
            is_paused=self.is_paused,
            mode=self.vis_mode
        )
        # Render 7 rows of frequency bars
        lines = self.engine.render_grid(values, height=6, bar_width=1, bar_spacing=1)

        header = Text(" ▃▅▇ LIVE CAVA VISUALIZER ▇▅▃", style="bold cyan")
        if self.vis_mode == "cava":
            status = " [LIVE CAVA]" if self.engine.cava.is_active() else " [SPECTRUM]"
        elif self.vis_mode == "off":
            status = " [OFF]"
        else:
            status = f" [{self.vis_mode.upper()}]"
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

    def update_track(self, track: Optional[dict], is_playing: bool, is_paused: bool):
        if not track:
            self.update(Panel(
                Text("\nNo track playing.\nSelect a track to start playback.\n", justify="center", style="dim white"),
                title="[bold magenta]♫ NOW PLAYING ♫[/bold magenta]",
                border_style="dim blue"
            ))
            return

        title = track.get("title") or "Unknown Title"
        artist = track.get("uploader") or track.get("artist") or "Unknown Artist"
        duration = format_duration(track.get("duration"))
        status_text = "⏸ PAUSED" if is_paused else ("▶ PLAYING" if is_playing else "⏹ STOPPED")
        status_style = "bold yellow" if is_paused else ("bold green" if is_playing else "dim")

        t = Table.grid(padding=(0, 1))
        t.add_column(width=10)
        t.add_column()

        t.add_row(Text("Track:", style="bold cyan"), Text(title[:38], style="bold white"))
        t.add_row(Text("Artist:", style="bold cyan"), Text(artist[:38], style="bold white"))
        t.add_row(Text("Duration:", style="bold cyan"), Text(duration, style="bold white"))
        t.add_row(Text("Status:", style="bold cyan"), Text(status_text, style=status_style))

        genre = track.get("genre")
        if genre:
            t.add_row(Text("Genre:", style="bold cyan"), Text(str(genre)[:38], style="bold white"))

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
        total_in_page: int
    ):
        elapsed_str = format_duration(time_pos)
        total_str = format_duration(duration)

        # Build seek bar
        bar_len = 24
        if duration > 0:
            pct = min(max(time_pos / duration, 0.0), 1.0)
            filled = int(pct * bar_len)
        else:
            pct = 0.0
            filled = 0

        seek_line = "━" * filled + ("●" if filled < bar_len else "") + "─" * max(0, bar_len - filled - 1)

        icon = "⏸" if is_paused else ("▶" if is_playing else "⏹")
        track_label = f"{title[:24]} - {artist[:18]}" if title else "Ready"

        vol_len = 6
        vol_filled = int((volume / 100.0) * vol_len)
        vol_bar = "=" * vol_filled + "-" * (vol_len - vol_filled)

        bar_text = Text()
        bar_text.append(f" {icon} ", style="bold green" if is_playing and not is_paused else "bold yellow")
        bar_text.append(f"{track_label:<44} ", style="bold white")
        bar_text.append(f"{elapsed_str} ", style="bold cyan")
        bar_text.append(f"[{seek_line}]", style="bright_magenta")
        bar_text.append(f" {total_str}  ", style="bold cyan")
        bar_text.append(f"Vol:{int(volume):>3}% [{vol_bar}]  ", style="bright_blue")

        # Badges
        bar_text.append("[AUTO]", style="bold green" if autoplay else "dim")
        bar_text.append(" ")
        bar_text.append("[SHUF]", style="bold green" if shuffle else "dim")
        bar_text.append(" ")
        bar_text.append(f"[REP:{repeat.upper()}]", style="bold green" if repeat != "off" else "dim")
        bar_text.append(" ")
        bar_text.append(f"[CACHE:{cached_count}/{total_in_page} ⚡]", style="bold green" if cached_count > 0 else "dim")

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
        width: 65%;
        height: 100%;
        border-right: solid #2c3549;
        padding: 0 1;
    }

    #right-panel {
        width: 35%;
        height: 100%;
        padding: 0 1;
    }

    #search-box {
        height: 3;
        margin-bottom: 1;
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

    #visualizer-card {
        height: 9;
        border: solid #22293a;
        margin-top: 1;
        background: #131722;
    }

    #now-playing-card {
        height: 7;
        margin-top: 1;
    }

    #info-card {
        height: 1fr;
        margin-top: 1;
        border: solid #22293a;
        background: #131722;
        padding: 1;
    }

    #transport-container {
        dock: bottom;
        height: 2;
        background: #181d2a;
        border-top: solid #4facfe;
        padding: 0 1;
    }
    """

    BINDINGS = [
        Binding("space", "toggle_play", "Play/Pause", priority=True),
        Binding("enter", "play_selected", "Play Selected"),
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
        Binding("q", "quit_app", "Quit"),
    ]

    def __init__(self, initial_url: Optional[str] = None):
        super().__init__()
        self.config = load_config()
        self.initial_url = initial_url or "https://soundcloud.com/discover"
        self.current_url = self.initial_url

        self.current_page = 1
        self.page_size = 30
        self.track_page: Optional[TrackPage] = None
        self.filtered_tracks: List[dict] = []
        self.selected_track_index: int = 0

        self.cache_manager = SongCacheManager(cache_size=30)
        self.cache_manager.set_on_cached_callback(self._on_track_cached_bg)

        self.player = MpvPlayer(initial_volume=self.config.get("volume", 80))
        self.player.set_on_track_end_callback(self._on_mpv_track_end)

        self.visualizer_engine = VisualizerEngine(num_bars=self.config.get("visualizer_bars", 24))
        self.vis_mode = self.config.get("visualizer", "cava")

        self.autoplay = bool(self.config.get("autoplay", False))
        self.shuffle = bool(self.config.get("shuffle", False))
        self.repeat_mode = str(self.config.get("repeat", "off"))

        self._tick_timer = None

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
            ("[n] / [p]", "Next / Prev Page (30 Tracks)"),
            ("[<] / [>]", "Seek -5s / +5s"),
            ("[-] / [+]", "Volume Down / Up"),
            ("[a]", "Toggle Autoplay"),
            ("[s]", "Toggle Shuffle"),
            ("[r]", "Cycle Repeat (Off/One/All)"),
            ("[v]", "Cycle Visualizer Mode"),
            ("[l]", "Load SoundCloud URL"),
            ("[/]", "Quick Search Filter"),
            ("[q]", "Quit Player"),
        ]
        for key, desc in shortcuts:
            t.add_row(Text(key, style="bold cyan"), Text(desc, style="white"))

        return Panel(t, title="[bold yellow]⚡ KEYBOARD SHORTCUTS ⚡[/bold yellow]", border_style="dim cyan")

    async def _load_tracks_page_worker(self, url: str, page: int):
        """Asynchronously fetches a page of 30 tracks, updates table, and starts preloading."""
        self.query_one("#pagination-bar", Static).update(f" Loading page {page} (max 30 tracks)...")

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

        # Kick off background pre-cache for the 30 songs
        self.cache_manager.preload_tracks(self.filtered_tracks, priority_index=self.selected_track_index)

    def _populate_table(self):
        """Fills DataTable with current tracks."""
        table = self.query_one("#tracks-table", DataTable)
        table.clear()

        start_num = (self.current_page - 1) * self.page_size + 1
        active_track = self.player.get_state().current_track

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
                title[:45],
                artist[:25],
                dur,
                has_cache,
                key=str(idx)
            )

        total_txt = f" of {self.track_page.total_tracks}" if self.track_page and self.track_page.total_tracks else ""
        source_title = self.track_page.playlist_title if self.track_page and self.track_page.playlist_title else self.current_url
        self.query_one("#pagination-bar", Static).update(
            Text(f" Page {self.current_page}{total_txt} ({len(self.filtered_tracks)} tracks) | [p] Prev Page | [n] Next Page | Source: {source_title[:35]}")
        )

    def _on_track_cached_bg(self, key: str, stream_url: str):
        """Called when a stream URL has been pre-cached in background."""
        self.call_from_thread(self._refresh_table_cache_icons)

    def _refresh_table_cache_icons(self):
        """Updates table cache icons when background preload resolves URLs."""
        table = self.query_one("#tracks-table", DataTable)
        for idx, track in enumerate(self.filtered_tracks):
            if self.cache_manager.has_stream_url(track):
                try:
                    table.update_cell_at((idx, 5), "⚡")
                except Exception:
                    pass

    def _on_ui_tick(self):
        """Periodic UI refresh callback for live visualizer and transport bar."""
        state = self.player.get_state()

        # Update Visualizer
        vis_widget = self.query_one("#visualizer-card", VisualizerWidget)
        vis_widget.update_state(state.is_playing, state.is_paused, self.vis_mode)

        # Update Now Playing Card
        np_card = self.query_one("#now-playing-card", NowPlayingCard)
        np_card.update_track(state.current_track, state.is_playing, state.is_paused)

        # Update Transport Bar
        curr = state.current_track or {}
        cached_count = self.cache_manager.cached_count(self.filtered_tracks)
        self.query_one("#transport-bar", TransportBar).update_transport(
            title=curr.get("title", ""),
            artist=curr.get("uploader", ""),
            time_pos=state.time_pos,
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
        table = self.query_one("#tracks-table", DataTable)
        try:
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
        table = self.query_one("#tracks-table", DataTable)
        if table.cursor_row is not None and table.cursor_row < len(self.filtered_tracks):
            self.selected_track_index = table.cursor_row
            self._play_track_at_index(self.selected_track_index)

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
                self.run_worker(self._load_tracks_page_worker(url, page=1), exclusive=True)

        self.push_screen(UrlModal(), handle_url_result)

    def action_focus_filter(self) -> None:
        self.query_one("#search-box", Input).focus()

    def action_clear_filter(self) -> None:
        search_box = self.query_one("#search-box", Input)
        search_box.value = ""
        if self.track_page:
            self.filtered_tracks = list(self.track_page.tracks)
            self._populate_table()
        self.query_one("#tracks-table", DataTable).focus()

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

    def action_quit_app(self) -> None:
        self.player.shutdown()
        self.visualizer_engine.stop()
        self.exit(0)


def run_tui(initial_url: Optional[str] = None):
    """Entry point to launch the Musikcube-style TUI."""
    app = ScloudPlayerApp(initial_url=initial_url)
    app.run()
