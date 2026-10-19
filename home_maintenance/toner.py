"""Printer toner alerts. Reads the configured toner sensors (percent) from Home Assistant; when one drops below
the threshold, sends a phone notification and adds the cartridge to the shopping list, once per cartridge.
The alert re-arms when the level is back at or above the threshold (a new cartridge).

Unavailable or unreadable sensors (the HP integration often reports `unavailable`) are never an error: they are
shown as "unavailable" and keep their last good level. The database is only written when something changed."""
import datetime
import re

import config
import db
import ha


def setting(key):
    """A value picked on the page (kept in the database) wins over the add-on option."""
    v = db.get_setting("toner_" + key)
    return config.options()[("toner_" + key) if key != "printer_model" else key] if v in (None, "") else v


def entities():
    """The watched entity ids: the page's picker, else the toner_entities option (comma, space or newline separated)."""
    v = setting("entities")
    return [e for e in (v if isinstance(v, list) else re.split(r"[,\s]+", str(v or ""))) if e]


def reading(state):
    """Percent (0-100) from a Home Assistant state object, None when unavailable or not a number."""
    if not state:
        return None
    try:
        v = float(state.get("state"))
    except (TypeError, ValueError):
        return None
    return v if 0 <= v <= 100 else None


def label(entity_id, state):
    """'Black' from 'HP Color LaserJet Black Toner' or sensor.hp_black_toner."""
    name = ((state or {}).get("attributes") or {}).get("friendly_name") or entity_id.split(".", 1)[-1].replace("_", " ")
    name = re.sub(r"\b(toner|ink|cartridge|level|remaining)\b", "", name, flags=re.I).strip()
    return " ".join(name.split()) or entity_id


def cartridge(entity_id, state):
    """Shopping list text, e.g. 'HP M255 black toner cartridge'."""
    color = label(entity_id, state)
    model = str(setting("printer_model") or "").strip()
    if model:               # "HP Black Toner" on an "HP M255" is just "Black"
        known = {w.lower() for w in model.split()}
        color = " ".join(w for w in color.split() if w.lower() not in known) or color
    return f"{model} {color} toner cartridge".strip() if model else f"{color} toner cartridge"


def check(now=None):
    """Reads every watched sensor once. Returns one dict per sensor: entity_id, name, level, status, alerted."""
    now = (now or datetime.datetime.now()).replace(microsecond=0).isoformat()
    threshold = setting("threshold")
    out = []
    for eid in entities():
        try:
            state = ha.get_state(eid)
        except Exception as e:
            print(f"Toner sensor {eid}: {e}", flush=True)
            state = None
        level = reading(state)
        prev = (db.rows("SELECT * FROM toner WHERE entity_id=?", (eid,)) or [None])[0]
        name = label(eid, state) if state else (prev or {}).get("name") or eid
        alerted = bool(prev and prev["alerted"])
        if level is None:
            status, level = "unavailable", (prev or {}).get("level")
        elif level < threshold:
            status = "low"
            if not alerted:
                alerted = _alert(eid, state, level, threshold)
        else:
            status, alerted = "ok", False
        fresh = {"entity_id": eid, "name": name, "level": level, "status": status, "alerted": alerted}
        if not prev or any(prev[k] != (int(v) if k == "alerted" else v) for k, v in fresh.items()):
            db.run("INSERT INTO toner(entity_id,name,level,status,alerted,checked_at) VALUES(?,?,?,?,?,?) "
                   "ON CONFLICT(entity_id) DO UPDATE SET name=excluded.name, level=excluded.level, "
                   "status=excluded.status, alerted=excluded.alerted, checked_at=excluded.checked_at",
                   (eid, name, level, status, int(alerted), now))
        out.append(fresh)
    return out


def _alert(eid, state, level, threshold):
    """Notification and shopping list item. True when at least one of them went through (so a failure retries)."""
    item = cartridge(eid, state)
    sent = False
    try:
        service = ha.notify_service()
        if service:
            ha.send_message(service, f"{label(eid, state)} toner is low",
                            f"{level:.0f}% left (alert below {threshold}%). Added {item} to the shopping list.",
                            f"toner-{eid}")
            sent = True
    except Exception as e:
        print(f"Toner notification failed: {e}", flush=True)
    try:
        ha.add_todo(item)
        sent = True
    except Exception as e:
        print(f"Toner shopping list add failed: {e}", flush=True)
    return sent


def status():
    """What the page shows: every watched sensor with its last known level and status (no call to Home Assistant)."""
    saved = {r["entity_id"]: r for r in db.rows("SELECT * FROM toner")}
    return [saved.get(e) or {"entity_id": e, "name": e, "level": None, "status": "not checked yet",
                             "alerted": 0, "checked_at": None} for e in entities()]
