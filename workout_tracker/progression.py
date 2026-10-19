"""Suggested weight and reps for today, from what you did last time and how it felt.

Small steps only: a rep or two at a time, weight only once you reach 12 reps, and nothing goes up after a hard
session or when your kidney or pelvic floor scores are elevated. The Easy week of the 4-week cycle backs off."""


def _median(values):
    values = sorted(values)
    return values[len(values) // 2]


HOLD_MAX_SECS = 120


def suggest_hold(date, sets, phase, rpe, kidney, pf):
    """Timed holds: seconds held last time (stored in the reps column) and today's target, a few seconds longer."""
    secs = [s["reps"] for s in sets if s.get("reps")]
    if not secs:
        return None
    typical = _median(secs)
    out = {"date": date, "last": ", ".join(f"{s} s" for s in secs), "weight": None, "reps": typical, "secs": typical,
           "sets_delta": 0}
    hard = (rpe or 0) >= 8 or (kidney or 0) > 3 or (pf or 0) > 6
    if phase == "Easy week":
        out["note"] = f"Easy week: hold {typical} s again, one hold fewer."
        out["sets_delta"] = -1
    elif hard:
        out["note"] = f"Hold {typical} s again: your last session was tough."
    elif typical >= HOLD_MAX_SECS:
        out["note"] = f"Hold {typical} s. That's plenty: keep the quality high."
    else:
        add = 10 if phase == "Build+" else 5
        target = min(typical + add, HOLD_MAX_SECS)
        out.update(reps=target, secs=target, note=f"Hold {target} s: {target - typical} s longer than last time.")
    return out


def suggest(date, sets, phase, rpe, kidney, pf):
    """Dict for the exercise card, or None when this exercise has never been logged."""
    reps = [s["reps"] for s in sets if s.get("reps")]
    if not reps:
        return None
    weights = [s["weight"] or 0 for s in sets]
    weight = max(weights)
    typical = _median(reps)
    last = (f"{weight:g} lb × " if weight else "") + ", ".join(str(r) for r in reps) + (" reps" if not weight else "")
    out = {"date": date, "last": last, "weight": weight or None, "reps": typical, "sets_delta": 0}

    hard = (rpe or 0) >= 8 or (kidney or 0) > 3 or (pf or 0) > 6
    if phase == "Easy week":
        out["note"] = "Easy week: same as last time, one set fewer."
        out["sets_delta"] = -1
    elif hard:
        why = "effort %s/10" % rpe if (rpe or 0) >= 8 else "kidney %s/10" % kidney if (kidney or 0) > 3 else "pelvic floor %s/10" % pf
        out["note"] = f"Hold at last time's load: your last session was tough ({why})."
    elif weight and typical >= 12:
        step = 2.5 if weight < 20 else 5
        out.update(weight=weight + step, reps=8, note=f"Add {step:g} lb and start back at 8 reps: you reached 12 last time.")
    else:
        add = 2 if phase == "Build+" else 1
        if not weight:
            add += 1  # bodyweight moves progress a little faster
        out["reps"] = min(typical + add, 30)
        out["note"] = f"Try {out['reps']} reps: add {add} to last time's {typical}."
    return out
