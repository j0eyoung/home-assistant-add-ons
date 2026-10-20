"""Trailing stops placed by the app once an entry order fills.

Brokers won't attach a trailing stop to an entry the way they attach a fixed stop loss, so the order
ticket records one here and the server's background loop watches the entry: as soon as it fills (or is
canceled after a partial fill) it sends a GTC trailing stop for the shares that filled.
"""
from __future__ import annotations

import json
import threading
import time
import uuid

from . import config

PATH = config.DATA_DIR / "exits.json"
GIVE_UP = 7 * 86400  # stop watching an entry that never shows up again
_lock = threading.Lock()

FILLED = {"filled"}
CLOSED = {"canceled", "cancelled", "apicancelled", "expired", "rejected", "inactive", "doneforday", "stopped", "suspended"}


def load() -> list[dict]:
    try:
        return json.loads(PATH.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def _save(items: list[dict]) -> None:
    PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(items[-200:], indent=1, default=str))
    tmp.replace(PATH)


def add(broker: str, order_id: str, symbol: str, entry_side: str, trail_percent: float | None,
        trail_price: float | None) -> None:
    with _lock:
        items = load()
        items.append({"id": uuid.uuid4().hex[:10], "time": time.time(), "broker": broker, "order_id": order_id,
                      "symbol": symbol, "side": "sell" if entry_side == "buy" else "buy",
                      "trail_percent": trail_percent, "trail_price": trail_price, "state": "waiting"})
        _save(items)


def waiting() -> list[dict]:
    return [x for x in load() if x["state"] == "waiting"]


def mark(exit_id: str, **fields) -> None:
    with _lock:
        items = load()
        for x in items:
            if x["id"] == exit_id:
                x.update(fields)
        _save(items)


def describe(x: dict) -> str:
    amt = f"{x['trail_percent']:g}%" if x.get("trail_percent") else f"${x['trail_price']:,.2f}"
    return f"trailing stop {amt}"


def check(brokers: dict, submit) -> list[str]:
    """One pass over the waiting exits. `submit(broker, exit, qty)` sends the trailing stop and returns
    its order id. Returns messages for the page's notifications."""
    msgs = []
    items = waiting()
    if not items:
        return msgs
    orders_by_broker: dict[str, dict] = {}
    for x in items:
        br = brokers.get(x["broker"])
        if br is None:
            continue
        if x["broker"] not in orders_by_broker:
            try:
                orders_by_broker[x["broker"]] = {o["id"]: o for o in br.orders()}
            except Exception:
                orders_by_broker[x["broker"]] = None
        book = orders_by_broker[x["broker"]]
        if book is None:
            continue
        o = book.get(x["order_id"])
        if o is None:
            if time.time() - x["time"] > GIVE_UP:
                mark(x["id"], state="lost")
            continue
        status = (o.get("status") or "").lower().replace("_", "")
        filled = float(o.get("filled_qty") or 0)
        if status in FILLED or (status in CLOSED and filled > 0):
            qty = filled or float(o.get("qty") or 0)
            try:
                exit_id = submit(br, x, qty)
                mark(x["id"], state="placed", exit_order=exit_id, qty=qty, placed=time.time())
                msgs.append(f"{x['symbol']}: {describe(x)} placed for {qty:g} shares")
            except Exception as e:
                mark(x["id"], state="failed", error=str(e))
                msgs.append(f"{x['symbol']}: couldn't place the {describe(x)}: {e}")
        elif status in CLOSED:
            mark(x["id"], state="canceled")
    return msgs
