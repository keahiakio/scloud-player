# SoundCloud Player (scloud-player)

A responsive, feature-rich terminal SoundCloud music player inspired by **musikcube**. Powered by `textual`, `yt-dlp`, `mpv`, and live `cava` audio frequency visualization. No login cookies or SoundCloud API keys required.

```
  ┌── SoundCloud Player [Musikcube] ────────────────────────────────────────────────────────┐
  │                                                                                          │
  │  Type to filter tracks... (Press '/' to search, Esc to clear)   ♫ NOW PLAYING ♫          │
  │  ┌──┬───┬────────────────────────────────┬──────────────┬─────┐  Track:    Solar Eclipse │
  │  │▶ │ 1 │ Solar Eclipse                  │ Drake        │03:24│  Artist:   Drake         │
  │  │· │ 2 │ Cold Shoulder                  │ Drake        │02:45│  Duration: 03:24         │
  │  │· │ 3 │ Quebec                         │ Drake        │03:10│  Status:   ▶ PLAYING     │
  │  └──┴───┴────────────────────────────────┴──────────────┴─────┘                          │
  │   Page 1 (30 tracks) | [p] Prev | [n] Next                      ▃▅▇ LIVE CAVA VISUALIZER ▇▅▃
  │                                                                     ▅      ▅             │
  │                                                                    ██▆    ██▆ ▄          │
  │                                                                  ▄█████  ███████▄        │
  │                                                                 █████████████████        │
  │  ▶ Solar Eclipse - Drake   01:14 [━━━━━━━━●──────────────] 03:24 Vol: 80% [====-]       │
  │    [AUTO: ON] [SHUF: OFF] [REP: OFF] [CACHE: 30/30 ⚡]                                    │
  └──────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## Key Features

- **Responsive Musikcube-Style TUI**: Multi-panel terminal user interface with adaptive split layout, tracks data table, now playing card, real-time seek bar, and live filter/search.
- **Live CAVA Spectrum Visualizer**: Integrated directly with `cava` (Console-based Audio Visualizer for PulseAudio/PipeWire), rendering real-time animated frequency bars with vibrant gradient colors (`bold magenta` peak -> `yellow` mid -> `bright blue` base) directly inside the TUI.
- **Fast 30-Song Paginated Loading**: Loads any SoundCloud URL (track, set, playlist, or user profile) in fast 30-song chunks via `--playlist-items` and batch metadata enrichment (SoundCloud API v2), keeping startup under 2 seconds.
- **30-Song In-Memory & Disk Stream Preloading**: Background worker pool pre-resolves direct audio streaming URLs for all 30 songs on the page. Transitions between tracks and autoplay take **zero delay**.
- **Non-blocking MPV Engine via IPC**: Communicates with `mpv` over Unix domain socket JSON IPC for fluid real-time seek bar tracking, volume adjustment, pause/play, and automatic track-end event detection.
- **Automated Installer (`install.sh`)**: One-command setup that verifies system dependencies (`mpv`, `cava`, `ffmpeg`), sets up Python virtual environment, installs dependencies, and creates a global `scloud-player` command.
- **Classic CLI Fallback**: Run with `--cli` for lightweight, non-TUI terminal prompt navigation.

---

## Quick Installation

Run the automated installer script:

```bash
git clone https://github.com/keahiakio/scloud-player.git
cd scloud-player
./install.sh
```

The installer will:
1. Detect your package manager and check for `mpv`, `cava`, and `ffmpeg`.
2. Create and configure a Python virtual environment (`./venv`).
3. Install all required dependencies (`textual`, `rich`, `yt-dlp`, `requests`).
4. Create an executable launcher at `~/.local/bin/scloud-player`.

Ensure `~/.local/bin` is in your `$PATH`. You can verify by running:

```bash
scloud-player --version
```

### Manual Installation

If you prefer to configure manually:

1. **Install system tools:**
   - Debian / Ubuntu:
     ```bash
     sudo apt update && sudo apt install -y python3 python3-venv mpv ffmpeg cava
     ```
   - Arch Linux:
     ```bash
     sudo pacman -S --needed python mpv ffmpeg cava
     ```
   - Fedora:
     ```bash
     sudo dnf install -y python3 mpv ffmpeg cava
     ```
   - macOS (Homebrew):
     ```bash
     brew install python mpv ffmpeg cava
     ```

2. **Set up virtual environment & dependencies:**
   ```bash
   python3 -m venv venv
   ./venv/bin/pip install -r requirements.txt
   ```

3. **Symlink launcher:**
   ```bash
   mkdir -p ~/.local/bin
   ln -sf "$(pwd)/main.py" ~/.local/bin/scloud-player
   ```

---

## Usage

Launch the player:

```bash
# Launch interactive TUI
scloud-player

# Launch TUI directly loaded with a SoundCloud URL
scloud-player "https://soundcloud.com/octobersveryown"

# Launch in classic CLI mode
scloud-player --cli "https://soundcloud.com/artist/sets/album"
```

### Keyboard Controls (TUI)

| Key | Action |
|:---:|:---|
| **`Space`** | Play / Pause current track |
| **`Enter`** | Play selected track |
| **`Up` / `Down`** or **`k` / `j`** | Navigate tracklist rows |
| **`n`** | Next Page (Loads next 30 tracks) |
| **`p`** | Previous Page (Loads previous 30 tracks) |
| **`>`** or **`Right`** | Seek forward 5 seconds |
| **`<`** or **`Left`** | Seek backward 5 seconds |
| **`+`** / **`-`** | Volume Up / Volume Down (5% increments) |
| **`a`** | Toggle Autoplay mode |
| **`s`** | Toggle Shuffle mode |
| **`r`** | Cycle Repeat mode (`Off` -> `One` -> `All`) |
| **`v`** | Cycle Visualizer mode (`CAVA` -> `Spectrum Sim` -> `Off`) |
| **`c`** | Spawn external CAVA visualizer window |
| **`l`** or **`u`** | Open interactive **Load URL** modal dialog |
| **`/`** | Focus search bar to filter tracks on current page |
| **`Esc`** | Clear filter and return focus to tracklist |
| **`q`** | Quit application |

Mouse interaction is also supported: click any row in the track table to select and play it.

---

## 30-Song Caching & Fast Pagination Architecture

### Fast 30-Track Batch Loading
When a SoundCloud URL or playlist is provided:
- `scloud-player` requests exactly 30 items for the active page (`--playlist-items 1:30` on page 1, `31:60` on page 2, etc.) using `yt-dlp`.
- Track titles, uploaders, durations, and permalinks are resolved in parallel via SoundCloud's API v2 batch endpoint (`/tracks?ids=...`), populating the table in under 2 seconds.

### Zero-Delay Stream Preloading
- In the background, a multi-threaded preloading queue (`SongCacheManager`) begins resolving the direct HLS/MP3 streaming URLs for all 30 songs on the page.
- Cached tracks display an electric badge (`⚡`) in the tracklist.
- When you click a track or autoplay advances, the stream URL is already in memory. Audio begins streaming instantaneously without waiting for network resolution.
- Valid stream URLs are also persisted to `~/.cache/scloud-player/stream_cache.json` with a 3-hour TTL.

---

## Live CAVA Visualizer Integration

The player includes built-in integration with [CAVA](https://github.com/karlstav/cava):
1. An internal CAVA daemon is automatically spawned with a raw ASCII streaming configuration.
2. CAVA monitors the desktop audio stream via PulseAudio or PipeWire.
3. The frequency values are rendered in real-time as multi-tier unicode equalizer bars (` `, `▂`, `▃`, `▄`, `▅`, `▆`, `▇`, `█`) with smooth color gradients.
4. **Dynamic Fallback**: If CAVA is not installed or audio monitor input is muted, the player automatically activates a realistic audio spectrum simulation while music is playing, ensuring the visualizer is always responsive and dynamic.
5. Pressing **`c`** allows launching a dedicated external CAVA terminal window.

---

## Configuration

Settings are saved in `~/.scloud-player-config.json`. You can modify defaults directly or adjust them via hotkeys in the player:

```json
{
    "player": "mpv",
    "autoplay": false,
    "shuffle": false,
    "page_size": 30,
    "cache_size": 30,
    "visualizer": "cava",
    "visualizer_bars": 24,
    "fullscreen": true,
    "repeat": "off",
    "volume": 80
}
```

---

## Running Tests

Run the test suite using `pytest`:

```bash
./venv/bin/pytest
```

---

## License & Compliance

### Dual License

This project is dual-licensed under either:

- **MIT License** ([LICENSE-MIT](LICENSE-MIT) or <https://opensource.org/licenses/MIT>)
- **Apache License, Version 2.0** ([LICENSE-APACHE](LICENSE-APACHE) or <https://www.apache.org/licenses/LICENSE-2.0>)

at your option.

### Third-Party Compliance & Credits

All dependencies and tools used by this project are open source:

- **textual**: MIT License (<https://github.com/Textualize/textual>) - Modern terminal application framework.
- **rich**: MIT License (<https://github.com/Textualize/rich>) - Terminal formatting, tables, and markup.
- **yt-dlp**: The Unlicense (<https://github.com/yt-dlp/yt-dlp>) - Media extraction tool.
- **requests**: Apache License 2.0 (<https://github.com/psf/requests>) - HTTP library.
- **cava**: MIT License (<https://github.com/karlstav/cava>) - Console audio visualizer (executed as independent subprocess).
- **mpv**: GPL-2.0-or-later / LGPL-2.1-or-later (<https://mpv.io>) - Audio backend controlled via JSON IPC.
- **ffmpeg**: LGPL-2.1-or-later / GPL-2.0-or-later (<https://ffmpeg.org>) - Multimedia decoding libraries.
