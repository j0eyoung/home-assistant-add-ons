"""Water, weight and blood pressure, and the questions to ask the PT.

Weight and blood pressure come from manual entries or from Home Assistant sensors (for example Home Assistant's
Withings integration for the scale and BP monitor): the add-on copies new readings into its own table, so the
history stays even after Home Assistant's recorder forgets them."""
import datetime
import sqlite3

import ha
import history
import library

# --- Questions for the PT ------------------------------------------------------------------------------------------


def questions(db_path):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    rows = [dict(r) for r in conn.execute("SELECT id, text, source, created, asked_on, answer FROM pt_questions "
                                          "ORDER BY asked_on IS NOT NULL, COALESCE(asked_on, '') DESC, id")]
    conn.close()
    return {"open": [r for r in rows if not r["asked_on"]], "asked": [r for r in rows if r["asked_on"]][:30]}


def add_question(db_path, text, source="me"):
    text = " ".join(text.split())[:300]
    if not text:
        return False
    conn = sqlite3.connect(db_path)
    if not conn.execute("SELECT 1 FROM pt_questions WHERE asked_on IS NULL AND lower(text) = lower(?)", (text,)).fetchone():
        conn.execute("INSERT INTO pt_questions (text, source, created) VALUES (?, ?, ?)",
                     (text, source if source in ("me", "ai") else "me", history.local_today()))
        conn.commit()
    conn.close()
    return True


def mark_asked(db_path, qid, answer="", undo=False):
    conn = sqlite3.connect(db_path)
    if undo:
        conn.execute("UPDATE pt_questions SET asked_on = NULL, answer = NULL WHERE id = ?", (qid,))
    else:
        conn.execute("UPDATE pt_questions SET asked_on = ?, answer = ? WHERE id = ?",
                     (history.local_today(), answer.strip()[:1000] or None, qid))
    conn.commit()
    conn.close()


def delete_question(db_path, qid):
    conn = sqlite3.connect(db_path)
    conn.execute("DELETE FROM pt_questions WHERE id = ?", (qid,))
    conn.commit()
    conn.close()


# --- Guided core canister (leaky can) breathing: 4 rounds of 10 paced breaths --------------------------------------------

_NUMBERS = ["one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten"]
_IN_CUES = {3: "In... let the pelvic floor soften", 6: "In... ribs wide", 9: "In... belly soft"}
_OUT_CUES = {2: "Out... feel the TA tighten under your fingers", 5: "Out... nothing pushes down",
             8: "Out... long and slow"}
PACES = {"calm": (4, 6), "quicker": (3, 5)}


def breathing_session(pace="calm", rounds=4, per_round=10):
    """Spoken segments (with exact lengths, so the voice keeps the pace) and the matching steps for the page's circle."""
    inhale, exhale = PACES.get(pace, PACES["calm"])
    segments = [{"text": "Core canister breathing. Lie on your back, knees bent, fingers just inside your hip bones. "
                         "Breathe in through your nose, and let your ribs widen, your belly soften, and your pelvic floor relax. "
                         "Breathe out slowly through soft lips, draw the lower belly in, and feel the TA tighten and flatten "
                         f"under your fingers. Never grip, and never push down. {rounds * per_round} breaths, in {rounds} rounds "
                         f"of {per_round}. Follow my voice and the circle.", "hold": 1}]
    steps = [{"kind": "talk", "label": "Getting ready"}]
    for r in range(1, rounds + 1):
        segments.append({"text": f"Round {r}.", "slot": 3})
        steps.append({"kind": "talk", "label": f"Round {r} of {rounds}", "round": r})
        for b in range(1, per_round + 1):
            segments.append({"text": "Breathe in" if b == 1 else _IN_CUES.get(b, "In"), "slot": inhale})
            steps.append({"kind": "in", "round": r, "breath": b, "secs": inhale})
            out = _OUT_CUES.get(b)
            segments.append({"text": f"{out}... {_NUMBERS[b - 1]}" if out else f"Out... {_NUMBERS[b - 1]}", "slot": exhale})
            steps.append({"kind": "out", "round": r, "breath": b, "secs": exhale})
        if r < rounds:
            segments.append({"text": "Rest. Breathe normally.", "slot": 10})
            steps.append({"kind": "rest", "label": "Rest", "round": r, "secs": 10})
    segments.append({"text": f"That's {rounds * per_round}. Nicely done. Let your breath come back to normal.", "hold": 1})
    steps.append({"kind": "talk", "label": "Done"})
    return segments, steps


# --- Water -----------------------------------------------------------------------------------------------------------


def water_settings(settings=None):
    w = (settings if settings is not None else library.load_settings()).get("water") or {}
    return {"goal": int(w.get("goal") or 80), "nudge": bool(w.get("nudge", True)), "time": w.get("time") or "14:00",
            "sent": w.get("sent") or ""}


def add_water(db_path, oz):
    now = history.local_now()
    conn = sqlite3.connect(db_path)
    conn.execute("INSERT INTO water_log (date, ts, oz) VALUES (?, ?, ?)",
                 (now.date().isoformat(), now.isoformat(timespec="seconds"), round(float(oz), 1)))
    conn.commit()
    conn.close()


def undo_water(db_path):
    conn = sqlite3.connect(db_path)
    conn.execute("DELETE FROM water_log WHERE id = (SELECT MAX(id) FROM water_log WHERE date = ?)", (history.local_today(),))
    conn.commit()
    conn.close()


def water_days(db_path, days, today):
    since = (today - datetime.timedelta(days=days - 1)).isoformat()
    conn = sqlite3.connect(db_path)
    try:
        rows = dict(conn.execute("SELECT date, SUM(oz) FROM water_log WHERE date >= ? GROUP BY date", (since,)).fetchall())
    except sqlite3.OperationalError:
        rows = {}
    conn.close()
    return [{"date": (today - datetime.timedelta(days=days - 1 - i)).isoformat(),
             "oz": round(rows.get((today - datetime.timedelta(days=days - 1 - i)).isoformat()) or 0, 1)} for i in range(days)]


def water_status(db_path, today):
    s = water_settings()
    days = water_days(db_path, 14, today)
    total = days[-1]["oz"]
    return {**s, "total": total, "pct": round(100 * total / s["goal"]) if s["goal"] else 0, "days": days}


# --- Weight and blood pressure ---------------------------------------------------------------------------------------


def add_reading(db_path, kind, v1, v2=None, v3=None, ts=None, source="manual"):
    ts = ts or history.local_now().isoformat(timespec="seconds")
    conn = sqlite3.connect(db_path)
    cur = conn.execute("INSERT OR IGNORE INTO body_metrics (date, ts, kind, v1, v2, v3, source) VALUES (?, ?, ?, ?, ?, ?, ?)",
                       (ts[:10], ts, kind, v1, v2, v3, source))
    conn.commit()
    added = cur.rowcount
    conn.close()
    return added


def delete_reading(db_path, rid):
    conn = sqlite3.connect(db_path)
    conn.execute("DELETE FROM body_metrics WHERE id = ?", (rid,))
    conn.commit()
    conn.close()


def readings(db_path, kind, since_iso):
    conn = sqlite3.connect(db_path)
    try:
        rows = conn.execute("SELECT id, date, ts, v1, v2, v3, source FROM body_metrics WHERE kind = ? AND date >= ? "
                            "ORDER BY ts", (kind, since_iso)).fetchall()
    except sqlite3.OperationalError:
        rows = []
    conn.close()
    keys = ("id", "date", "ts", "v1", "v2", "v3", "source")
    return [dict(zip(keys, r)) for r in rows]


def bp_category(sys_, dia):
    """American Heart Association categories (adults), as plain words."""
    if sys_ is None or dia is None:
        return None
    if sys_ > 180 or dia > 120:
        return "Very high: if you also feel unwell (chest pain, headache, vision changes), get help now"
    if sys_ >= 140 or dia >= 90:
        return "High (stage 2)"
    if sys_ >= 130 or dia >= 80:
        return "High (stage 1)"
    if sys_ >= 120:
        return "Elevated"
    return "Normal"


def body_status(db_path, today, days=90):
    since = (today - datetime.timedelta(days=days - 1)).isoformat()
    w = readings(db_path, "weight", since)
    bp = readings(db_path, "bp", since)
    latest_bp = bp[-1] if bp else None
    return {"days": days, "weight": w, "bp": bp,
            "bp_category": bp_category(latest_bp["v1"], latest_bp["v2"]) if latest_bp else None,
            "sensors": library.load_settings().get("body") or {}}


# Readings from Home Assistant sensors (e.g. the Withings integration)

def _lb(value, unit):
    unit = (unit or "").lower()
    v = float(value)
    if unit in ("kg", "kilograms"):
        return round(v * 2.20462, 1)
    if unit in ("g",):
        return round(v / 453.592, 1)
    return round(v, 1)


def _num(state):
    try:
        return float(state)
    except (TypeError, ValueError):
        return None


def _parse_ts(ts):
    """Home Assistant timestamps are UTC; stored as local time like everything else."""
    try:
        t = datetime.datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except (AttributeError, ValueError):
        return None
    return t.astimezone(history.local_now().tzinfo)


def sensor_options():
    """Home Assistant sensors that look like a scale or a blood pressure monitor, for the Settings drop-downs."""
    weight, bp, pulse = [], [], []
    for s in ha._states("sensor"):
        a = s.get("attributes") or {}
        eid, unit = s["entity_id"], (a.get("unit_of_measurement") or "").lower()
        item = {"id": eid, "name": a.get("friendly_name") or eid, "state": s.get("state"), "unit": a.get("unit_of_measurement")}
        if a.get("device_class") == "weight" or unit in ("kg", "lb", "lbs") and "weight" in eid:
            weight.append(item)
        elif unit == "mmhg":
            bp.append(item)
        elif unit in ("bpm", "beats/min") and any(w in eid for w in ("pulse", "heart")):
            pulse.append(item)
    return {"weight": weight, "bp": bp, "pulse": pulse}


def sync_from_ha(db_path, full=False):
    """Copies new readings from the chosen sensors (history since the last sync, or the last 10 days)."""
    cfg = library.load_settings().get("body") or {}
    ents = [cfg.get(k) for k in ("weight_entity", "sys_entity", "dia_entity", "pulse_entity") if cfg.get(k)]
    if not ents or not ha.available():
        return 0
    now = history.local_now()
    start = now - datetime.timedelta(days=10)
    if cfg.get("last_sync") and not full:
        try:
            start = max(start, datetime.datetime.fromisoformat(cfg["last_sync"]) - datetime.timedelta(hours=2))
        except ValueError:
            pass
    hist = ha.history(ents, start.isoformat())
    added = 0
    if cfg.get("weight_entity"):
        unit = ((ha.entity(cfg["weight_entity"]) or {}).get("attributes") or {}).get("unit_of_measurement")
        for ts, state in hist.get(cfg["weight_entity"], []):
            t, v = _parse_ts(ts), _num(state)
            if t and v and v > 0:
                added += add_reading(db_path, "weight", _lb(v, unit), ts=t.isoformat(timespec="seconds"), source="ha")
    if cfg.get("sys_entity") and cfg.get("dia_entity"):
        dias = [(_parse_ts(ts), _num(s)) for ts, s in hist.get(cfg["dia_entity"], [])]
        pulses = [(_parse_ts(ts), _num(s)) for ts, s in hist.get(cfg.get("pulse_entity") or "", [])]

        def near(points, t):
            best = min((p for p in points if p[0] and p[1]), key=lambda p: abs((p[0] - t).total_seconds()), default=None)
            return best[1] if best and abs((best[0] - t).total_seconds()) <= 300 else None
        for ts, state in hist.get(cfg["sys_entity"], []):
            t, s = _parse_ts(ts), _num(state)
            d = near(dias, t) if t else None
            if t and s and d:
                added += add_reading(db_path, "bp", s, d, near(pulses, t), ts=t.isoformat(timespec="seconds"), source="ha")
    library.save_settings({"body": {**cfg, "last_sync": now.isoformat(timespec="seconds")}})
    return added
