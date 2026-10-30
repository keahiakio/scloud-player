# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2026 Kiwi Akio

"""
Classic command-line interface for scloud-player.
Provides simple paginated terminal menu navigation, readline history,
and visualizer playback.
"""

import math
import os
import random
import readline
import re
import select
import subprocess
import sys
import time
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from scloud_player.api import (
    enrich_tracks_metadata,
    fetch_track_page,
    format_duration,
    get_full_track_info,
    get_stream_url,
    get_track_data,
)
from scloud_player.cache import SongCacheManager
from scloud_player.config import (
    CONFIG_FILE,
    HISTORY_FILE,
    load_config,
    save_config,
)
from scloud_player.player import get_visualizer_args

console = Console()


def setup_readline():
    """Sets up readline for input history."""
    if os.path.exists(HISTORY_FILE):
        try:
            readline.read_history_file(HISTORY_FILE)
        except Exception:
            pass

    readline.set_history_length(1000)
    import atexit
    atexit.register(readline.write_history_file, HISTORY_FILE)


def clear_terminal():
    """Clears the terminal screen."""
    console.clear()


def ansi_to_readline(ansi_str):
    """Wraps ANSI escape sequences in \001 and \002 so readline calculates prompt length correctly."""
    return re.sub(r"(\x1b\[[0-9;]*m)", r"\001\1\002", ansi_str)


def get_user_input(prompt_text):
    """Gets user input with readline handling for rich-formatted prompts."""
    with console.capture() as capture:
        console.print(prompt_text, end=": ")
    ansi_prompt = capture.get()
    readline_prompt = ansi_to_readline(ansi_prompt)

    try:
        return input(readline_prompt).strip()
    except EOFError:
        return "q"
    except KeyboardInterrupt:
        raise


def display_tracks(tracks, page_number, page_size, total_tracks, cache_mgr=None):
    """Displays a list of tracks in a table, paginated."""
    if not tracks:
        console.print("[bold yellow]No tracks found.[/bold yellow]")
        return

    enrich_tracks_metadata(tracks)
    total_pages = max(1, math.ceil(total_tracks / page_size)) if total_tracks else page_number

    table = Table(title=f"Select a Track (Page {page_number}/{total_pages})", show_lines=True)
    table.add_column("Index", style="cyan", width=6)
    table.add_column("Title", style="magenta")
    table.add_column("Uploader", style="green")
    table.add_column("Duration", style="blue", width=10)
    table.add_column("Cache", style="yellow", width=6)

    start_num = (page_number - 1) * page_size + 1
    for i, track in enumerate(tracks):
        is_cached = "⚡" if (cache_mgr and cache_mgr.has_stream_url(track)) else "·"
        table.add_row(
            str(start_num + i),
            track.get("title") or "N/A",
            track.get("uploader") or "N/A",
            format_duration(track.get("duration")),
            is_cached
        )

    console.print(table)


def play_track(track_info, player="mpv", config=None, cache_mgr=None):
    """
    Plays a stream URL with the selected player.
    Fetches full track info and stream URL (using cache when available).
    """
    enrich_tracks_metadata([track_info])
    target_url = track_info.get("webpage_url") or track_info.get("url")

    # Use cache if available
    stream_url = None
    if cache_mgr:
        stream_url = cache_mgr.get_stream_url(track_info)
    if not stream_url and target_url:
        stream_url = get_stream_url(target_url)

    if not stream_url:
        console.print(f"[bold red]Could not resolve stream URL for {track_info.get('title', 'track')}.[/bold red]")
        return -1

    title = track_info.get("title", "Unknown Title")
    uploader = track_info.get("uploader", "Unknown Uploader")
    duration_str = format_duration(track_info.get("duration"))

    card_table = Table.grid(padding=(0, 2))
    card_table.add_column(style="bold cyan", justify="right")
    card_table.add_column(style="bold white")
    card_table.add_row("Track:", title)
    card_table.add_row("Artist:", uploader)
    card_table.add_row("Duration:", duration_str)

    panel_content = Table.grid(padding=1)
    panel_content.add_row(card_table)
    panel_content.add_row("[dim]Controls: [Space] Pause  |  [9/0] Volume  |  [q] Stop  |  [a] Toggle Autoplay[/dim]")

    panel = Panel(
        panel_content,
        title="[bold magenta] ▃▅▇█ NOW PLAYING █▇▅▃ [/bold magenta]",
        border_style="bright_blue",
        expand=False,
    )
    console.print("")
    console.print(panel)
    console.print(f"[dim]Link:[/dim] [link={target_url}]{target_url}[/link]\n")

    input_conf = os.path.expanduser("~/.cache/scloud-player-input.conf")
    os.makedirs(os.path.dirname(input_conf), exist_ok=True)
    with open(input_conf, "w") as f:
        f.write("a quit 4\n")

    try:
        if player.lower() == "vlc":
            subprocess.run(["cvlc", "--play-and-exit", stream_url], check=True)
        else:
            vis_mode = config.get("visualizer", "spectrum") if config else "spectrum"
            is_fullscreen = config.get("fullscreen", True) if config else True
            vis_args = get_visualizer_args(vis_mode, title, uploader, fullscreen=is_fullscreen)

            cmd = ["mpv", f"--input-conf={input_conf}"] + vis_args + [stream_url]
            result = subprocess.run(cmd, check=False)
            if result.returncode == 4:
                console.print("[bold cyan]Autoplay disabled via 'a' key.[/bold cyan]")
                return 4
            elif result.returncode != 0:
                return -1
        return 0
    except subprocess.CalledProcessError as e:
        console.print(f"[bold red]{player} playback interrupted or failed: {e}[/bold red]")
        return -1
    except FileNotFoundError:
        console.print(f"[bold red]Error: '{player}' is not installed or not in your PATH.[/bold red]")
        sys.exit(1)


def intermission(next_track_title):
    """Shows a brief countdown between autoplay tracks, allowing the user to cancel."""
    console.print(f"\n[bold yellow]Up Next: {next_track_title}[/bold yellow]")
    for i in range(3, 0, -1):
        console.print(f"[bold yellow]Starting in {i}s... (Press 'q' to stop autoplay, any other key to play now)[/bold yellow]\r", end="")
        rlist, _, _ = select.select([sys.stdin], [], [], 1)
        if rlist:
            char = sys.stdin.read(1).lower()
            if char == "q":
                console.print("\n[bold cyan]Autoplay stopped.[/bold cyan]")
                return False
            break
    console.print("")
    return True


def run_cli(initial_url=None):
    """Main classic CLI interactive loop."""
    setup_readline()
    config = load_config()
    config["autoplay"] = False
    cache_mgr = SongCacheManager(cache_size=30)

    try:
        while True:
            if initial_url:
                soundcloud_url = initial_url
                initial_url = None
            else:
                soundcloud_url = get_user_input("[bold cyan]Please enter a SoundCloud URL[/bold cyan]")
                if soundcloud_url.lower() == "q":
                    break

            if not soundcloud_url:
                continue

            page_size = 30
            current_page = 1
            current_track_index = -1

            while True:
                # Load up to 30 tracks for current page
                page_data = fetch_track_page(soundcloud_url, page=current_page, page_size=page_size)
                tracks = page_data.tracks
                if not tracks:
                    console.print("[bold red]No tracks were loaded.[/bold red]")
                    break

                # Kick off preload for the 30 songs
                cache_mgr.preload_tracks(tracks)

                if config.get("shuffle", False):
                    random.shuffle(tracks)

                total_tracks = page_data.total_tracks or len(tracks)

                clear_terminal()
                display_tracks(tracks, current_page, page_size, total_tracks, cache_mgr=cache_mgr)

                if current_track_index != -1 and current_track_index < len(tracks):
                    selected = tracks[current_track_index]
                    status = play_track(selected, player=config.get("player", "mpv"), config=config, cache_mgr=cache_mgr)
                    if status == 4:
                        config["autoplay"] = False
                        current_track_index = -1
                        time.sleep(1)
                        continue
                    elif status == 0:
                        current_track_index += 1
                        if current_track_index >= len(tracks):
                            if page_data.has_next:
                                current_page += 1
                                current_track_index = 0
                            else:
                                console.print("[bold yellow]End of tracks.[/bold yellow]")
                                current_track_index = -1
                                time.sleep(1)

                        if config.get("autoplay", False) and current_track_index != -1:
                            next_title = tracks[current_track_index].get("title") or "Unknown"
                            if not intermission(next_title):
                                config["autoplay"] = False
                                current_track_index = -1
                                time.sleep(1)
                        continue
                    else:
                        current_track_index = -1
                        time.sleep(1)

                prompt_text = "[bold yellow]Enter track #, 'n' next page, 'p' prev page, 's' autoplay, 'sh' shuffle, 'v' vis, 'q' back[/bold yellow]"
                choice_str = get_user_input(prompt_text).lower()

                if choice_str == "q":
                    break
                elif choice_str == "n":
                    if page_data.has_next:
                        current_page += 1
                        current_track_index = -1
                    else:
                        console.print("[bold yellow]Already on the last page.[/bold yellow]")
                        time.sleep(1)
                elif choice_str == "p":
                    if current_page > 1:
                        current_page -= 1
                        current_track_index = -1
                    else:
                        console.print("[bold yellow]Already on the first page.[/bold yellow]")
                        time.sleep(1)
                elif choice_str == "s":
                    current_track_index = 0
                    config["autoplay"] = True
                elif choice_str == "sh":
                    config["shuffle"] = not config.get("shuffle", False)
                    save_config(config)
                    console.print(f"[bold cyan]Shuffle {'enabled' if config['shuffle'] else 'disabled'}.[/bold cyan]")
                    time.sleep(1)
                elif choice_str in ("v", "vis"):
                    modes = ["cava", "spectrum", "waves", "vectorscope", "caca", "off"]
                    curr = config.get("visualizer", "cava")
                    next_i = (modes.index(curr) + 1) % len(modes) if curr in modes else 0
                    config["visualizer"] = modes[next_i]
                    save_config(config)
                    console.print(f"[bold cyan]Visualizer: [bold yellow]{config['visualizer']}[/bold yellow][/bold cyan]")
                    time.sleep(1)
                else:
                    try:
                        choice = int(choice_str)
                        start_num = (current_page - 1) * page_size + 1
                        local_idx = choice - start_num
                        if 0 <= local_idx < len(tracks):
                            play_track(tracks[local_idx], player=config.get("player", "mpv"), config=config, cache_mgr=cache_mgr)
                        else:
                            console.print("[bold red]Invalid track number.[/bold red]")
                            time.sleep(1)
                    except ValueError:
                        console.print("[bold red]Invalid input.[/bold red]")
                        time.sleep(1)

    except KeyboardInterrupt:
        console.print("\n[bold red]Exiting scloud-player...[/bold red]")
        sys.exit(0)
