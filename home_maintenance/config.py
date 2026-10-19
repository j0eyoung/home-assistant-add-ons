"""Add-on options from /data/options.json (env vars override for local dev)."""
import json
import os

OPTIONS_PATH = os.getenv("OPTIONS_PATH", "/data/options.json")

_DEFAULTS = {
    "notify_service": "", "reminder_time": "09:00", "todo_entity": "todo.shopping_list",
    "toner_entities": "", "toner_threshold": 15, "printer_model": "",
    "s3_endpoint": "", "s3_bucket": "", "s3_access_key": "", "s3_secret_key": "", "s3_region": "auto",
    "s3_prefix": "home/receipts",
}


def options():
    opts = dict(_DEFAULTS)
    try:
        with open(OPTIONS_PATH) as f:
            opts.update({k: v.strip() if isinstance(v, str) else v for k, v in json.load(f).items()
                         if v not in (None, "") and not (isinstance(v, str) and not v.strip())})
    except (OSError, ValueError):
        pass
    try:
        opts["toner_threshold"] = min(90, max(1, int(opts["toner_threshold"])))
    except (TypeError, ValueError):
        opts["toner_threshold"] = 15
    return opts
