#!/bin/bash
# ClipABit Uninstaller for macOS
# Standalone script — no Python required.
# NOTE: intentionally no set -e — uninstaller must continue past individual failures.
set -u

BOLD='\033[1m'
GREEN='\033[92m'
YELLOW='\033[93m'
RED='\033[91m'
CYAN='\033[96m'
RESET='\033[0m'

failures=0

# Helper: remove a file with error tracking
remove_file() {
    local path="$1" label="$2" quiet="${3:-}"
    if [ -f "$path" ]; then
        if rm -f "$path"; then
            [ -z "$quiet" ] && echo -e "${GREEN}  Removed: ${label}${RESET}"
        else
            echo -e "${RED}  Failed to remove: ${label}${RESET}"
            failures=$((failures + 1))
        fi
    fi
}

# Helper: remove a directory with error tracking
remove_dir() {
    local path="$1" label="$2" quiet="${3:-}"
    if [ -d "$path" ]; then
        if rm -rf "$path"; then
            [ -z "$quiet" ] && echo -e "${GREEN}  Removed: ${label}${RESET}"
        else
            echo -e "${RED}  Failed to remove: ${label}${RESET}"
            failures=$((failures + 1))
        fi
    fi
}

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

# Remove files — shim first (removes Resolve menu entry)
remove_file "$SHIM"       "Bootstrap shim"
remove_file "$SHIM.bak"   "Bootstrap shim (backup)" quiet
remove_dir  "$PLUGIN_PKG" "Plugin package"
remove_dir  "$PLUGIN_PKG.bak" "Plugin package (backup)" quiet
remove_dir  "$PYTHON_DIR" "Python runtime"
remove_dir  "$PYTHON_DIR.bak" "Python runtime (backup)" quiet
remove_dir  "$DEPS_DIR"   "Dependencies"
remove_dir  "$DEPS_DIR.bak" "Dependencies (backup)" quiet
remove_file "$CONFIG_FILE" "Configuration"
remove_file "$CONFIG_FILE.bak" "Configuration (backup)" quiet

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
remove_dir "/tmp/clipabit-staging" "Staging leftovers" quiet

# Remove empty ClipABit directory
if [ -d "$CLIPABIT_DIR" ] && [ -z "$(ls -A "$CLIPABIT_DIR" 2>/dev/null)" ]; then
    rmdir "$CLIPABIT_DIR" && echo -e "${GREEN}  Removed empty directory: $CLIPABIT_DIR${RESET}"
fi

# Summary
echo ""
if [ "$failures" -gt 0 ]; then
    echo -e "${BOLD}============================================================${RESET}"
    echo -e "${YELLOW}  Uninstall completed with ${failures} error(s).${RESET}"
    echo -e "${BOLD}============================================================${RESET}\n"
    exit 1
else
    echo -e "${BOLD}============================================================${RESET}"
    echo -e "${BOLD}ClipABit Uninstall Complete${RESET}"
    echo -e "${BOLD}============================================================${RESET}\n"
fi
