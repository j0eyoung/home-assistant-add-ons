#!/bin/bash

# Data lives in the shared config folder so it survives updates
export RESORTS_PATH="/config/ski_resorts.json"
export SETTINGS_PATH="/config/ski_settings.json"
export DB_PATH="/config/ski.db"

opt() {
    python3 -c "import json,sys; v=json.load(open('/data/options.json')).get(sys.argv[1]); print('' if v is None else ''.join(str(v).split()))" "$1" 2>/dev/null
}

export POWDER_ALERT_INCHES="$(opt powder_alert_inches)"
[ -z "$POWDER_ALERT_INCHES" ] && export POWDER_ALERT_INCHES=6

# Anthropic API key from the Configuration tab (whitespace stripped); "Ask Claude" is off without it
key="$(opt anthropic_api_key)"
if [ -n "$key" ]; then
    export ANTHROPIC_API_KEY="$key"
else
    echo "No Anthropic API key set: Ask Claude will not work until you add one in the Configuration tab."
fi

exec uvicorn api:app --host 0.0.0.0 --port 8099
