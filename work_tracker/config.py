"""Add-on options from /data/options.json (env vars override for local dev)."""
import json
import os

OPTIONS_PATH = os.getenv("OPTIONS_PATH", "/data/options.json")

_DEFAULTS = {
    "notify_service": "", "stop_time": "17:30", "daily_target": 0.0, "weekly_target": 0.0,
    "task_time": "09:00", "summary_day": "fri", "summary_time": "17:00",
}
DAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]


def options():
    opts = dict(_DEFAULTS)
    try:
        with open(OPTIONS_PATH) as f:
            opts.update({k: v.strip() if isinstance(v, str) else v for k, v in json.load(f).items()
                         if v not in (None, "") and not (isinstance(v, str) and not v.strip())})
    except (OSError, ValueError):
        pass
    for k in ("daily_target", "weekly_target"):
        try:
            opts[k] = max(0.0, float(opts[k]))
        except (TypeError, ValueError):
            opts[k] = 0.0
    if str(opts["summary_day"]).lower() not in DAYS:
        opts["summary_day"] = "fri"
    opts["summary_day"] = str(opts["summary_day"]).lower()
    return opts
