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
CACHE_DIR = os.path.expanduser("~/.cache/scloud-player")

DEFAULT_CONFIG = {
    "player": "mpv",
    "autoplay": False,
    "shuffle": False,
    "page_size": 30,          # 30 songs max per page
    "cache_size": 30,         # 30 songs cached in memory/stream cache
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
