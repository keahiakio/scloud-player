To use the SoundCloud Player script, follow these steps:

1.  **Navigate to the project directory:**
    ```bash
    cd scloud-player
    ```

2.  **Run the script:**
    ```bash
    ./venv/bin/python main.py
    ```
    Alternatively, you can make the script executable and run it directly:
    ```bash
    chmod +x main.py
    ./main.py
    ```

3.  **Enter a SoundCloud URL:**
    The script will prompt you to enter a SoundCloud URL. This can be a link to:
    *   A user's "likes" page (e.g., `https://soundcloud.com/keahiakio/likes`)
    *   A user's "posts" page (e.g., `https://soundcloud.com/user/tracks`)
    *   A public playlist (e.g., `https://soundcloud.com/monstercat/sets/call-of-the-wild-275`)
    *   The SoundCloud discover page (e.g., `https://soundcloud.com/discover`)

    Example:
    ```
    Please enter a SoundCloud URL: https://soundcloud.com/keahiakio/likes
    ```

4.  **Navigate and select a track:**
    The script will display a paginated list of tracks (15 songs per page).
    ```
                                     Select a Track (Page X/Y)                                     
    ┏━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━┳━━━━━━━━━━┓
    ┡━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━╇━━━━━━━━━━┩
    │ ...   │                                                           │ N/A      │ N/A      │
    └───────┴───────────────────────────────────────────────────────────┴──────────┴──────────┘
    Enter track number, 'n' for next, 'p' for previous, 's' to start autoplay, or 'q' to quit:
    ```
    **Note on Uploader/Duration:** For faster loading of the track list, the 'Uploader' and 'Duration' columns in the table initially show "N/A". The full uploader name and accurate duration will be fetched and displayed in the "Playing:" message when you select and play a specific track.

    You have the following options:
    *   Enter a **track number** (e.g., `6`) to play the corresponding song.
    *   Enter `n` (or `N`) to go to the **next page**.
    *   Enter `p` (or `P`) to go to the **previous page**.
    *   Enter `s` (or `S`) to **start autoplay** from the first track of the current page.
    *   Enter `q` (or `Q`) to **quit** the script.

5.  **Enjoy the music!**
    When you select a track, the script will first fetch its full details (including uploader and duration) and display them, then launch `mpv` to play the audio. `mpv` will take over your terminal during playback. After the track finishes (or you close `mpv`), the script will return to the track selection prompt.

**Troubleshooting:**

*   **`yt-dlp` or `mpv` not found:** Ensure both `yt-dlp` and `mpv` are installed on your system and available in your PATH. If you encounter issues with `yt-dlp`, you might need to install `curl_cffi` manually into the virtual environment (`./venv/bin/pip install curl_cffi`).
*   **"Connection refused" or "Internal Server Error":** This might be a temporary issue with SoundCloud or an invalid URL. Double-check the URL you provided.
*   **`mpv` exits prematurely / Nothing plays:** This can be due to various reasons (e.g., invalid stream, `mpv` configuration, audio device issues). To diagnose, you would temporarily modify the `play_track` function in `main.py` to print `mpv`'s verbose output (e.g., `subprocess.run(["mpv", "--verbose", stream_url], capture_output=True, text=True)` and then print `process.stdout` and `process.stderr`). However, this requires direct modification of the script and is beyond the current scope of the task.

If you encounter any other issues, please let me know!
