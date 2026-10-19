"""Personal records, symptom trends, the PT visit report and the ski readiness tests.

Everything here reads the same SQLite history the rest of the add-on writes; nothing is stored except the ski test
results (ski_tests table) and the records found when a workout is saved (kept in that workout's JSON)."""
import datetime
import json
import sqlite3

import history
import library
import planner

# --- Personal records ------------------------------------------------------------------------------------------------


def personal_records(db_path, log_id, holds):
    """New bests set in workout `log_id`, compared with every earlier done set of the same exercise.
    A first-ever session sets no record (there's nothing to beat yet). Holds store seconds in the reps column."""
    conn = sqlite3.connect(db_path)
    rows = conn.execute("SELECT exercise, COALESCE(weight_lbs, 0), COALESCE(reps, 0) FROM workout_sets "
                        "WHERE log_id = ? AND done = 1 AND exercise != ''", (log_id,)).fetchall()
    out = []
    for name in sorted({r[0] for r in rows}):
        mine = [(w, r) for e, w, r in rows if e == name]
        prev = conn.execute("SELECT COALESCE(weight_lbs, 0), COALESCE(reps, 0) FROM workout_sets "
                            "WHERE exercise = ? AND done = 1 AND log_id < ?", (name, log_id)).fetchall()
        if not prev:
            continue
        if name in holds:
            best, old = max(r for _, r in mine), max(r for _, r in prev)
            if best > old:
                out.append({"exercise": name, "text": f"Longest hold: {best} s (was {old} s)"})
            continue
        top, old_top = max(w for w, _ in mine), max(w for w, _ in prev)
        if top > old_top:
            out.append({"exercise": name, "text": f"Heaviest: {top:g} lb (was {old_top:g} lb)"})
        elif top and top == old_top:
            best = max(r for w, r in mine if w == top)
            old = max(r for w, r in prev if w == top)
            if best > old:
                out.append({"exercise": name, "text": f"Most reps at {top:g} lb: {best} (was {old})"})
        elif not top and not old_top:
            best, old = max(r for _, r in mine), max(r for _, r in prev)
            if best > old:
                out.append({"exercise": name, "text": f"Most reps: {best} (was {old})"})
    conn.close()
    return out


# --- Symptom trends ------------------------------------------------------------------------------------------------

THEME_SHORT = {"legs": "Legs", "back": "Back", "core": "Core", "hips": "Hips", "full": "Full body", "mobility": "Mobility"}


def day_type(workout, date_iso, goals):
    """A short name for what kind of day a logged workout was (Legs, Core, Cardio, Recovery, Snow day…)."""
    if workout.get("type") == "snow":
        return "Snow day"
    if workout.get("day_type"):
        return workout["day_type"]
    if workout.get("cardio_type") == "recovery":
        return "Recovery"
    try:
        day = planner.day_plan(datetime.date.fromisoformat(date_iso), goals)
    except Exception:
        return "Workout"
    if day["focus"] == "cardio":
        return "Cardio"
    return THEME_SHORT.get(day.get("theme"), "Workout")


def _avg(values):
    values = [v for v in values if v is not None]
    return round(sum(values) / len(values), 1) if values else None


def trends(db_path, days, today, goals):
    """Day-by-day kidney and pelvic floor scores with that day's workout effort, plus plain-language patterns:
    how you feel the morning after hard days, after each kind of day, and which way the scores are heading."""
    since = today - datetime.timedelta(days=days - 1)
    scores = history.daily_scores(db_path, days, today)
    work = {}
    for w in history.get_history(db_path, 400):
        if w["date"] < since.isoformat():
            break
        wk = w.get("workout") or {}
        if wk.get("session") == 2:
            continue
        work.setdefault(w["date"], {"effort": w.get("rpe"), "type": day_type(wk, w["date"], goals),
                                    "sets": sum(1 for s in w["sets"] if s.get("done")),
                                    "minutes": wk.get("cardio_minutes")})
    series = []
    for i in range(days):
        d = (since + datetime.timedelta(days=i)).isoformat()
        sc, wk = scores.get(d) or {}, work.get(d) or {}
        series.append({"date": d, "kidney": sc.get("kidney"), "pf": sc.get("pelvic_floor"),
                       "effort": wk.get("effort"), "type": wk.get("type")})

    # The morning after each workout day
    after = []
    for d, wk in work.items():
        nxt = scores.get((datetime.date.fromisoformat(d) + datetime.timedelta(days=1)).isoformat())
        if nxt:
            after.append({"effort": wk["effort"] or 0, "type": wk["type"], "kidney": nxt["kidney"], "pf": nxt["pelvic_floor"]})

    notes = []
    hard = [a for a in after if a["effort"] >= 7]
    easy = [a for a in after if a["effort"] < 7]
    if len(hard) >= 2 and len(easy) >= 2:
        notes.append(f"The morning after hard sessions (effort 7+): kidney {_avg(a['kidney'] for a in hard)}, "
                     f"pelvic floor {_avg(a['pf'] for a in hard)}. After easier ones: kidney {_avg(a['kidney'] for a in easy)}, "
                     f"pelvic floor {_avg(a['pf'] for a in easy)} ({len(hard)} hard, {len(easy)} easier days).")
    by_type = {}
    for a in after:
        by_type.setdefault(a["type"], []).append(a)
    table = sorted(({"type": t, "n": len(v), "kidney": _avg(x["kidney"] for x in v), "pf": _avg(x["pf"] for x in v)}
                    for t, v in by_type.items()), key=lambda r: -r["n"])
    overall_k, overall_p = _avg(a["kidney"] for a in after), _avg(a["pf"] for a in after)
    enough = [r for r in table if r["n"] >= 2]
    for key, label, overall in (("kidney", "Kidney", overall_k), ("pf", "Pelvic floor", overall_p)):
        if len(enough) >= 2 and overall is not None:
            worst = max(enough, key=lambda r: r[key])
            if worst[key] - overall >= 0.7:
                notes.append(f"{label} is highest the morning after {worst['type']} days ({worst[key]} vs {overall} on average).")
    scored = [s for s in series if s["kidney"] is not None]
    if len(scored) >= 8:
        half = len(scored) // 2
        for key, label in (("kidney", "Kidney"), ("pf", "Pelvic floor")):
            a, b = _avg(s[key] for s in scored[:half]), _avg(s[key] for s in scored[half:])
            if a is not None and b is not None and abs(b - a) >= 0.5:
                notes.append(f"{label} scores are trending {'down' if b < a else 'up'} ({a} → {b}).")
    if not notes:
        notes.append("No clear pattern yet. A morning check-in every day makes these patterns show up sooner.")
    return {"days": days, "series": series, "notes": notes, "by_type": table,
            "averages": {"kidney": _avg(s["kidney"] for s in series), "pf": _avg(s["pf"] for s in series)}}


# --- PT visit report -----------------------------------------------------------------------------------------------


def _best(rows, hold):
    """(summary text, sort value) for one day's done sets of one exercise."""
    if hold:
        secs = max((r or 0) for _, r in rows)
        return f"{secs} s", secs
    top = max((w or 0) for w, _ in rows)
    reps = max((r or 0) for w, r in rows if (w or 0) == top)
    return (f"{top:g} lb × {reps}" if top else f"{reps} reps"), (top, reps)


def lifts(db_path, since_iso, is_hold):
    """Each exercise done since a date: sessions, first and latest (heaviest weight and its reps, or longest hold)."""
    conn = sqlite3.connect(db_path)
    rows = conn.execute("SELECT date, exercise, weight_lbs, reps FROM workout_sets WHERE done = 1 AND exercise != '' "
                        "AND date >= ? ORDER BY date, id", (since_iso,)).fetchall()
    conn.close()
    by = {}
    for d, e, w, r in rows:
        by.setdefault(e, {}).setdefault(d, []).append((w, r))
    out = []
    for name, dates in by.items():
        hold = is_hold(name)
        ds = sorted(dates)
        first, latest = _best(dates[ds[0]], hold), _best(dates[ds[-1]], hold)
        out.append({"exercise": name, "sessions": len(ds), "first": first[0], "first_date": ds[0],
                    "latest": latest[0], "latest_date": ds[-1], "better": latest[1] > first[1]})
    return sorted(out, key=lambda x: (-x["sessions"], x["exercise"]))[:30]


def pt_report(db_path, days, today, goals, warmup_names, is_hold):
    since = today - datetime.timedelta(days=days - 1)
    s_iso = since.isoformat()
    logs = [w for w in history.get_history(db_path, 400) if w["date"] >= s_iso]
    main = [w for w in logs if (w.get("workout") or {}).get("session") != 2]
    done_dates = {w["date"] for w in main}
    planned = 0
    for i in range(days):
        d = since + datetime.timedelta(days=i)
        try:
            if planner.day_plan(d, goals)["focus"] in ("strength", "cardio"):
                planned += 1
        except Exception:
            pass
    tracked = [w for w in main if "warmup_done" in (w.get("workout") or {})]
    # out of the workouts where it was on the list (a PT exercise added last week only counts from then)
    routine = [{"name": n, "done": sum(1 for w in tracked if n in w["workout"]["warmup_done"]),
                "of": sum(1 for w in tracked if n in (w["workout"].get("warmup") or warmup_names))} for n in warmup_names]
    routine = [r for r in routine if r["of"]]
    conn = sqlite3.connect(db_path)
    try:
        checkins = conn.execute("SELECT COUNT(*) FROM daily_checkins WHERE date >= ?", (s_iso,)).fetchone()[0]
    except sqlite3.OperationalError:
        checkins = 0
    conn.close()
    settings = library.load_settings()
    bothered = sorted(({"name": n, "since": p["since"], "until": p["until"],
                        "status": "sitting out" if p["until"] >= today.isoformat() else "back, going lighter"}
                       for n, p in (settings.get("paused") or {}).items() if p["until"] >= s_iso),
                      key=lambda b: b["since"])
    notes = [{"date": w["date"], "text": w["notes"].strip()} for w in logs if (w.get("notes") or "").strip()][:10]
    return {
        "days": days, "from": s_iso, "to": today.isoformat(),
        "workouts": len(done_dates), "planned": planned, "second_sessions": len(logs) - len(main),
        "snow_days": sum(1 for w in main if (w.get("workout") or {}).get("type") == "snow"),
        "checkins": checkins, "routine": routine, "routine_days": len(tracked),
        "trends": trends(db_path, days, today, goals), "lifts": lifts(db_path, s_iso, is_hold),
        "bothered": bothered, "notes": notes, "pt_exercises": settings.get("pt_exercises") or [],
        "prs": [dict(p, date=w["date"]) for w in main for p in (w.get("workout") or {}).get("prs", [])],
        # every session ever (they're every two weeks), so the first one stays the baseline
        "biofeedback": bio_results(db_path), "bio_measures": BIOFEEDBACK,
    }


# --- Pelvic floor biofeedback (manometry with the pelvic PT, about every two weeks) ------------------------------------

BIOFEEDBACK = [
    {"id": "resting", "name": "Resting tone", "unit": "pressure", "better": "lower",
     "help": "Pressure with the pelvic floor at rest. For a tight pelvic floor, lower is the goal."},
    {"id": "peak", "name": "Peak squeeze", "unit": "pressure", "better": "higher",
     "help": "Highest reading in a maximum contraction."},
    {"id": "hold", "name": "Endurance hold", "unit": "s", "better": "higher",
     "help": "How long you held a steady squeeze."},
    {"id": "relax", "name": "Time to relax after a squeeze", "unit": "s", "better": "lower",
     "help": "Seconds to drop back to resting tone."},
    {"id": "quick", "name": "Quick flicks in 10 s", "unit": "count", "better": "higher",
     "help": "Quick contract-and-let-go reps, each fully relaxed."},
    {"id": "rest_end", "name": "Resting tone at the end", "unit": "pressure", "better": "lower",
     "help": "Resting tone after the session's relaxation (down-training) work."},
]
BIO_UNITS = ["mmHg", "cmH2O", "µV"]


def bio_settings(settings=None):
    b = (settings if settings is not None else library.load_settings()).get("biofeedback") or {}
    return {"enabled": bool(b.get("enabled")), "unit": b.get("unit") if b.get("unit") in BIO_UNITS else "mmHg",
            "every_days": int(b.get("every_days") or 14), "snooze_until": b.get("snooze_until") or ""}


def bio_results(db_path):
    """[{"date", "values", "unit", "notes"}], oldest first."""
    conn = sqlite3.connect(db_path)
    try:
        rows = conn.execute("SELECT date, data, unit, notes FROM biofeedback ORDER BY date").fetchall()
    except sqlite3.OperationalError:
        rows = []
    conn.close()
    out = []
    for d, data, unit, notes in rows:
        try:
            values = json.loads(data or "{}")
        except ValueError:
            values = {}
        out.append({"date": d, "values": values, "unit": unit or "mmHg", "notes": notes or ""})
    return out


def bio_status(db_path, today):
    s = bio_settings()
    results = bio_results(db_path)
    last = results[-1]["date"] if results else None
    nxt = (datetime.date.fromisoformat(last) + datetime.timedelta(days=s["every_days"])) if last else today
    due = s["enabled"] and nxt <= today and not (s["snooze_until"] and s["snooze_until"] > today.isoformat())
    return {**s, "measures": BIOFEEDBACK, "units": BIO_UNITS, "results": results, "last": last, "next": nxt.isoformat(),
            "due": due}


def save_bio(db_path, date_iso, values, notes, unit):
    known = {m["id"] for m in BIOFEEDBACK}
    clean = {k: round(float(v), 1) for k, v in values.items() if k in known and v is not None and 0 <= float(v) <= 1000}
    if not clean and not notes.strip():
        return False
    conn = sqlite3.connect(db_path)
    conn.execute("INSERT OR REPLACE INTO biofeedback (date, data, unit, notes) VALUES (?, ?, ?, ?)",
                 (date_iso, json.dumps(clean), unit, notes.strip()[:1000]))
    conn.commit()
    conn.close()
    return True


def delete_bio(db_path, date_iso):
    conn = sqlite3.connect(db_path)
    conn.execute("DELETE FROM biofeedback WHERE date = ?", (date_iso,))
    conn.commit()
    conn.close()


# --- Ski readiness tests ---------------------------------------------------------------------------------------------

SKI_TESTS = [
    {"id": "wallsit", "name": "Wall sit", "unit": "s", "timer": 240,
     "how": "Back flat on the wall, thighs about parallel, knees over ankles. Breathe out slowly; stop when your form breaks.",
     "why": "Quad endurance for long runs."},
    {"id": "balance_l", "name": "Single-leg balance, left, eyes closed", "unit": "s", "timer": 60,
     "how": "Stand near a wall, lift the right foot, close your eyes. Stop when the foot touches down or you grab the wall.",
     "why": "Edge control and ankle reactions."},
    {"id": "balance_r", "name": "Single-leg balance, right, eyes closed", "unit": "s", "timer": 60,
     "how": "Same on the other leg.", "why": "Edge control and ankle reactions."},
    {"id": "skater", "name": "Skater steps in 30 s", "unit": "landings", "timer": 30, "count": True,
     "how": "Step or small-hop side to side, landing softly on one leg; count every landing. Step, don't hop, if your pelvic floor is above 4 today.",
     "why": "Side-to-side power and soft landings for turns."},
    {"id": "sideplank_l", "name": "Side plank, left (knees down is fine)", "unit": "s", "timer": 120,
     "how": "Elbow under shoulder, body in a line, long slow exhales. Stop when the hips sag.",
     "why": "Core that holds you steady through bumps."},
    {"id": "sideplank_r", "name": "Side plank, right (knees down is fine)", "unit": "s", "timer": 120,
     "how": "Same on the other side.", "why": "Core that holds you steady through bumps."},
]
SKI_TEST_EVERY_DAYS = 14


def ski_results(db_path):
    """[{"date", "values": {test_id: value}}], oldest first."""
    conn = sqlite3.connect(db_path)
    try:
        rows = conn.execute("SELECT date, test, value FROM ski_tests ORDER BY date").fetchall()
    except sqlite3.OperationalError:
        rows = []
    conn.close()
    by = {}
    for d, t, v in rows:
        by.setdefault(d, {})[t] = v
    return [{"date": d, "values": v} for d, v in sorted(by.items())]


def ski_status(db_path, today):
    results = ski_results(db_path)
    last = results[-1]["date"] if results else None
    nxt = (datetime.date.fromisoformat(last) + datetime.timedelta(days=SKI_TEST_EVERY_DAYS)) if last else today
    return {"tests": SKI_TESTS, "results": results, "last": last, "next": nxt.isoformat(), "due": nxt <= today,
            "every_days": SKI_TEST_EVERY_DAYS}


def save_ski_results(db_path, values, date_iso):
    known = {t["id"]: t for t in SKI_TESTS}
    clean = {k: round(float(v), 1) for k, v in values.items() if k in known and v is not None and 0 <= float(v) <= 600}
    conn = sqlite3.connect(db_path)
    for k, v in clean.items():
        conn.execute("DELETE FROM ski_tests WHERE date = ? AND test = ?", (date_iso, k))
        conn.execute("INSERT INTO ski_tests (date, test, value) VALUES (?, ?, ?)", (date_iso, k, v))
    conn.commit()
    conn.close()
    return len(clean)
