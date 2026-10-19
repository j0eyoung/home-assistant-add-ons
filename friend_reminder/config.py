"""Add-on options from /data/options.json (env vars override for local dev)."""
import json
import os

OPTIONS_PATH = os.getenv("OPTIONS_PATH", "/data/options.json")

_DEFAULTS = {
    "anthropic_api_key": "", "model": "claude-opus-5-5",
    "notify_service": "", "nudge_time": "12:00", "nudges_per_day": 1,
}


def options():
    opts = dict(_DEFAULTS)
    try:
        with open(OPTIONS_PATH) as f:
            # strip: a key pasted with a trailing newline would break the HTTP headers it goes into
            opts.update({k: v.strip() if isinstance(v, str) else v for k, v in json.load(f).items()
                         if v not in (None, "") and not (isinstance(v, str) and not v.strip())})
    except (OSError, ValueError):
        pass
    if os.getenv("ANTHROPIC_API_KEY"):
        opts["anthropic_api_key"] = os.environ["ANTHROPIC_API_KEY"]
    try:
        opts["nudges_per_day"] = min(2, max(1, int(opts["nudges_per_day"])))
    except (TypeError, ValueError):
        opts["nudges_per_day"] = 1
    return opts
