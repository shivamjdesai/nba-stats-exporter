#!/bin/bash

set -u

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$PROJECT_DIR" || exit 1

echo "Starting NBA Stats Exporter live preview..."

if ! command -v python3 >/dev/null 2>&1; then
    echo
    echo "Python 3 is required. Install it from https://www.python.org/downloads/"
    read -r -p "Press Return to close."
    exit 1
fi

if command -v git >/dev/null 2>&1 && git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    if [ -z "$(git status --porcelain)" ]; then
        echo "Checking GitHub for updates..."
        git pull --ff-only || echo "Could not retrieve updates; starting the current version."
    else
        echo "Local changes detected; automatic GitHub updates are paused."
    fi
fi

if [ ! -d ".venv" ]; then
    echo "Creating the local Python environment..."
    python3 -m venv .venv || exit 1
fi

source .venv/bin/activate

REQUIREMENTS_HASH="$(shasum -a 256 requirements.txt | awk '{print $1}')"
HASH_FILE=".venv/.requirements-hash"
INSTALLED_HASH=""
if [ -f "$HASH_FILE" ]; then
    INSTALLED_HASH="$(<"$HASH_FILE")"
fi

if [ "$REQUIREMENTS_HASH" != "$INSTALLED_HASH" ]; then
    echo "Installing or updating application requirements..."
    python3 -m pip install --upgrade pip || exit 1
    python3 -m pip install -r requirements.txt || exit 1
    printf '%s\n' "$REQUIREMENTS_HASH" > "$HASH_FILE"
fi

auto_sync() {
    while true; do
        sleep 15
        if command -v git >/dev/null 2>&1 \
            && git rev-parse --is-inside-work-tree >/dev/null 2>&1 \
            && [ -z "$(git status --porcelain)" ]; then
            BEFORE_SHA="$(git rev-parse HEAD 2>/dev/null)"
            if git pull --ff-only --quiet; then
                AFTER_SHA="$(git rev-parse HEAD 2>/dev/null)"
                if [ "$BEFORE_SHA" != "$AFTER_SHA" ]; then
                    echo "New changes received from GitHub. Refreshing the app..."
                fi
            fi
        fi
    done
}

auto_sync &
SYNC_PID=$!
trap 'kill "$SYNC_PID" >/dev/null 2>&1 || true' EXIT INT TERM

echo
echo "The app will open in your browser. Keep this window open while using it."
echo "Future GitHub updates will be checked every 15 seconds."
echo
python3 -m streamlit run app.py
