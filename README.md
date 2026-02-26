# SoundCloud Player

A simple terminal-based SoundCloud player using `yt-dlp` and `mpv`.

## Installation

Follow these steps to set up the SoundCloud Player:

### 1. Prerequisites

Ensure you have the following installed on your system:
- **Python 3**: The scripting language.
- **mpv**: The media player used for audio playback.
  - On Debian/Ubuntu: `sudo apt install mpv`

### 2. Clone the Repository

```bash
git clone https://github.com/keahiakio/scloud-player.git
cd scloud-player
```

### 3. Set Up a Virtual Environment

It's recommended to use a virtual environment to manage dependencies:

```bash
python3 -m venv venv
```

### 4. Install Dependencies

Install the required Python packages into the virtual environment:

```bash
./venv/bin/pip install -r requirements.txt
```

## Configuration

The script stores its settings in `~/.scloud-player-config.json`. You can manually edit this file to change:
- `player`: Either `mpv` (default) or `vlc`.
- `autoplay`: Set to `true` to start playing automatically when a URL is loaded.
- `shuffle`: Set to `true` to shuffle tracks on load.
- `page_size`: Number of tracks displayed per page.

## Usage

Follow these steps to use the SoundCloud Player script:

1.  **Navigate to the project directory:**
    ```bash
    cd scloud-player
    ```

2.  **Run the script:**
    ```bash
    ./venv/bin/python main.py
    ```
    Alternatively, you can make the script executable and run it directly (if your shebang matches your environment):
    ```bash
    chmod +x main.py
    ./main.py
    ```

3.  **Enter a SoundCloud URL:**
    The script will prompt you to enter a SoundCloud URL.
    *   **Input History:** You can use the **Up/Down arrow keys** to scroll through your previous URL and track selection entries.

4.  **Navigate and select a track:**
    The script will display a paginated list of tracks.

    You have the following options:
    *   Enter a **track number** (e.g., `6`) to play the corresponding song.
    *   Enter `n` to go to the **next page**.
    *   Enter `p` to go to the **previous page**.
    *   Enter `s` to **start autoplay** from the first track of the current page.
    *   Enter `ap` to **toggle autoplay** mode (saves to config).
    *   Enter `sh` to **toggle shuffle** mode (saves to config).
    *   Enter `q` to **go back** to the URL entry prompt.
    *   Press `Ctrl+C` to **exit** the program completely.

5.  **Enjoy the music!**
    When you select a track, the script will first fetch its full details (including uploader and duration) and display them, then launch `mpv` to play the audio. `mpv` will take over your terminal during playback. After the track finishes (or you close `mpv`), the script will return to the track selection prompt.

## Global Execution

To run `scloud-player` from any directory in your terminal, you can create a symlink in your local bin directory:

1.  **Make the script executable:**
    ```bash
    chmod +x ~/scloud-player/main.py
    ```

2.  **Create a symlink:**
    ```bash
    ln -s ~/scloud-player/main.py ~/.local/bin/scloud-player
    ```

3.  **Verify your PATH:**
    Ensure `~/.local/bin` is in your `$PATH` environment variable. You can check this by running `echo $PATH`. If it's not there, you may need to add it to your `.bashrc` or `.config/fish/config.fish`.

Now you can just run `scloud-player` from anywhere!

**Troubleshooting:**

*   **`yt-dlp` or `mpv` not found:** Ensure both `yt-dlp` and `mpv` are installed on your system and available in your PATH. If you encounter issues with `yt-dlp`, you might need to install `curl_cffi` manually into the virtual environment (`./venv/bin/pip install curl_cffi`).
*   **"Connection refused" or "Internal Server Error":** This might be a temporary issue with SoundCloud or an invalid URL. Double-check the URL you provided.
*   **`mpv` exits prematurely / Nothing plays:** This can be due to various reasons (e.g., invalid stream, `mpv` configuration, audio device issues). To diagnose, you would temporarily modify the `play_track` function in `main.py` to print `mpv`'s verbose output (e.g., `subprocess.run(["mpv", "--verbose", stream_url], capture_output=True, text=True)` and then print `process.stdout` and `process.stderr`). However, this requires direct modification of the script and is beyond the current scope of the task.

If you encounter any other issues, please let me know!
