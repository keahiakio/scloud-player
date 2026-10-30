# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2026 Kiwi Akio

"""
Configuration management for scloud-player.
Loads and saves persistent user preferences from ~/.scloud-player-config.json.
"""

import json
import os
import shutil

CONFIG_FILE = os.path.expanduser("~/.scloud-player-config.json")
HISTORY_FILE = os.path.expanduser("~/.scloud-player-history")
URL_HISTORY_FILE = os.path.expanduser("~/.scloud-player-url-history")
CACHE_DIR = os.path.expanduser("~/.cache/scloud-player")

DEFAULT_CONFIG = {
    "player": "mpv",
    "autoplay": False,
    "shuffle": False,
    "page_size": 40,          # 40 songs max per page
    "cache_size": 40,         # 40 songs cached in memory/stream cache
    "visualizer": "cava",     # "cava", "spectrum", "waves", "vectorscope", "off"
    "visualizer_bars": 24,    # Number of frequency bars in TUI visualizer
    "fullscreen": True,
    "repeat": "off",          # "off", "one", "all"
    "volume": 80,
    "theme": "musikcube"
}


def get_cava_executable():
    """Finds cava binary on system PATH or common locations."""
    path = shutil.which("cava")
    if path:
        return path
    for candidate in [
        os.path.expanduser("~/.local/bin/cava"),
        "/usr/local/bin/cava",
        "/usr/bin/cava",
    ]:
        if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
            return candidate
    return None


def get_mpv_executable():
    """Finds mpv binary on system PATH or common locations."""
    path = shutil.which("mpv")
    if path:
        return path
    for candidate in [
        os.path.expanduser("~/.local/bin/mpv"),
        "/usr/local/bin/mpv",
        "/usr/bin/mpv",
    ]:
        if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
            return candidate
    return "mpv"


def load_config(config_file=None):
    """Loads configuration from file or returns default."""
    import sys
    main_mod = sys.modules.get("main")
    target_file = config_file or getattr(main_mod, "CONFIG_FILE", CONFIG_FILE)
    if os.path.exists(target_file):
        try:
            with open(target_file, "r", encoding="utf-8") as f:
                config = json.load(f)
                for k, v in DEFAULT_CONFIG.items():
                    if k not in config:
                        config[k] = v
                return config
        except Exception:
            pass
    return DEFAULT_CONFIG.copy()


def save_config(config, config_file=None):
    """Saves configuration to file."""
    import sys
    main_mod = sys.modules.get("main")
    target_file = config_file or getattr(main_mod, "CONFIG_FILE", CONFIG_FILE)
    try:
        os.makedirs(os.path.dirname(target_file), exist_ok=True)
        with open(target_file, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=4)
    except Exception:
        pass


def load_url_history() -> list:
    """Loads previously used SoundCloud URLs in chronological order (oldest to newest)."""
    urls: list = []

    # 1. Load from dedicated URL history file if it exists
    if os.path.exists(URL_HISTORY_FILE):
        try:
            with open(URL_HISTORY_FILE, "r", encoding="utf-8") as f:
                for line in f:
                    u = line.strip()
                    if u and u not in urls:
                        urls.append(u)
        except Exception:
            pass

    # 2. Also backfill from ~/.scloud-player-history if missing or short
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    u = line.strip()
                    if not u:
                        continue
                    if "soundcloud" in u.lower() or u.startswith("http") or (u.count("/") >= 2 and not u.startswith("/")):
                        if u in urls:
                            urls.remove(u)
                        urls.append(u)
        except Exception:
            pass

    return urls


def add_url_to_history(url: str):
    """Adds a URL to persistent history, deduplicating so it becomes the latest entry."""
    u = url.strip()
    if not u:
        return

    urls = load_url_history()
    if u in urls:
        urls.remove(u)
    urls.append(u)

    # Keep at most 500 entries
    if len(urls) > 500:
        urls = urls[-500:]

    try:
        os.makedirs(os.path.dirname(URL_HISTORY_FILE), exist_ok=True)
        with open(URL_HISTORY_FILE, "w", encoding="utf-8") as f:
            for item in urls:
                f.write(f"{item}\n")
    except Exception:
        pass

    # Also append to HISTORY_FILE so CLI readline has it
    try:
        with open(HISTORY_FILE, "a", encoding="utf-8") as f:
            f.write(f"{u}\n")
    except Exception:
        pass
