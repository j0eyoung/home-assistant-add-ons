"""Suggested weight and reps for today, from what you did last time and how it felt.

Double progression in small steps: reps climb a rep or two at a time inside the exercise's rep range (from its dose,
"2 x 10-12" -> 10 to 12), and weight goes up only once EVERY set reached the top of the range. The next weight is
one you own (your dumbbells and kettlebells, the smallest plate jump on the bar, the cable machine's step), set in
Settings > Gear details. Reps fall well short after a jump: back to the lighter weight. At your heaviest weight,
progress with reps and then a slower lowering instead.

Nothing goes up after a hard session, when your kidney or pelvic floor scores are elevated, or when the exercise
bothered you recently. The Easy week of the 4-week cycle backs off."""
import re

import library


def _median(values):
    values = sorted(values)
    return values[len(values) // 2]


HOLD_MAX_SECS = 120
DEFAULT_RANGE = (8, 12)
BIG_JUMP = 0.15            # a jump of more than 15% restarts a couple of reps lower
_RANGE = re.compile(r"(\d+)\s*[x×]\s*(\d+)(?:\s*-\s*(\d+))?", re.I)


def suggest_hold(date, sets, phase, rpe, kidney, pf, bothered=False, **_):
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
    elif bothered:
        out["note"] = f"Hold {typical} s again, or less: this bothered you recently."
    elif typical >= HOLD_MAX_SECS:
        out["note"] = f"Hold {typical} s. That's plenty: keep the quality high."
    else:
        add = 10 if phase == "Build+" else 5
        target = min(typical + add, HOLD_MAX_SECS)
        out.update(reps=target, secs=target, note=f"Hold {target} s: {target - typical} s longer than last time.")
    return out


def rep_range(dose):
    """(low, high) reps from a dose: "2 x 10-12" -> (10, 12), "3 x 8" -> (8, 8). Unknown -> 8 to 12."""
    m = _RANGE.search(dose or "")
    if not m:
        return DEFAULT_RANGE
    lo = int(m.group(2))
    hi = int(m.group(3) or lo)
    if not 3 <= lo <= hi <= 30:
        return DEFAULT_RANGE
    return lo, hi


# --- The weights you own (Settings > Gear details) ------------------------------------------------------------

DEFAULT_WEIGHTS = {"dumbbell": [5, 10, 15, 20, 25, 30, 35], "kettlebell": [15], "bar_step": 5, "cable_step": 5}
BAR_EQUIPMENT = {"barbell", "ez bar", "plates", "landmine"}
CABLE_EQUIPMENT = {"cable", "machine"}


def owned_weights():
    saved = library.load_settings().get("weights") or {}
    return {k: saved.get(k, v) for k, v in DEFAULT_WEIGHTS.items()}


def clean_weights(raw, old=None):
    """Checks what Settings sends: sorted lists of pounds for dumbbells and kettlebells, steps of 1-25 lb."""
    out = dict(old or DEFAULT_WEIGHTS)

    def nums(v):
        if isinstance(v, str):
            v = re.split(r"[,\s;]+", v)
        found = set()
        for x in v or []:
            try:
                n = round(float(x) * 2) / 2              # to the nearest half pound
            except (TypeError, ValueError):
                continue
            if 0 < n <= 300:
                found.add(int(n) if n == int(n) else n)
        return sorted(found)[:40]

    for k in ("dumbbell", "kettlebell"):
        if k in raw:
            out[k] = nums(raw[k])
    for k in ("bar_step", "cable_step"):
        if k in raw:
            try:
                out[k] = max(1, min(float(raw[k]), 25))
                out[k] = int(out[k]) if out[k] == int(out[k]) else out[k]
            except (TypeError, ValueError):
                pass
    return out


def _fmt(w):
    return f"{w:g}"


def next_weight(equipment, weight, weights=None):
    """The next weight up you can actually load, or None when you're at your heaviest."""
    weights = weights or owned_weights()
    if equipment in ("dumbbell", "kettlebell") and weights.get(equipment):
        return next((w for w in weights[equipment] if w > weight), None)
    if equipment in BAR_EQUIPMENT:
        return weight + weights["bar_step"]
    if equipment in CABLE_EQUIPMENT:
        return weight + weights["cable_step"]
    return weight + (2.5 if weight < 20 else 5)


def lighter_weight(equipment, weight, weights=None):
    """The next weight down, or None when there is nothing lighter."""
    weights = weights or owned_weights()
    if equipment in ("dumbbell", "kettlebell") and weights.get(equipment):
        return next((w for w in reversed(weights[equipment]) if w < weight), None)
    step = weights["bar_step"] if equipment in BAR_EQUIPMENT else weights["cable_step"] if equipment in CABLE_EQUIPMENT \
        else 2.5 if weight <= 20 else 5
    return weight - step if weight - step > 0 else None


def _kind(equipment):
    return {"dumbbell": "dumbbell", "kettlebell": "kettlebell"}.get(equipment, "weight")


def suggest(date, sets, phase, rpe, kidney, pf, equipment=None, dose=None, bothered=False, weights=None):
    """Dict for the exercise card, or None when this exercise has never been logged."""
    reps = [s["reps"] for s in sets if s.get("reps")]
    if not reps:
        return None
    weights_used = [s["weight"] or 0 for s in sets]
    weight = max(weights_used)
    typical = _median(reps)
    last = (f"{weight:g} lb × " if weight else "") + ", ".join(str(r) for r in reps) + (" reps" if not weight else "")
    out = {"date": date, "last": last, "weight": weight or None, "reps": typical, "sets_delta": 0}
    lo, hi = rep_range(dose)
    # reps done with the heaviest weight decide whether that weight is mastered
    top_reps = [s["reps"] for s in sets if s.get("reps") and (s["weight"] or 0) == weight] or reps

    hard = (rpe or 0) >= 8 or (kidney or 0) > 3 or (pf or 0) > 6
    if phase == "Easy week":
        out["note"] = "Easy week: same as last time, one set fewer."
        out["sets_delta"] = -1
    elif hard:
        why = "effort %s/10" % rpe if (rpe or 0) >= 8 else "kidney %s/10" % kidney if (kidney or 0) > 3 else "pelvic floor %s/10" % pf
        out["note"] = f"Hold at last time's load: your last session was tough ({why})."
    elif bothered:
        out["note"] = "Same load as last time, or lighter: this bothered you recently."
    elif not weight:
        add = 2 if phase == "Build+" else 1
        add += 1  # bodyweight moves progress a little faster
        out["reps"] = min(typical + add, 30)
        out["note"] = f"Try {out['reps']} reps: add {add} to last time's {typical}."
    elif max(top_reps) < lo - 2:
        down = lighter_weight(equipment, weight, weights)
        if down:
            out.update(weight=down, reps=lo,
                       note=f"Drop to {_fmt(down)} lb for {lo} reps: last time's reps were well under {lo}.")
        else:
            out.update(reps=lo, note=f"Stay at {_fmt(weight)} lb and aim for {lo} reps.")
    elif min(top_reps) >= hi:
        up = next_weight(equipment, weight, weights)
        if up is None:
            cap = hi + 6
            if typical < cap:
                out["reps"] = min(typical + (2 if phase == "Build+" else 1), cap)
                out["note"] = (f"{_fmt(weight)} lb is your heaviest {_kind(equipment)}: try {out['reps']} reps instead "
                               "of adding weight.")
            else:
                out["note"] = (f"{_fmt(weight)} lb is your heaviest {_kind(equipment)} and you're at {typical} reps: "
                               "slow each lowering to 3 seconds to make it harder.")
        else:
            start = lo if (up - weight) / weight <= BIG_JUMP else max(lo - 2, 5)
            out.update(weight=up, reps=start,
                       note=f"Every set reached {hi} reps: go up to {_fmt(up)} lb and start at {start} reps.")
    else:
        add = 2 if phase == "Build+" else 1
        target = min(max(typical, lo - 2) + add, hi)
        out["reps"] = target
        if typical >= hi:
            short = sum(1 for r in top_reps if r < hi)
            out["note"] = (f"Stay at {_fmt(weight)} lb: get every set to {hi} reps "
                           f"({short} set{'s' if short != 1 else ''} fell short) before adding weight.")
        else:
            out["note"] = f"Stay at {_fmt(weight)} lb and try {target} reps (up to {hi}, then the weight goes up)."
    return out
