#!/usr/bin/env bash
# Run this to check for a working Python install and, if you confirm,
# install/update everything the LED Controller app needs on macOS or
# Linux:
#   chmod +x setup_unix.sh   (only needed the first time)
#   ./setup_unix.sh
#
# Checks a handful of common Python command names, since not every
# system has a bare "python3" on PATH (e.g. freshly-added deadsnakes
# PPAs on Linux, or Homebrew installs on macOS sometimes only expose
# a versioned binary like "python3.13").
#
# setup.py itself lives in the "Setup" subfolder next to this script.

set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SETUP_SCRIPT="$DIR/Setup/setup.py"
MIN_MAJOR=3
MIN_MINOR=9
DOWNLOAD_URL="https://www.python.org/downloads/"

open_download_page() {
    if command -v open >/dev/null 2>&1; then
        open "$DOWNLOAD_URL" >/dev/null 2>&1 || true        # macOS
    elif command -v xdg-open >/dev/null 2>&1; then
        xdg-open "$DOWNLOAD_URL" >/dev/null 2>&1 || true    # most Linux desktops
    else
        echo "Could not open a browser automatically. Please visit:"
        echo "  $DOWNLOAD_URL"
        return
    fi
    echo "If a browser didn't open, visit this page manually:"
    echo "  $DOWNLOAD_URL"
}

is_no() {
    case "$1" in
        [nN]|[nN][oO]) return 0 ;;
        *) return 1 ;;
    esac
}

PYTHON=""
for candidate in python3 python python3.13 python3.12 python3.11 python3.10 python3.9; do
    if command -v "$candidate" >/dev/null 2>&1; then
        PYTHON="$candidate"
        break
    fi
done

if [ -z "$PYTHON" ]; then
    echo ""
    echo "No Python installation was found (checked python3, python, and"
    echo "common versioned names)."
    echo "This app needs Python $MIN_MAJOR.$MIN_MINOR or newer."
    echo ""
    read -r -p "Would you like to open the Python download page now? [Y/n] " DOWNLOAD_PY
    if is_no "$DOWNLOAD_PY"; then
        echo "You can install Python later from $DOWNLOAD_URL"
    else
        open_download_page
        echo "Any 3.9 or newer version works fine with this app - you don't need"
        echo "the very latest release. Install it, then run this script again."
    fi
    exit 1
fi

echo "Found a Python installation via: $PYTHON ($("$PYTHON" --version 2>&1))"

if ! "$PYTHON" -c "import sys; sys.exit(0 if sys.version_info >= ($MIN_MAJOR, $MIN_MINOR) else 1)"; then
    echo ""
    echo "This Python installation looks older than $MIN_MAJOR.$MIN_MINOR."
    echo "This app needs Python $MIN_MAJOR.$MIN_MINOR or newer."
    echo ""
    read -r -p "Would you like to open the Python download page to get a newer version? [Y/n] " DOWNLOAD_PY
    if is_no "$DOWNLOAD_PY"; then
        echo "Continuing with the current Python installation - some things may not work correctly."
    else
        open_download_page
        echo "Any 3.9 or newer version works fine with this app - you don't need"
        echo "the very latest release, just something at or above $MIN_MAJOR.$MIN_MINOR."
        echo "Install it, then run this script again."
        exit 1
    fi
else
    echo "Python version meets the minimum requirement of $MIN_MAJOR.$MIN_MINOR+."
fi

if [ ! -f "$SETUP_SCRIPT" ]; then
    echo ""
    echo "ERROR: Could not find setup.py at:"
    echo "  $SETUP_SCRIPT"
    echo "Make sure the \"Setup\" folder is next to this script."
    exit 1
fi

read -r -p "Run setup.py now to install/update dependencies? [Y/n] " RUN_SETUP
if is_no "$RUN_SETUP"; then
    echo "Skipping setup.py. You can run it later with:"
    echo "  $PYTHON \"$SETUP_SCRIPT\""
    exit 0
fi

"$PYTHON" "$SETUP_SCRIPT" "$@"
