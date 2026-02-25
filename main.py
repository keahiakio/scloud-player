#!/home/keahiakio/scloud-player/venv/bin/python
import subprocess
import json
import sys
import math
import os
import time
import random
import readline
from rich.console import Console
from rich.table import Table
from rich.prompt import Prompt

console = Console() # Initialize console globally

CONFIG_FILE = os.path.expanduser("~/.scloud-player-config.json")
HISTORY_FILE = os.path.expanduser("~/.scloud-player-history")

DEFAULT_CONFIG = {
    "player": "mpv",
    "autoplay": False,
    "shuffle": False,
    "page_size": 15
}

def load_config():
    """Loads configuration from file or returns default."""
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r') as f:
                config = json.load(f)
                # Ensure all default keys exist
                for k, v in DEFAULT_CONFIG.items():
                    if k not in config:
                        config[k] = v
                return config
        except Exception as e:
            console.print(f"[bold red]Error loading config: {e}. Using defaults.[/bold red]")
    return DEFAULT_CONFIG.copy()

def save_config(config):
    """Saves configuration to file."""
    try:
        with open(CONFIG_FILE, 'w') as f:
            json.dump(config, f, indent=4)
    except Exception as e:
        console.print(f"[bold red]Error saving config: {e}[/bold red]")

def setup_readline():
    """Sets up readline for input history."""
    if os.path.exists(HISTORY_FILE):
        try:
            readline.read_history_file(HISTORY_FILE)
        except Exception:
            pass
    
    # Set history length
    readline.set_history_length(1000)
    # Standard Emacs-like bindings (Up/Down for history) are default in most readline builds
    import atexit
    atexit.register(readline.write_history_file, HISTORY_FILE)

def clear_terminal():
    """Clears the terminal screen."""
    console.clear()

def get_user_input(prompt_text):
    """Gets user input using console.print and input() to avoid readline/rich conflicts."""
    console.print(prompt_text, end=": ")
    try:
        return input().strip()
    except EOFError:
        return "q"
    except KeyboardInterrupt:
        raise

def format_duration(seconds):
    """Formats duration in seconds to MM:SS or HH:MM:SS."""
    if seconds is None:
        return "N/A"
    seconds = int(seconds)
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    seconds = seconds % 60
    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    return f"{minutes:02d}:{seconds:02d}"

def get_track_data(url):
    """
    Fetches basic track data from a SoundCloud URL using yt-dlp.
    Uses --flat-playlist for speed, which might not include all details like uploader.
    """
    try:
        command = ["/home/keahiakio/scloud-player/venv/bin/yt-dlp", "--flat-playlist", "-j", "--print-json", url]
        result = subprocess.run(command, capture_output=True, text=True, check=True)
        
        tracks = []
        for line in result.stdout.strip().split('\n'):
            if line:
                track_info = json.loads(line)
                tracks.append(track_info)
        return tracks
    except subprocess.CalledProcessError as e:
        console.print(f"[bold red]Error fetching tracks: {e.stderr}[/bold red]")
        return None
    except FileNotFoundError:
        console.print("[bold red]Error: 'yt-dlp' is not installed or not in your PATH.[/bold red]")
        console.print("Please install it to use this script (e.g., 'pip install yt-dlp').")
        sys.exit(1)

def get_full_track_info(track_url):
    """
    Fetches full metadata for a single track using yt-dlp.
    """
    try:
        command = ["/home/keahiakio/scloud-player/venv/bin/yt-dlp", "-j", "--print-json", track_url]
        result = subprocess.run(command, capture_output=True, text=True, check=True)
        return json.loads(result.stdout.strip())
    except subprocess.CalledProcessError as e:
        console.print(f"[bold red]Error fetching full track info for {track_url}: {e.stderr}[/bold red]")
        return None
    except FileNotFoundError:
        console.print("[bold red]Error: 'yt-dlp' is not installed or not in your PATH.[/bold red]")
        console.print("Please install it to use this script.")
        sys.exit(1)
    except json.JSONDecodeError:
        console.print(f"[bold red]Error decoding JSON for full track info: {track_url}[/bold red]")
        return None


def display_tracks(tracks, page_number, page_size, total_tracks):
    """
    Displays a list of tracks in a table, paginated.
    """
    if not tracks:
        console.print("[bold yellow]No tracks found.[/bold yellow]")
        return

    start_index = (page_number - 1) * page_size
    end_index = min(start_index + page_size, total_tracks)
    
    tracks_to_display = tracks[start_index:end_index]

    total_pages = math.ceil(total_tracks / page_size)

    table = Table(title=f"Select a Track (Page {page_number}/{total_pages})", show_lines=True)
    table.add_column("Index", style="cyan")
    table.add_column("Title", style="magenta")
    table.add_column("Uploader", style="green")
    table.add_column("Duration", style="blue")

    for i, track in enumerate(tracks_to_display):
        # Displaying "N/A" for uploader in the table for speed
        table.add_row(
            str(start_index + i + 1), 
            track.get('title', 'N/A'), 
            track.get('uploader', 'N/A'), # Will be N/A here, fetched on play
            format_duration(track.get('duration'))
        )

    console.print(table)

def get_stream_url(track_url):
    """
    Gets the direct stream URL for a track using yt-dlp.
    """
    try:
        command = ["/home/keahiakio/scloud-player/venv/bin/yt-dlp", "-g", track_url]
        result = subprocess.run(command, capture_output=True, text=True, check=True)
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        console.print(f"[bold red]Error getting stream URL: {e.stderr}[/bold red]")
        return None
    except FileNotFoundError:
        console.print("[bold red]Error: 'yt-dlp' is not installed or not in your PATH.[/bold red]")
        console.print("Please install it to use this script (e.g., 'pip install yt-dlp').")
        sys.exit(1)

def play_track(track_info, player="mpv"):
    """
    Plays a stream URL with the selected player. Fetches full track info right before playing.
    Returns True if playback was successful, False if interrupted or an error occurs.
    """
    # Fetch full track info for the selected track to get accurate uploader/title
    full_info = get_full_track_info(track_info['url'])
    if not full_info:
        console.print(f"[bold red]Could not get full info for {track_info.get('title', 'selected track')}.[/bold red]")
        return False
    
    stream_url = get_stream_url(full_info['webpage_url']) # Use webpage_url for stream
    if not stream_url:
        return False

    title = full_info.get('title', 'Unknown Title')
    uploader = full_info.get('uploader', 'Unknown Uploader')
    duration = full_info.get('duration')
    duration_str = format_duration(duration)

    console.print(f"\n[bold green]Playing:[/bold green] [yellow]{title}[/yellow] by [green]{uploader}[/green] ([blue]{duration_str}[/blue])\n[dim]Link:[/dim] [link={full_info.get('webpage_url', track_info.get('url'))}]{full_info.get('webpage_url', track_info.get('url'))}[/link]")
    
    try:
        if player.lower() == "vlc":
            # Using cvlc for terminal-based VLC
            subprocess.run(["cvlc", "--play-and-exit", stream_url], check=True)
        else:
            subprocess.run(["mpv", stream_url], check=True)
        return True
    except subprocess.CalledProcessError as e:
        console.print(f"[bold red]{player} playback interrupted or failed: {e}[/bold red]")
        return False
    except FileNotFoundError:
        console.print(f"[bold red]Error: '{player}' is not installed or not in your PATH.[/bold red]")
        console.print(f"Please install it to play tracks.")
        sys.exit(1)


if __name__ == "__main__":
    setup_readline()
    config = load_config()
    
    try:
        # Use initial argument if provided
        initial_url = sys.argv[1] if len(sys.argv) > 1 else None
        
        while True:
            if initial_url:
                soundcloud_url = initial_url
                initial_url = None # Only use it once
            else:
                soundcloud_url = get_user_input("[bold cyan]Please enter a SoundCloud URL[/bold cyan]")
                if soundcloud_url.lower() == "q":
                    break

            if not soundcloud_url:
                continue

            tracks = get_track_data(soundcloud_url)

            if tracks:
                if config.get("shuffle", False):
                    random.shuffle(tracks)
                    console.print("[bold cyan]Shuffle enabled: tracks shuffled.[/bold cyan]")
                    time.sleep(1)

                page_size = config.get("page_size", 15)
                current_page = 1
                total_tracks = len(tracks)
                total_pages = math.ceil(total_tracks / page_size)
                
                # If autoplay is enabled in config, start from first track
                current_track_index = 0 if config.get("autoplay", False) else -1

                while True:
                    clear_terminal()
                    display_tracks(tracks, current_page, page_size, total_tracks)
                    
                    # Adjust prompt based on whether autoplay is active or a track was just played
                    if current_track_index != -1 and current_track_index < total_tracks:
                        prompt_message = f"[bold yellow]Playing next: {tracks[current_track_index].get('title', 'Unknown')}...[/bold yellow]"
                        console.print(prompt_message)
                        time.sleep(1) 
                        
                        selected_track = tracks[current_track_index]
                        if play_track(selected_track, player=config.get("player", "mpv")):
                            current_track_index += 1
                            if (current_track_index % page_size) == 0 and (current_track_index // page_size) + 1 > current_page and current_page < total_pages:
                                current_page += 1
                                console.print(f"[bold green]Advancing to page {current_page}...[/bold green]")
                                time.sleep(1)
                            
                            if current_track_index >= total_tracks:
                                console.print("[bold yellow]End of tracks. Looping back to start.[/bold yellow]")
                                current_page = 1
                                current_track_index = 0
                                time.sleep(1)
                            continue
                        else:
                            current_track_index = -1
                            console.print("[bold red]Autoplay/Selection stopped due to playback issue.[/bold red]")
                            time.sleep(2) 
                            
                    
                    prompt_text = "[bold yellow]Enter track number, 'n' for next page, 'p' for previous page, 's' to start autoplay, 'sh' to toggle shuffle, or 'q' to go back[/bold yellow]"
                    choice_str = get_user_input(prompt_text)

                    if choice_str.lower() == 'q':
                        break # Back to URL prompt
                    elif choice_str.lower() == 'n':
                        if current_page < total_pages:
                            current_page += 1
                            current_track_index = -1
                        else:
                            console.print("[bold yellow]Already on the last page.[/bold yellow]")
                            time.sleep(1)
                    elif choice_str.lower() == 'p':
                        if current_page > 1:
                            current_page -= 1
                            current_track_index = -1
                        else:
                            console.print("[bold yellow]Already on the first page.[/bold red]")
                            time.sleep(1)
                    elif choice_str.lower() == 's':
                        current_track_index = (current_page - 1) * page_size
                        if current_track_index < total_tracks:
                            console.print(f"[bold green]Starting autoplay from track {current_track_index + 1}...[/bold green]")
                            time.sleep(1)
                            continue
                        else:
                            console.print("[bold red]No tracks available to start autoplay.[/bold red]")
                            time.sleep(1)
                    elif choice_str.lower() == 'sh':
                        config["shuffle"] = not config.get("shuffle", False)
                        save_config(config)
                        status = "enabled" if config["shuffle"] else "disabled"
                        console.print(f"[bold cyan]Shuffle {status}. (Takes effect on next URL load)[/bold cyan]")
                        time.sleep(1)
                    else:
                        try:
                            choice = int(choice_str)
                            absolute_choice_index = choice - 1 

                            if 0 <= absolute_choice_index < total_tracks:
                                selected_track = tracks[absolute_choice_index]
                                if play_track(selected_track, player=config.get("player", "mpv")):
                                    # If they manually picked one, we don't necessarily start autoplay unless they want to
                                    current_track_index = -1
                                else:
                                    current_track_index = -1
                            else:
                                console.print("[bold red]Invalid track number.[/bold red]")
                                time.sleep(1)
                        except ValueError:
                            console.print("[bold red]Please enter a valid number, 'n', 'p', 's', 'sh', or 'q'.[/bold red]")
                            time.sleep(1)
            else:
                console.print("[bold red]No tracks were loaded.[/bold red]")
    except KeyboardInterrupt:
        console.print("\n[bold red]Exiting scloud-player...[/bold red]")
        sys.exit(0)