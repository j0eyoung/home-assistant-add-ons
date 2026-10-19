#!/bin/bash

# Fill blank options from addon_secrets.json (shared across add-ons, kept only on the Green)
python3 shared_secrets.py

# Database in the add-on's own config folder so it survives updates
export DB_PATH="/config/home_maintenance.db"

python3 db.py

# Web UI and API through Home Assistant ingress only.
# --no-access-log: an access log line for every request would be written to the eMMC journal.
exec uvicorn api:app --host 0.0.0.0 --port 8504 --no-access-log
