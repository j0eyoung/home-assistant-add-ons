#!/bin/bash

# Fill blank options from /config/addon_secrets.json (shared across add-ons, kept only on the Green)
python3 shared_secrets.py

# Set the database path to the shared Home Assistant config folder
# so it persists across updates and is accessible to Claude Terminal
export DB_PATH="/config/workout_tracker.db"

# The AI Coach tab signs in to Claude itself; the login is kept here so it survives updates.
export CLAUDE_CONFIG_DIR="/data/claude"
mkdir -p "$CLAUDE_CONFIG_DIR"

# Optional fallback: Claude token from the add-on Configuration tab (made with `claude setup-token`).
# Strip all whitespace: copying a wrapped token out of a terminal adds line breaks.
token="$(python3 -c 'import json; print("".join((json.load(open("/data/options.json")).get("claude_code_oauth_token") or "").split()))' 2>/dev/null)"
if [ -n "$token" ]; then
    export CLAUDE_CODE_OAUTH_TOKEN="$token"
else
    echo "No Claude token set: the AI Coach tab will not work until you add one in the Configuration tab."
fi

# Initialize the database if it doesn't exist
python3 db.py

# Collect API Ninjas exercises in the background (does nothing without a key)
python3 ninjas_sync.py &

# Web UI and its API (Home Assistant ingress and direct on port 8501). Claude Terminal uses
# the same server for /workout/today and /workout/log.
exec uvicorn api:app --host 0.0.0.0 --port 8501
