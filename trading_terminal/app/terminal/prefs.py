"""Screen settings (ranges, tabs, recent tickers, last screen) kept on the server, so every device shares them."""
from __future__ import annotations

import json
import threading

from . import config

PATH = config.DATA_DIR / "prefs.json"
MAX_BYTES = 64_000
_lock = threading.Lock()


def load() -> dict:
    try:
        v = json.loads(PATH.read_text())
        return v if isinstance(v, dict) else {}
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def update(values: dict) -> dict:
    """Merges `values` in (a value of None removes the key) and returns everything."""
    with _lock:
        cur = load()
        for k, v in values.items():
            k = str(k)[:64]
            if v is None:
                cur.pop(k, None)
            else:
                cur[k] = v
        text = json.dumps(cur, separators=(",", ":"))
        if len(text) > MAX_BYTES:
            raise ValueError("Too many saved settings")
        PATH.parent.mkdir(parents=True, exist_ok=True)
        tmp = PATH.with_suffix(".tmp")
        tmp.write_text(text)
        tmp.replace(PATH)
        return cur
