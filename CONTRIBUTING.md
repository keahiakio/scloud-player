# Contributing to scloud-player

Thank you for your interest in improving `scloud-player`! We welcome contributions ranging from bug fixes and sound engine tweaks to visual themes, keybindings, and documentation enhancements.

---

## Code of Conduct

This project is governed by the Contributor Covenant [Code of Conduct](CODE_OF_CONDUCT.md). By contributing, you agree to foster an open, welcoming, and inclusive community.

---

## Architecture Overview

`scloud-player` is built around several decoupled components:
- **TUI Frontend (`scloud_player/tui.py`)**: Built using [Textual](https://github.com/Textualize/textual) and [Rich](https://github.com/Textualize/rich) for a reactive, dual-pane terminal layout.
- **Audio Engine (`scloud_player/player.py`)**: Controls an `mpv` background daemon over a non-blocking JSON IPC Unix domain socket.
- **Spectrum Visualizer (`scloud_player/visualizer.py`)**: Spawns and monitors [CAVA](https://github.com/karlstav/cava) for real-time audio analysis.
- **SoundCloud API & Streaming (`scloud_player/api.py`)**: Resolves profile likes, playlists, and tracks via SoundCloud API v2 and `yt-dlp`.

---

## Development & Local Testing

### Prerequisites
- Python 3.10+
- `mpv`, `ffmpeg`, and `cava` (installed via your package manager)
- Git

### Setup Instructions
1. Fork and clone the repository:
   ```bash
   git clone https://github.com/<your-username>/scloud-player.git
   cd scloud-player
   ```
2. Create and activate a virtual environment:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt pytest
   ```

### Running Tests
Run the automated test suite with `pytest`:
```bash
./venv/bin/pytest tests/
# or with active virtualenv:
pytest tests/
```

### Running the App
Test the interactive TUI locally:
```bash
python3 main.py
```

---

## Coding Standards

- Follow [PEP 8](https://peps.python.org/pep-0008/) style guidelines.
- Preserve asynchronous responsiveness; avoid blocking the Textual event loop with synchronous network or audio I/O.
- Ensure all new features or bug fixes have corresponding unit tests in `tests/`.
- Use [Conventional Commits](https://www.conventionalcommits.org/) (e.g., `feat:`, `fix:`, `perf:`, `docs:`, `test:`).

---

## Pull Request Process

1. Create a feature branch:
   ```bash
   git checkout -b feature/my-feature-name
   ```
2. Make your commits with clear messages.
3. Run the test suite:
   ```bash
   pytest tests/
   ```
4. Push your branch to your fork and submit a Pull Request to `keahiakio/scloud-player:main`.
5. Fill out the PR template checklist to facilitate review.
