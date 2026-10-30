#!/usr/bin/env bash
# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2026 Kiwi Akio
#
# Automated Installer for SoundCloud Player (scloud-player)
# Installs system dependencies, sets up Python virtual environment,
# and configures the global 'scloud-player' CLI executable.

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BIN_DIR="${HOME}/.local/bin"
VENV_DIR="${SCRIPT_DIR}/venv"

BOLD="\033[1m"
GREEN="\033[0;32m"
CYAN="\033[0;36m"
YELLOW="\033[1;33m"
RED="\033[0;31m"
RESET="\033[0m"

echo -e "${CYAN}${BOLD}"
echo "  ╔═══════════════════════════════════════════════════════╗"
echo "  ║         SoundCloud Player (scloud-player)             ║"
echo "  ║           Musikcube TUI Edition Installer             ║"
echo "  ╚═══════════════════════════════════════════════════════╝"
echo -e "${RESET}"

# 1. Detect Package Manager
detect_pkg_manager() {
    if command -v apt-get &>/dev/null; then
        echo "apt"
    elif command -v dnf &>/dev/null; then
        echo "dnf"
    elif command -v pacman &>/dev/null; then
        echo "pacman"
    elif command -v zypper &>/dev/null; then
        echo "zypper"
    elif command -v brew &>/dev/null; then
        echo "brew"
    else
        echo "unknown"
    fi
}

PKG_MGR=$(detect_pkg_manager)

# 2. Check and prompt for system dependencies
MISSING_PKGS=()

if ! command -v python3 &>/dev/null; then
    MISSING_PKGS+=("python3")
fi

if ! command -v mpv &>/dev/null; then
    MISSING_PKGS+=("mpv")
fi

if ! command -v ffmpeg &>/dev/null; then
    MISSING_PKGS+=("ffmpeg")
fi

CAVA_AVAILABLE=true
if ! command -v cava &>/dev/null && [ ! -f "${HOME}/.local/bin/cava" ]; then
    CAVA_AVAILABLE=false
    MISSING_PKGS+=("cava")
fi

if [ ${#MISSING_PKGS[@]} -gt 0 ]; then
    echo -e "${YELLOW}[!] Missing recommended system tools: ${MISSING_PKGS[*]}${RESET}"
    case "$PKG_MGR" in
        apt)
            echo -e "${CYAN}You can install them via:${RESET}"
            echo -e "  sudo apt update && sudo apt install -y python3 python3-venv mpv ffmpeg cava"
            ;;
        dnf)
            echo -e "${CYAN}You can install them via:${RESET}"
            echo -e "  sudo dnf install -y python3 mpv ffmpeg cava"
            ;;
        pacman)
            echo -e "${CYAN}You can install them via:${RESET}"
            echo -e "  sudo pacman -S --needed python mpv ffmpeg cava"
            ;;
        brew)
            echo -e "${CYAN}You can install them via:${RESET}"
            echo -e "  brew install python mpv ffmpeg cava"
            ;;
        *)
            echo -e "${YELLOW}Please install ${MISSING_PKGS[*]} using your distribution's package manager.${RESET}"
            ;;
    esac
    echo ""
else
    echo -e "${GREEN}[✓] System multimedia tools found (mpv, ffmpeg, cava).${RESET}"
fi

# 3. Create Virtual Environment
echo -e "${CYAN}[*] Setting up Python virtual environment in ${VENV_DIR}...${RESET}"
if [ ! -d "${VENV_DIR}" ]; then
    python3 -m venv "${VENV_DIR}"
fi

# 4. Install / Upgrade Python dependencies
echo -e "${CYAN}[*] Installing dependencies from requirements.txt...${RESET}"
"${VENV_DIR}/bin/pip" install --quiet --upgrade pip
"${VENV_DIR}/bin/pip" install --quiet -r "${SCRIPT_DIR}/requirements.txt"

echo -e "${GREEN}[✓] Python dependencies installed successfully.${RESET}"

# 5. Create launcher script in ~/.local/bin/scloud-player
mkdir -p "${BIN_DIR}"
LAUNCHER="${BIN_DIR}/scloud-player"
rm -f "${LAUNCHER}"

echo -e "${CYAN}[*] Creating executable launcher at ${LAUNCHER}...${RESET}"
cat << 'EOF' > "${LAUNCHER}"
#!/usr/bin/env bash
SCRIPT_DIR="$(cd "$(dirname "$(readlink -f "$0")")/.." && pwd)"
REPO_DIR="/home/keahiakio/scloud-player"

if [ -d "${REPO_DIR}/venv" ]; then
    exec "${REPO_DIR}/venv/bin/python" "${REPO_DIR}/main.py" "$@"
else
    exec python3 "${REPO_DIR}/main.py" "$@"
fi
EOF

# Update dynamic repo path in launcher script
sed -i "s|REPO_DIR=\"/home/keahiakio/scloud-player\"|REPO_DIR=\"${SCRIPT_DIR}\"|g" "${LAUNCHER}"
chmod +x "${LAUNCHER}"
chmod +x "${SCRIPT_DIR}/main.py"

echo -e "${GREEN}[✓] Launcher created and marked executable.${RESET}"

# 6. Verify PATH
if [[ ":$PATH:" != *":${BIN_DIR}:"* ]]; then
    echo -e "${YELLOW}[!] Warning: ${BIN_DIR} is not currently in your \$PATH.${RESET}"
    echo -e "    Add this line to your ~/.bashrc or ~/.zshrc or ~/.config/fish/config.fish:"
    echo -e "    ${CYAN}export PATH=\"\$HOME/.local/bin:\$PATH\"${RESET}"
fi

# 7. Self-test
echo ""
echo -e "${GREEN}${BOLD}Installation complete!${RESET}"
echo -e "Run the player at any time with:"
echo -e "  ${CYAN}scloud-player${RESET}                           (Interactive Musikcube TUI)"
echo -e "  ${CYAN}scloud-player \"<SoundCloud URL>\"${RESET}       (Load URL in TUI)"
echo -e "  ${CYAN}scloud-player --cli${RESET}                     (Classic CLI mode)"
echo ""
