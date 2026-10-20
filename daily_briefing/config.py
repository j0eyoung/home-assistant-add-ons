"""Add-on options from /data/options.json (env vars override for local dev)."""
import json
import os

OPTIONS_PATH = os.getenv("OPTIONS_PATH", "/data/options.json")

_DEFAULTS = {
    "notify_service": "", "morning_notification": True, "morning_time": "07:00",
    "refresh_seconds": 60, "calendars": [], "weather_entity": "",
    "shopping_list": "todo.shopping_list", "api_token": "", "api_key": "",
}


def options():
    opts = dict(_DEFAULTS)
    try:
        with open(OPTIONS_PATH) as f:
            # strip: a token pasted with a trailing newline would break the HTTP headers it goes into
            opts.update({k: v.strip() if isinstance(v, str) else v for k, v in json.load(f).items()
                         if v not in (None, "") and not (isinstance(v, str) and not v.strip())})
    except (OSError, ValueError):
        pass
    try:
        opts["refresh_seconds"] = min(600, max(30, int(opts["refresh_seconds"])))
    except (TypeError, ValueError):
        opts["refresh_seconds"] = 60
    cals = opts.get("calendars")
    opts["calendars"] = [c.strip() for c in cals if isinstance(c, str) and c.strip()] if isinstance(cals, list) else []
    return opts
