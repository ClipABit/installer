#!/bin/bash
# ClipABit Uninstaller for macOS
# Standalone script — no Python required.
set -euo pipefail

BOLD='\033[1m'
GREEN='\033[92m'
YELLOW='\033[93m'
RED='\033[91m'
CYAN='\033[96m'
RESET='\033[0m'

# Resolve directories
SHIM="$HOME/Library/Application Support/Blackmagic Design/DaVinci Resolve/Fusion/Scripts/Utility/ClipABit.py"
PLUGIN_PKG="$HOME/Library/Application Support/Blackmagic Design/DaVinci Resolve/Fusion/Modules/clipabit"
# ClipABit application directories
CLIPABIT_DIR="$HOME/Library/Application Support/ClipABit"
PYTHON_DIR="$CLIPABIT_DIR/python"
DEPS_DIR="$CLIPABIT_DIR/deps"
CONFIG_FILE="$CLIPABIT_DIR/config.dat"

echo -e "\n${BOLD}============================================================${RESET}"
echo -e "${BOLD}ClipABit Uninstaller${RESET}"
echo -e "${BOLD}============================================================${RESET}\n"

# Check if Resolve is running
if pgrep -x "DaVinci Resolve" > /dev/null 2>&1; then
    echo -e "${YELLOW}  DaVinci Resolve is currently running.${RESET}"
    echo -e "${YELLOW}  Please close it before uninstalling, or restart it after.${RESET}"
    if [ "${1:-}" != "-y" ] && [ "${1:-}" != "--yes" ]; then
        read -rp "  Continue anyway? [y/N]: " answer
        if [[ ! "$answer" =~ ^[Yy] ]]; then
            echo -e "${CYAN}  Uninstall cancelled.${RESET}"
            exit 0
        fi
    fi
fi

# Check what exists
found=0
for item in "$SHIM" "$PLUGIN_PKG" "$PYTHON_DIR" "$DEPS_DIR" "$CONFIG_FILE"; do
    [ -e "$item" ] && found=1 && break
done

if [ "$found" -eq 0 ]; then
    echo -e "${CYAN}  No ClipABit installation found. Nothing to remove.${RESET}"
    exit 0
fi

# Display what will be removed
echo -e "${CYAN}  The following will be removed:${RESET}\n"
[ -e "$SHIM" ]       && echo "    Bootstrap shim:  $SHIM"
[ -e "$PLUGIN_PKG" ] && echo "    Plugin package:  $PLUGIN_PKG"
[ -e "$PYTHON_DIR" ] && echo "    Python runtime:  $PYTHON_DIR"
[ -e "$DEPS_DIR" ]   && echo "    Dependencies:    $DEPS_DIR"
[ -e "$CONFIG_FILE" ]&& echo "    Configuration:   $CONFIG_FILE"
echo ""
echo -e "${CYAN}  Keychain credentials (clipabit-plugin) will also be cleared.${RESET}"
echo -e "${CYAN}  Package receipt (com.clipabit.plugin.installer) will be removed.${RESET}"

# Confirmation
if [ "${1:-}" != "-y" ] && [ "${1:-}" != "--yes" ]; then
    echo ""
    read -rp "  Proceed with uninstall? [y/N]: " answer
    if [[ ! "$answer" =~ ^[Yy] ]]; then
        echo -e "${CYAN}  Uninstall cancelled.${RESET}"
        exit 0
    fi
fi

echo ""

# Remove files — shim first
[ -f "$SHIM" ]       && rm -f "$SHIM"       && echo -e "${GREEN}  Removed: Bootstrap shim${RESET}"
[ -f "$SHIM.bak" ]   && rm -f "$SHIM.bak"
[ -d "$PLUGIN_PKG" ] && rm -rf "$PLUGIN_PKG" && echo -e "${GREEN}  Removed: Plugin package${RESET}"
[ -d "$PLUGIN_PKG.bak" ] && rm -rf "$PLUGIN_PKG.bak"
[ -d "$PYTHON_DIR" ] && rm -rf "$PYTHON_DIR" && echo -e "${GREEN}  Removed: Python runtime${RESET}"
[ -d "$PYTHON_DIR.bak" ] && rm -rf "$PYTHON_DIR.bak"
[ -d "$DEPS_DIR" ]   && rm -rf "$DEPS_DIR"   && echo -e "${GREEN}  Removed: Dependencies${RESET}"
[ -d "$DEPS_DIR.bak" ] && rm -rf "$DEPS_DIR.bak"
[ -f "$CONFIG_FILE" ]&& rm -f "$CONFIG_FILE" && echo -e "${GREEN}  Removed: Configuration${RESET}"
[ -f "$CONFIG_FILE.bak" ] && rm -f "$CONFIG_FILE.bak"

# Clear keychain credentials
if security delete-generic-password -s "clipabit-plugin" -a "tokens" > /dev/null 2>&1; then
    echo -e "${GREEN}  Keychain credentials removed.${RESET}"
else
    echo -e "${CYAN}  No keychain credentials found.${RESET}"
fi

# Remove pkg receipt
if pkgutil --forget com.clipabit.plugin.installer > /dev/null 2>&1; then
    echo -e "${GREEN}  Package receipt removed.${RESET}"
else
    echo -e "${CYAN}  No package receipt found.${RESET}"
fi

# Clean up staging leftovers
[ -d "/tmp/clipabit-staging" ] && rm -rf "/tmp/clipabit-staging"

# Remove empty ClipABit directory
if [ -d "$CLIPABIT_DIR" ] && [ -z "$(ls -A "$CLIPABIT_DIR" 2>/dev/null)" ]; then
    rmdir "$CLIPABIT_DIR" && echo -e "${GREEN}  Removed empty directory: $CLIPABIT_DIR${RESET}"
fi

echo -e "\n${BOLD}============================================================${RESET}"
echo -e "${BOLD}ClipABit Uninstall Complete${RESET}"
echo -e "${BOLD}============================================================${RESET}\n"
