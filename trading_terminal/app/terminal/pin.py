"""Trade PIN: a short number asked for before a live order is sent, on top of the Home Assistant login.

Only a salted hash is stored. Five wrong tries lock orders for 15 minutes. A forgotten PIN is cleared
by turning on the add-on's `reset_trade_pin` option and restarting the add-on.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import threading
import time

from . import config

PATH = config.DATA_DIR / "trade_pin.json"
ROUNDS = 200_000
MAX_TRIES = 5
LOCK_SECONDS = 15 * 60
_lock = threading.Lock()
_fails = {"n": 0, "until": 0.0}


def _load() -> dict:
    try:
        return json.loads(PATH.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _save(d: dict) -> None:
    PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(d))
    tmp.replace(PATH)


def _hash(pin: str, salt: str) -> str:
    return hashlib.pbkdf2_hmac("sha256", pin.encode(), bytes.fromhex(salt), ROUNDS).hex()


def reset_if_asked() -> bool:
    if os.getenv("RESET_TRADE_PIN", "").strip().lower() in ("1", "true", "yes", "on"):
        PATH.unlink(missing_ok=True)
        return True
    return False


def is_set() -> bool:
    return bool(_load().get("hash"))


def paper_too() -> bool:
    return bool(_load().get("paper"))


def required() -> bool:
    """Live orders always need the PIN; paper orders only when you've asked for that."""
    return config.LIVE or (is_set() and paper_too())


def status() -> dict:
    return {"set": is_set(), "required": required(), "paper": paper_too(), "live": config.LIVE,
            "locked_for": max(0, int(_fails["until"] - time.time()))}


def _valid_format(pin: str) -> bool:
    return pin.isdigit() and 4 <= len(pin) <= 8


def check(pin) -> None:
    """Raises ValueError with a plain-English reason unless the PIN is right."""
    with _lock:
        if not is_set():
            raise ValueError("Set a trade PIN first (it's asked for before every live order).")
        left = _fails["until"] - time.time()
        if left > 0:
            raise ValueError(f"Too many wrong PINs. Orders are locked for {int(left // 60) + 1} more minutes.")
        if not str(pin or "").strip():
            raise ValueError("Enter your trade PIN.")
        d = _load()
        if hmac.compare_digest(_hash(str(pin or ""), d["salt"]), d["hash"]):
            _fails.update(n=0, until=0.0)
            return
        _fails["n"] += 1
        if _fails["n"] >= MAX_TRIES:
            _fails.update(n=0, until=time.time() + LOCK_SECONDS)
            raise ValueError(f"Wrong PIN. Orders are locked for {LOCK_SECONDS // 60} minutes.")
        tries = MAX_TRIES - _fails["n"]
        raise ValueError(f"Wrong PIN ({tries} {'try' if tries == 1 else 'tries'} left).")


def set_pin(new: str, current: str | None = None) -> None:
    new = str(new or "").strip()
    if not _valid_format(new):
        raise ValueError("The PIN must be 4 to 8 digits.")
    if is_set():
        check(current)
    d = _load()
    salt = secrets.token_hex(16)
    d.update(salt=salt, hash=_hash(new, salt))
    _save(d)


def set_paper(on: bool, current: str | None) -> None:
    check(current)
    d = _load()
    d["paper"] = bool(on)
    _save(d)


def remove(current: str | None) -> None:
    check(current)
    PATH.unlink(missing_ok=True)
