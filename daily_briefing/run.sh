#!/bin/bash

# Fill blank options from addon_secrets.json (shared across add-ons, kept only on the Green)
python3 shared_secrets.py

# Web UI and API through Home Assistant ingress only. Nothing is written to disk: the briefing is kept in memory.
# --no-access-log: an access log line for every request would be written to the eMMC journal.
exec uvicorn api:app --host 0.0.0.0 --port 8506 --no-access-log
