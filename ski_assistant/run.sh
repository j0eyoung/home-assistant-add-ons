#!/bin/bash

# Fill blank options from /config/addon_secrets.json (shared across add-ons, kept only on the Green)
python3 shared_secrets.py

# Data lives in the shared config folder so it survives updates
export RESORTS_PATH="/config/ski_resorts.json"
export SETTINGS_PATH="/config/ski_settings.json"
export DB_PATH="/config/ski.db"

opt() {
    python3 -c "import json,sys; v=json.load(open('/data/options.json')).get(sys.argv[1]); print('' if v is None else ''.join(str(v).split()))" "$1" 2>/dev/null
}

export POWDER_ALERT_INCHES="$(opt powder_alert_inches)"
[ -z "$POWDER_ALERT_INCHES" ] && export POWDER_ALERT_INCHES=6

# Claude runs through Claude Code on your subscription. Sign in from Settings in the app; the login is kept
# here so it survives updates.
export CLAUDE_CONFIG_DIR="/data/claude"
mkdir -p "$CLAUDE_CONFIG_DIR"

# Optional fallback: a token from `claude setup-token` in the Configuration tab (whitespace stripped)
token="$(opt claude_code_oauth_token)"
if [ -n "$token" ]; then
    export CLAUDE_CODE_OAUTH_TOKEN="$token"
fi

# Optional: CDOT COtrip key for live I-70 incidents, conditions and travel times
export COTRIP_API_KEY="$(opt cotrip_api_key)"

exec uvicorn api:app --host 0.0.0.0 --port 8099
