"""Lets the coach change today's plan, safely.

The coach (a headless Claude CLI that cannot run tools) may end a reply with a fenced `plan-changes` block. The app
never trusts it: every change is checked here against the exercise library and the safety rules, shown to Joe as
Apply / No thanks, and only then saved for that day. Recovery days (kidney flank above 5) stay recovery days."""
import datetime
import difflib
import json
import re

import library
from engine import CARDIO_MAX_MINUTES, CARDIO_TEXT

BLOCK = re.compile(r"```\s*plan-changes\s*(\{.*?\})\s*```", re.S)
MAX_CHANGES = 6
KEEP_DAYS = 14

INSTRUCTIONS = (
    "CHANGING TODAY'S PLAN: you may propose changes, and Joe will be asked to approve them. To do so, end your reply with "
    'one fenced block exactly like this (use only the operations you need):\n'
    '```plan-changes\n{"changes": [{"op": "add", "name": "Exercise name", "why": "short reason"}, '
    '{"op": "remove", "name": "Exercise name in today\'s plan"}, '
    '{"op": "cardio", "type": "bike", "minutes": 25, "why": "short reason"}, '
    '{"op": "extra_cardio", "type": "walk", "minutes": 20, "why": "a second, easy session later in the day"}]}\n```\n'
    'To change a day in the weekly plan use {"op": "day", "date": "YYYY-MM-DD", "focus": "strength|cardio|recovery|rest", '
    '"type": "swim|bike|run|walk", "minutes": 30, "why": "short reason"} (type and minutes only for cardio days; dates from today '
    "to 13 days ahead; each week keeps at least one rest or recovery day and at most 5 strength days). "
    "Rules: at most 6 changes; exercise names must come from today's plan or the SAFE EXERCISES list below, spelled exactly; "
    "cardio type is one of recovery, swim, bike, run, walk; on a recovery day change nothing except adding gentle mobility; "
    "never raise cardio by more than 10 minutes. Explain the reason in your reply too. If you do not want to change the plan, "
    "do not include the block."
)


def extract(reply, pattern=BLOCK):
    """(reply without the block, parsed block or None)."""
    if not reply:
        return reply, None
    m = pattern.search(reply)
    if not m:
        return reply, None
    clean = (reply[:m.start()] + reply[m.end():]).strip()
    try:
        return clean, json.loads(m.group(1))
    except ValueError:
        return clean, None


# --- A 4-week block: the coach plans every day of the next four weeks, Joe applies it in one tap --------------

PLAN_BLOCK = re.compile(r"```\s*plan-block\s*(\{.*?\})\s*```", re.S)
ASKS_FOR_BLOCK = re.compile(r"\b(4|four)[- ]?weeks?\b|\bblock\b|\bmonth\b|\bnext few weeks\b|\bmesocycle\b", re.I)
DAY_LABELS = {"legs": "Legs", "back": "Back", "core": "Core", "hips": "Hips", "full": "Full body"}


def block_instructions(today):
    import planner
    this_monday = planner.monday(today)
    return (
        "PLANNING A 4-WEEK BLOCK: when Joe asks for a plan for the next few weeks, you may end your reply with one fenced "
        "block like this instead of plan-changes:\n"
        '```plan-block\n{"start": "YYYY-MM-DD", "goal": "one line: what these four weeks build toward", "weeks": [\n'
        ' {"phase": "Base", "focus": "one short line for the week", "days": ["strength:legs", "strength:core", '
        '"cardio:walk:30", "strength:back", "strength:hips", "strength:full", "rest"]},\n'
        " ... exactly 4 weeks]}\n```\n"
        f"start is a Monday: {this_monday.isoformat()} (this week) or "
        f"{(this_monday + datetime.timedelta(days=7)).isoformat()} (next week). "
        "days lists Monday to Sunday, each one of: strength:legs, strength:back, strength:core, strength:hips, "
        f"strength:full, cardio:<walk|bike|run|swim|row>:<minutes 5-{CARDIO_MAX_MINUTES}>, recovery, rest. "
        "Every week keeps at least one rest or recovery day and at most 5 strength days. phase is Base, Build, Build+ or "
        "Easy week: include at least one Easy week (usually the last) and never two Build+ weeks in a row. bike = Peloton, "
        "row = water rower: while one is locked its days are walked instead. The exercises, sets and weights are still "
        "picked each day from his morning check-in, and a high kidney score still turns any day into recovery, so plan "
        "the shape of the weeks, not the exercises. Explain the plan briefly in your reply."
    )


def _parse_day(raw, goals):
    """A block day from the coach ("strength:legs", "cardio:walk:30", "rest") or from the page (a dict)."""
    import planner
    if isinstance(raw, dict):
        focus, theme, ctype, minutes = raw.get("focus"), raw.get("theme"), raw.get("cardio_type"), raw.get("cardio_minutes")
    else:
        parts = [p.strip().lower() for p in str(raw or "").split(":")]
        focus = parts[0]
        theme = parts[1] if focus == "strength" and len(parts) > 1 else None
        ctype = parts[1] if focus == "cardio" and len(parts) > 1 else None
        minutes = parts[2] if focus == "cardio" and len(parts) > 2 else None
    if focus in ("rest", "recovery"):
        return {"focus": focus}
    if focus == "strength":
        return {"focus": "strength", "theme": theme} if theme in planner.THEMES else None
    if focus == "cardio":
        if ctype not in CARDIO_TEXT or ctype == "recovery":
            return None
        if minutes in (None, ""):
            return {"focus": "cardio", "cardio_type": ctype, "cardio_minutes": None}   # the engine picks the minutes
        try:
            minutes = int(minutes)
        except (TypeError, ValueError):
            return None
        if not 5 <= minutes <= CARDIO_MAX_MINUTES:
            return None
        return {"focus": "cardio", "cardio_type": ctype, "cardio_minutes": minutes}
    return None


def _usual_day(d, goals):
    """The normal pattern for a date (ignoring any block), used when a proposed day or week isn't allowed."""
    import planner
    base = planner._base(d, goals)
    if base["focus"] == "strength":
        return {"focus": "strength", "theme": planner.theme_for(d, "strength", goals)}
    if base["focus"] == "cardio":
        return {"focus": "cardio", "cardio_type": base["cardio_type"], "cardio_minutes": None}
    return {"focus": base["focus"]}


def day_label(day):
    if day["focus"] == "strength":
        return DAY_LABELS.get(day.get("theme"), "Strength")
    if day["focus"] == "cardio":
        name = {"walk": "Walk", "bike": "Peloton", "row": "Rower", "run": "Run", "swim": "Swim"}.get(day["cardio_type"], "Cardio")
        return f"{name} {day['cardio_minutes']} min" if day.get("cardio_minutes") else name
    return day["focus"].capitalize()


def validate_block(data, today, goals, machines=None):
    """(block ready to save, or None, and reasons for anything changed or refused). Nothing the coach sends is trusted:
    a day that isn't allowed falls back to the usual plan, a week without a rest day or with more than 5 strength days
    keeps the usual week, and every block gets an Easy week."""
    import planner
    data = data or {}
    notes = []
    try:
        start = planner.monday(datetime.date.fromisoformat(str(data.get("start"))))
    except ValueError:
        return None, ["The 4-week plan had no start date, so it was skipped."]
    this_monday = planner.monday(today)
    if start not in (this_monday, this_monday + datetime.timedelta(days=7)):
        return None, [f"A 4-week plan has to start this week or next, not {start:%b %d}."]
    weeks_in = data.get("weeks") or []
    if len(weeks_in) != planner.BLOCK_WEEKS:
        return None, [f"The plan had {len(weeks_in)} weeks instead of 4, so it was skipped."]
    weeks, days_out = [], {}
    for i, w in enumerate(weeks_in):
        w = w if isinstance(w, dict) else {}
        wstart = start + datetime.timedelta(days=7 * i)
        phase = w.get("phase") if w.get("phase") in planner.PHASES else None
        if not phase:
            phase = planner.PHASES[planner.week_number(wstart) % 4]
            notes.append(f"Week {i + 1} had no valid phase, so it follows the usual cycle ({phase}).")
        raw_days = w.get("days") if isinstance(w.get("days"), list) else []
        days = []
        for j in range(7):
            d = wstart + datetime.timedelta(days=j)
            day = _parse_day(raw_days[j], goals) if j < len(raw_days) else None
            if day is None:
                day = _usual_day(d, goals)
                notes.append(f"{d:%a %b %d} wasn't a day the plan allows, so it keeps the usual plan.")
            days.append(day)
        focuses = [x["focus"] for x in days]
        if not any(f in ("rest", "recovery") for f in focuses) or focuses.count("strength") > planner.MAX_STRENGTH_DAYS:
            days = [_usual_day(wstart + datetime.timedelta(days=j), goals) for j in range(7)]
            notes.append(f"Week {i + 1} needs a rest or recovery day and at most 5 strength days, so it keeps the usual week.")
        weeks.append({"phase": phase, "focus": str(w.get("focus") or "")[:160], "start": wstart.isoformat()})
        for j, day in enumerate(days):
            days_out[(wstart + datetime.timedelta(days=j)).isoformat()] = day
    for i in range(1, len(weeks)):
        if weeks[i]["phase"] == "Build+" and weeks[i - 1]["phase"] == "Build+":
            weeks[i]["phase"] = "Build"
            notes.append(f"Week {i + 1} is Build instead of a second Build+ in a row.")
    if not any(w["phase"] == "Easy week" for w in weeks):
        weeks[-1]["phase"] = "Easy week"
        notes.append("Week 4 is an Easy week: every block needs one.")
    locked = [m for m, st in (machines or {}).items() if not st.get("ok")]
    if any(d.get("cardio_type") in locked for d in days_out.values()):
        names = ", ".join(sorted({(machines[m] or {}).get("name", m) for m in locked
                                  if any(d.get("cardio_type") == m for d in days_out.values())}))
        notes.append(f"{names}: locked for now, so those days are walked until it unlocks.")
    # days already gone keep what they were: changing them would count as skipped days and re-plan the week
    days_out = {k: v for k, v in days_out.items() if k >= today.isoformat()}
    block = {"start": start.isoformat(), "goal": str(data.get("goal") or "")[:200], "weeks": weeks, "days": days_out,
             "created": today.isoformat()}
    return block, notes


def block_preview(block, goals=()):
    """The block as the page shows it: four weeks of seven labelled days."""
    import planner
    out = {"start": block["start"], "goal": block["goal"], "weeks": []}
    for w in block["weeks"]:
        wstart = datetime.date.fromisoformat(w["start"])
        days = []
        for j in range(7):
            d = wstart + datetime.timedelta(days=j)
            day = block["days"].get(d.isoformat()) or _usual_day(d, goals)
            days.append({**day, "date": d.isoformat(), "weekday": planner.DAY_NAMES[j], "label": day_label(day)})
        out["weeks"].append({**w, "days": days})
    return out


def block_context(today):
    """One line per week of the current block, for the coach."""
    import planner
    b = planner.block(today)
    if not b:
        return "No 4-week block is planned; the usual Base/Build/Build+/Easy cycle applies."
    lines = [f"CURRENT 4-WEEK BLOCK (goal: {b.get('goal') or 'not given'}):"]
    for i, w in enumerate(b["weeks"]):
        wstart = datetime.date.fromisoformat(w["start"])
        days = [day_label(b["days"].get((wstart + datetime.timedelta(days=j)).isoformat())
                          or _usual_day(wstart + datetime.timedelta(days=j), ()))
                for j in range(7)]
        lines.append(f"Week {i + 1} from {wstart:%Y-%m-%d}, {w['phase']}: {w.get('focus') or ''} [{', '.join(days)}]")
    return "\n".join(lines)


def _resolve(name, by_name):
    """Library entry for a name the coach wrote (exact, case-insensitive, then a close match)."""
    if not name:
        return None
    lower = {n.lower(): n for n in by_name}
    key = lower.get(str(name).strip().lower())
    if key is None:
        close = difflib.get_close_matches(str(name).strip().lower(), list(lower), n=1, cutoff=0.88)
        key = lower[close[0]] if close else None
    return by_name[key] if key else None


def validate(data, plan, by_name, equipment):
    """(changes that are allowed, reasons for the ones that are not)."""
    allowed, rejected = [], []
    recovery = plan.get("cardio_type") == "recovery"
    in_plan = {n.lower(): n for n in plan.get("strength", [])}
    equipment = set(equipment or []) | {"bodyweight"}
    for op in ((data or {}).get("changes") or [])[:MAX_CHANGES]:
        kind = op.get("op")
        why = str(op.get("why") or "")[:160]
        if kind == "add":
            e = _resolve(op.get("name"), by_name)
            if not e:
                rejected.append(f"'{op.get('name')}' isn't in the exercise library.")
            elif not e["safe"]:
                rejected.append(f"{e['name']} is filtered out for your kidney or pelvic floor.")
            elif e["equipment"] not in equipment:
                rejected.append(f"{e['name']} needs {e['equipment']}, which isn't in your equipment list.")
            elif recovery and "mobility" not in e["goal_tags"]:
                rejected.append(f"{e['name']} isn't gentle mobility, and today is a recovery day.")
            elif e["name"].lower() in in_plan:
                continue  # already in the plan
            else:
                allowed.append({"op": "add", "name": e["name"], "why": why})
                in_plan[e["name"].lower()] = e["name"]
        elif kind == "remove":
            name = in_plan.get(str(op.get("name") or "").strip().lower())
            if name:
                allowed.append({"op": "remove", "name": name, "why": why})
                in_plan.pop(name.lower(), None)
            else:
                rejected.append(f"'{op.get('name')}' isn't in today's plan.")
        elif kind == "cardio":
            ctype, current = op.get("type"), plan.get("cardio_minutes") or 0
            try:
                minutes = int(op.get("minutes"))
            except (TypeError, ValueError):
                rejected.append("The cardio change didn't have a number of minutes.")
                continue
            if ctype not in CARDIO_TEXT:
                rejected.append(f"'{ctype}' isn't a cardio type the app uses.")
            elif recovery and ctype != "recovery":
                rejected.append("Today is a recovery day, so cardio stays easy recovery.")
            elif not 5 <= minutes <= CARDIO_MAX_MINUTES:
                rejected.append(f"{minutes} minutes is outside the safe range (5-{CARDIO_MAX_MINUTES}).")
            elif ctype == plan.get("cardio_type") and minutes > current + 10:
                rejected.append(f"Cardio can go up by at most 10 minutes at once (now {current}).")
            else:
                allowed.append({"op": "cardio", "type": ctype, "minutes": minutes, "why": why})
        elif kind == "extra_cardio":
            ctype = op.get("type")
            try:
                minutes = int(op.get("minutes"))
            except (TypeError, ValueError):
                rejected.append("The second cardio session didn't have a number of minutes.")
                continue
            if ctype not in CARDIO_TEXT or ctype == "recovery":
                rejected.append(f"'{ctype}' isn't a cardio type the app uses.")
            elif recovery and ctype not in ("walk", "swim"):
                rejected.append("Today is a recovery day, so a second cardio session can only be an easy walk or swim.")
            elif not 5 <= minutes <= 30:
                rejected.append("A second cardio session can be 5 to 30 minutes.")
            else:
                allowed.append({"op": "extra_cardio", "type": ctype, "minutes": minutes, "why": why})
        else:
            rejected.append("An unknown change was skipped.")
    return allowed, rejected


def validate_days(ops, today, goals):
    """Week-plan changes: {"op": "day", "date": "2026-10-10", "focus": "rest"|"recovery"|"strength"|"cardio", ...}.
    Allowed for today and the next 13 days; every week must keep at least one rest or recovery day and at most 5
    strength days, and cardio stays within 5-45 minutes."""
    import planner
    allowed, rejected = [], []
    focus_by_date = {}
    for op in ops[:MAX_CHANGES]:
        try:
            d = datetime.date.fromisoformat(str(op.get("date")))
        except ValueError:
            rejected.append(f"'{op.get('date')}' isn't a date the week plan can change.")
            continue
        focus = op.get("focus")
        if not 0 <= (d - today).days <= 13:
            rejected.append(f"{d:%a %b %d} is outside the next two weeks.")
        elif focus not in planner.FOCUS:
            rejected.append(f"'{focus}' isn't a day type (strength, cardio, recovery or rest).")
        else:
            entry = {"op": "day", "date": d.isoformat(), "focus": focus, "why": str(op.get("why") or "")[:160]}
            if focus == "cardio":
                ctype = op.get("type") or planner.day_plan(d, goals)["cardio_type"] or ("swim" if "triathlon" in goals else "walk")
                try:
                    minutes = int(op.get("minutes") or planner.day_plan(d, goals)["cardio_minutes"] or 20)
                except (TypeError, ValueError):
                    rejected.append("The cardio day didn't have a number of minutes.")
                    continue
                if ctype not in CARDIO_TEXT or ctype == "recovery" or not 5 <= minutes <= CARDIO_MAX_MINUTES:
                    rejected.append(f"Cardio on {d:%a %b %d} needs a type (swim, bike, run, walk) and 5-{CARDIO_MAX_MINUTES} minutes.")
                    continue
                entry.update(type=ctype, minutes=minutes)
            allowed.append(entry)
            focus_by_date[d] = focus
    # every affected week keeps at least one rest/recovery day and no more than 5 strength days
    weeks = {planner.monday(d) for d in focus_by_date}
    for start in weeks:
        days = [start + datetime.timedelta(days=i) for i in range(7)]
        focuses = [focus_by_date.get(d) or planner.day_plan(d, goals)["focus"] for d in days]
        if not any(f in ("rest", "recovery") for f in focuses) or focuses.count("strength") > planner.MAX_STRENGTH_DAYS:
            bad = {d for d in focus_by_date if planner.monday(d) == start}
            allowed = [c for c in allowed if datetime.date.fromisoformat(c["date"]) not in bad]
            rejected.append(f"The week of {start:%b %d} needs at least one rest or recovery day and at most 5 strength days.")
    return allowed, rejected


def label(c):
    if c["op"] == "day":
        d = datetime.date.fromisoformat(c["date"])
        extra = f" ({c['minutes']} min {c['type']})" if c["focus"] == "cardio" else ""
        return f"{d:%a %b %d}: {c['focus']}{extra}"
    if c["op"] == "extra_cardio":
        return f"Second session: {c['minutes']} min easy {c['type']}"
    if c["op"] == "add":
        return f"Add {c['name']}"
    if c["op"] == "remove":
        return f"Remove {c['name']}"
    return f"Cardio: {c['minutes']} min {c['type']}"


# --- Saved per day, in settings.json so they survive updates --------------------------------------------------

def overrides_for(date):
    return (library.load_settings().get("plan_overrides") or {}).get(date, {}).get("changes", [])


def session2_names(date):
    """Exercises added as a second session today (their reason starts with 'second session')."""
    return [c["name"] for c in overrides_for(date) if c.get("op") == "add" and str(c.get("why", "")).startswith("second session")]


def save(date, changes):
    all_ov = library.load_settings().get("plan_overrides") or {}
    existing = all_ov.get(date, {}).get("changes", [])
    all_ov[date] = {"changes": existing + changes}
    for old in sorted(all_ov)[:-KEEP_DAYS]:
        all_ov.pop(old, None)
    library.save_settings({"plan_overrides": all_ov})


def clear(date):
    all_ov = library.load_settings().get("plan_overrides") or {}
    if all_ov.pop(date, None) is not None:
        library.save_settings({"plan_overrides": all_ov})


def apply(workout, changes):
    """Today's workout with the approved changes folded in."""
    for c in changes:
        if c["op"] == "add" and c["name"] not in workout["strength"]:
            workout["strength"].append(c["name"])
            workout.setdefault("accessories", []).append(
                {"name": c["name"], "why": "Added by your coach" + (f": {c['why']}" if c.get("why") else "")})
        elif c["op"] == "remove" and c["name"] in workout["strength"]:
            workout["strength"].remove(c["name"])
            workout["accessories"] = [a for a in workout.get("accessories", []) if a["name"] != c["name"]]
        elif c["op"] == "extra_cardio":
            workout["extra_cardio"] = {"type": c["type"], "minutes": c["minutes"], "text": CARDIO_TEXT[c["type"]],
                                       "note": "Second session" + (f": {c['why']}" if c.get("why") else "")}
        elif c["op"] == "cardio":
            workout["cardio_type"], workout["cardio_minutes"] = c["type"], c["minutes"]
            workout["cardio"] = (f"{c['minutes']} min: {CARDIO_TEXT[c['type']]}. "
                                 "Easy pace (you can talk in full sentences); the first 5 min are your warm-up.")
            workout["cardio_note"] = "Changed by your coach" + (f": {c['why']}" if c.get("why") else ".")
    return workout


# --- What the coach is told -----------------------------------------------------------------------------------

def week_context(today, goals):
    import planner
    lines = ["THIS WEEK AND NEXT (weekly plan; today is " + today.strftime("%a %Y-%m-%d") + "):"]
    for start in (planner.monday(today), planner.monday(today) + datetime.timedelta(days=7)):
        for i in range(7):
            d = start + datetime.timedelta(days=i)
            p = planner.day_plan(d, goals)
            cardio = f" {p['cardio_minutes']} min {p['cardio_type']}" if p["cardio_type"] else ""
            group = f" [{p['theme_label']}]" if p.get("theme_label") and p["focus"] == "strength" else ""
            lines.append(f"{d:%a %Y-%m-%d}: {p['focus']}{group}{cardio}")
    return "\n".join(lines)


def context(plan, entries, equipment, goals, per_tag=10):
    """Today's plan and a short list of safe exercises the coach may propose (names must match exactly)."""
    equipment = set(equipment or []) | {"bodyweight"}
    safe = [e for e in entries if e["safe"] and e["equipment"] in equipment and e["images"]]
    lines = ["TODAY'S PLAN (what Joe will do):",
             "Strength and extras: " + "; ".join(plan.get("strength", [])),
             f"Cardio: {plan.get('cardio_minutes')} min, type {plan.get('cardio_type')}",
             "Recovery day: " + ("YES (change nothing except gentle mobility)" if plan.get("cardio_type") == "recovery" else "no"),
             "Active sports and goals: " + (", ".join(goals) or "general fitness"),
             "", "SAFE EXERCISES you may add (already screened for his kidney and pelvic floor):"]
    snow = {"skiing", "snowboarding"} & set(goals)
    tags = (["legs", "balance", "core", "mobility", "upper back"] if snow else ["legs", "core", "mobility", "upper back"])
    for tag in tags:
        names = sorted(e["name"] for e in safe if tag in e["goal_tags"])[:400]
        step = max(1, len(names) // per_tag)
        lines.append(f"{tag}: " + "; ".join(names[::step][:per_tag]))
    return "\n".join(lines)
