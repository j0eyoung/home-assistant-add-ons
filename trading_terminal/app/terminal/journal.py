"""Trade journal: every order sent from the app, with the note you wrote about why."""
from __future__ import annotations

import json
import time
import uuid

from . import config

PATH = config.DATA_DIR / "journal.json"


def load() -> list[dict]:
    try:
        return json.loads(PATH.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def _save(entries: list[dict]) -> None:
    PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(entries, indent=1, default=str))
    tmp.replace(PATH)


def add(broker: str, order_id: str, req, price: float | None, note: str, tags: list[str]) -> None:
    entries = load()
    entries.append({
        "id": uuid.uuid4().hex[:10], "time": time.time(), "broker": broker, "order_id": order_id,
        "mode": config.MODE_LABEL, "symbol": req.symbol, "side": req.side, "qty": req.qty,
        "type": req.order_type, "price": price, "stop_loss": req.stop_loss, "take_profit": req.take_profit,
        "note": note.strip(), "tags": tags, "review": "",
    })
    _save(entries)


def update(entry_id: str, **fields) -> None:
    entries = load()
    for e in entries:
        if e["id"] == entry_id:
            e.update(fields)
    _save(entries)


def delete(entry_id: str) -> None:
    _save([e for e in load() if e["id"] != entry_id])


TAGS = ["Breakout", "Pullback", "Earnings", "News", "Value", "Momentum", "Dividend", "Idea list", "Hunch", "Exit plan"]
