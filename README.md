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
  │   Page 1 (40 tracks) | [p] Prev | [n] Next                      ▃▅▇ LIVE CAVA VISUALIZER ▇▅▃
  │                                                                     ▅      ▅             │
  │                                                                    ██▆    ██▆ ▄          │
  │                                                                  ▄█████  ███████▄        │
  │                                                                 █████████████████        │
  │  ▶ Solar Eclipse - Drake   01:14 [━━━━━━━━●──────────────] 03:24 Vol: 80% [====-]       │
  │    [AUTO: ON] [SHUF: OFF] [REP: OFF] [CACHE: 40/40 ⚡]                                    │
  └──────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## Key Features

- **Dynamic Resizing & Responsive Musikcube-Style TUI**: Multi-panel terminal user interface that dynamically adapts to any window or screen size (80x24 standard terminals, tmux/kitty split panes, and ultra-compact displays). Supports 1-click view switching (`Tab` / `m`) between Fullscreen Tracks, Fullscreen Visualizer, and Dual-Column Split mode.
- **Adaptive Visualizer & Transport Bar**: Real-time frequency bars (6 to 36 bars) and transport controls automatically scale to fit available terminal width and height without line-wrapping, overflow, or clipping.
- **Live CAVA Spectrum Visualizer**: Integrated directly with `cava` (Console-based Audio Visualizer for PulseAudio/PipeWire), rendering real-time animated frequency bars with vibrant gradient colors (`bold magenta` peak -> `yellow` mid -> `bright blue` base) directly inside the TUI.
- **Fast 40-Song Paginated Loading**: Loads any SoundCloud URL (track, set, playlist, or user profile) in fast 40-song chunks via `--playlist-items` and batch metadata enrichment (SoundCloud API v2), keeping startup under 2 seconds.
- **40-Song In-Memory & Disk Stream Preloading**: Background worker pool pre-resolves direct audio streaming URLs for all 40 songs on the page. Transitions between tracks and autoplay take **zero delay**.
- **Non-blocking MPV Engine via IPC**: Communicates with `mpv` over Unix domain socket JSON IPC for fluid real-time live seek bar tracking, volume adjustment, pause/play, and automatic track-end event detection.
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
| **`Tab`** or **`m`** | **Switch View Mode** (`Tracks` -> `Visualizer` -> `Split`) |
| **`]`** or **`N`** | **Next Track** (skip to next track in queue) |
| **`[`** or **`P`** | **Previous Track** (previous track or restart) |
| **`Up` / `Down`** or **`k` / `j`** | Navigate tracklist rows |
| **`n`** | Next Page (Loads next 40 tracks) |
| **`p`** | Previous Page (Loads previous 40 tracks) |
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

## Dynamic Resizing & View Modes

`scloud-player` features an intelligent, multi-tier responsive layout system designed to look great on any terminal size, from full 4K monitors to 80x24 standard terminals, tmux/kitty split panes, and compact laptop windows:

- **View Mode Switching (`Tab` or `m`)**:
  - **`Tracks` View**: Expands the track library to 100% width, showing full titles, artists, duration, and stream caching indicators. Perfect for compact terminals or browsing large playlists.
  - **`Visualizer` View**: Expands the Now Playing metadata card and live CAVA spectrum visualizer to 100% width with high-resolution multi-column bars.
  - **`Split` View**: Dual-column Musikcube layout with side-by-side library and visualizer panels.
  - **`Auto` Mode (Default)**: Automatically selects `Split` on screens $\ge 85$ columns and switches to `Tracks` on narrow screens ($< 85$ columns).
- **Adaptive Breakpoints**:
  - **Width Breakpoints**:
    - $\ge 115$ columns: Full transport bar with 20-character seek bar, volume meter, and verbose badges.
    - $85 - 114$ columns: Streamlined seek bar, volume percentage, and compact badges.
    - $65 - 84$ columns (Standard 80-col terminals): 8-character seek bar, elapsed/total timer, and abbreviated status badges. Fits neatly on a single line with zero wrapping.
    - $< 65$ columns: Ultra-compact transport display omitting the seek bar to prioritize track title and timer.
  - **Height Breakpoints**:
    - $\ge 26$ rows: Full view with keyboard shortcut cheatsheet.
    - $18 - 25$ rows: Shortcuts cheatsheet hides automatically, giving full vertical space to the visualizer and track list.
    - $< 18$ rows: Ultra-short mode hiding the visualizer and top bar, leaving maximum screen real estate for the track library.

---

## 40-Song Caching & Fast Pagination Architecture

### Fast 40-Track Batch Loading
When a SoundCloud URL or playlist is provided:
- `scloud-player` requests exactly 40 items for the active page (`--playlist-items 1:40` on page 1, `41:80` on page 2, etc.) using `yt-dlp`.
- Track titles, uploaders, durations, and permalinks are resolved in parallel via SoundCloud's API v2 batch endpoint (`/tracks?ids=...`), populating the table in under 2 seconds.

### Zero-Delay Stream Preloading
- In the background, a multi-threaded preloading queue (`SongCacheManager`) begins resolving the direct HLS/MP3 streaming URLs for all 40 songs on the page.
- Cached tracks display an electric badge (`⚡`) in the tracklist.
- When you click a track, press Next Track (`]`), or autoplay advances, the stream URL is already in memory. Audio begins streaming instantaneously without waiting for network resolution.
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
    "page_size": 40,
    "cache_size": 40,
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

## Credits & Acknowledgements

This project is built on the shoulders of giants across the open source community. Immense gratitude and credit go to:

- **[musikcube](https://github.com/clangen/musikcube)** (Casey Langen & contributors):
  The gold standard of terminal audio players. `scloud-player` is heavily inspired by `musikcube`'s clean multi-pane layout, responsive split architecture, and intuitive keyboard navigation.
- **[CAVA (Console-based Audio Visualizer)](https://github.com/karlstav/cava)** (Karl Stavestrand & contributors):
  The legendary terminal audio visualizer for Linux and macOS. Powers the live, responsive audio spectrum analysis by reading audio sinks directly from PulseAudio and PipeWire.
- **[mpv](https://mpv.io)** (The mpv project & contributors):
  The rock-solid media player used as the audio engine daemon. Its JSON IPC protocol enables non-blocking transport controls, live time-position polling, and instant streaming.
- **[Textual](https://github.com/Textualize/textual)** (Will McGugan & Textualize):
  The modern, reactive Python TUI framework that brings terminal applications to life with CSS styling and asynchronous widgets.
- **[Rich](https://github.com/Textualize/rich)** (Will McGugan & Textualize):
  The foundational Python library for beautiful terminal formatting, tables, color gradients, and renderables.
- **[yt-dlp](https://github.com/yt-dlp/yt-dlp)** (The yt-dlp project team):
  The high-performance media downloader and metadata extractor that makes fast paginated SoundCloud stream extraction possible.
- **[FFmpeg](https://ffmpeg.org)** (Fabrice Bellard & the FFmpeg team):
  The universal multimedia processing framework used under the hood for audio decoding.
- **[Requests](https://github.com/psf/requests)** (Kenneth Reitz & the Python Software Foundation):
  The standard HTTP library powering rapid batch track enrichment against SoundCloud's API v2.

---

## License & Compliance

### Dual License

This project is dual-licensed under either:

- **MIT License** ([LICENSE-MIT](LICENSE-MIT) or <https://opensource.org/licenses/MIT>)
- **Apache License, Version 2.0** ([LICENSE-APACHE](LICENSE-APACHE) or <https://www.apache.org/licenses/LICENSE-2.0>)

at your option.

### Third-Party Compliance & Licenses

All dependencies and external programs used by this project are open source:

- **musikcube**: BSD-3-Clause (<https://github.com/clangen/musikcube>) - Layout & UX inspiration.
- **cava**: MIT License (<https://github.com/karlstav/cava>) - Audio visualizer subprocess.
- **mpv**: GPL-2.0-or-later / LGPL-2.1-or-later (<https://mpv.io>) - Media player daemon controlled via external JSON IPC.
- **textual**: MIT License (<https://github.com/Textualize/textual>) - Terminal user interface framework.
- **rich**: MIT License (<https://github.com/Textualize/rich>) - Terminal formatting and tables.
- **yt-dlp**: The Unlicense (<https://github.com/yt-dlp/yt-dlp>) - Stream URL and metadata extractor.
- **ffmpeg**: LGPL-2.1-or-later / GPL-2.0-or-later (<https://ffmpeg.org>) - Multimedia decoding libraries.
- **requests**: Apache License 2.0 (<https://github.com/psf/requests>) - HTTP client library.
