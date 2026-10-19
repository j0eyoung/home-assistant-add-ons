"""The week view: what each day of the week is for (strength, cardio, recovery or rest), built from your sports and
your recent symptoms. Today's real workout still adapts to how you feel; the week is the intent it follows.

Pattern (Mon-Sun): strength, cardio, strength (lighter), cardio, strength, long easy cardio, rest. The coach can move
things around; changes are saved per date in settings.json."""
import datetime
import time

import library

FOCUS = ("strength", "cardio", "recovery", "rest")
LABELS = {"strength": "Strength", "cardio": "Cardio", "recovery": "Recovery", "rest": "Rest"}
DAY_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
KEEP_DAYS = 28

# weekday -> (focus, cardio slot). Slots: a = main cardio, b = second cardio, long = long easy day
PATTERN = {0: ("strength", None), 1: ("strength", None), 2: ("cardio", "a"), 3: ("strength", None),
           4: ("strength", None), 5: ("strength", None), 6: ("rest", None)}
MAX_STRENGTH_DAYS = 5
STRENGTH_WEEKDAYS = [0, 1, 3, 4, 5]


def monday(date):
    return date - datetime.timedelta(days=date.weekday())


def _cardio_type(slot, goals):
    if "triathlon" in goals:
        return {"a": "swim", "b": "run", "long": "bike"}[slot]
    return {"a": "walk", "b": "bike", "long": "walk"}[slot]


# Each strength day works a different group, and the groups shift every week so no weekday is always the same.
THEMES = ["legs", "back", "core", "hips", "full"]
THEME_LABELS = {"legs": "Legs: quads and glutes", "back": "Back and posture", "hips": "Hips and balance",
                "core": "Core activation day", "full": "Full body and core",
                "core_add": "plus core", "mobility": "plus hip and spine mobility"}
PHASES = ["Base", "Build", "Build+", "Easy week"]  # 4-week cycle; the easy week trims the extras


def week_number(date):
    return date.isocalendar()[1]


def phase(date):
    return PHASES[week_number(date) % 4]


SEASON_PHASES = {
    "Foundation": "Building a base. Keep the core work and general strength going.",
    "Ski prep": "Two leg days a week, with single-leg strength and balance.",
    "Sharpen": "Leg-heavy: quads, single-leg control and balance, the last hard weeks.",
    "Taper": "Opening week: no new leg load. Core, hips, mobility and rest.",
    "Opening day": "Ski day! Rest and fuel up.",
    "In season": "Keep legs strong with one leg day a week; ski days count as training.",
}


def season_info(today, season_iso=None):
    """{"days", "phase", "text"} for the snow season date set in Settings, or None."""
    season_iso = season_iso if season_iso is not None else (library.load_settings().get("season_start") or "")
    try:
        opening = datetime.date.fromisoformat(season_iso)
    except ValueError:
        return None
    days = (opening - today).days
    if days > 56:
        name = "Foundation"
    elif days > 14:
        name = "Ski prep"
    elif days > 3:
        name = "Sharpen"
    elif days > 0:
        name = "Taper"
    elif days == 0:
        name = "Opening day"
    elif days > -150:
        name = "In season"
    else:
        return None
    return {"days": days, "phase": name, "text": SEASON_PHASES[name], "opening": opening.isoformat()}


def theme_for(date, focus, goals=()):
    if focus == "strength":
        # position among the week's strength days, shifted each week so a weekday is not always the same group
        pos = STRENGTH_WEEKDAYS.index(date.weekday()) if date.weekday() in STRENGTH_WEEKDAYS else date.weekday() % 5
        theme = THEMES[(pos + week_number(date)) % len(THEMES)]
        snow = {"skiing", "snowboarding"} & set(goals)
        season = season_info(date) if snow else None
        if season:
            p = season["phase"]
            if p in ("Ski prep", "Sharpen") and theme == "full":
                theme = "legs"                       # a second leg day in the build-up
            elif p in ("Taper", "Opening day") and theme in ("legs", "full"):
                theme = "core"                       # no new leg load in opening week
            elif p == "In season" and theme == "full":
                theme = "hips"
        return theme
    if focus == "cardio":
        return "core_add" if (date.weekday() // 2 + week_number(date)) % 2 == 0 else "mobility"
    return None


def _base(date, goals):
    focus, slot = PATTERN[date.weekday()]
    day = {"focus": focus, "cardio_type": None, "cardio_minutes": None}
    if slot:
        # Only the type is planned; today's engine works out the minutes from how your last sessions went
        day["cardio_type"] = _cardio_type(slot, goals)
        day["long"] = slot == "long"
    return day


def overrides():
    return library.load_settings().get("week_overrides") or {}


# --- Skipped days: the rest of this week is re-planned ----------------------------------------------------------

THEME_PRIORITY = ["core", "legs", "back", "hips", "full"]   # core activation first: it is the weakest area
_ctx = {"today": None, "done": None, "snow": None, "machines": None, "cache": (0.0, None, None), "mcache": (0.0, None)}


def set_context(today_fn, done_fn, snow_fn=None, machines_fn=None):
    """The app tells the planner what 'today' is, which dates have a logged workout, which were snow days and which
    cardio machines are unlocked (readiness.status)."""
    _ctx["today"], _ctx["done"], _ctx["snow"], _ctx["machines"] = today_fn, done_fn, snow_fn, machines_fn


def machines():
    """Unlocked cardio machines, cached for a few seconds (the week view asks many times per request)."""
    if not _ctx["machines"]:
        return {}
    stamp, cached = _ctx["mcache"]
    if cached is not None and time.time() - stamp < 5:
        return cached
    try:
        result = _ctx["machines"]()
    except Exception:
        result = {}
    _ctx["mcache"] = (time.time(), result)
    return result


def replan_map(goals):
    """{"themes": {date: theme}, "missed": [...], "dropped": [...]} for this week, or {} when nothing was skipped.

    Strength days that passed without a logged workout are moved into the strength days still ahead (this week only),
    core first. A week keeps its rest day and its 5-strength-day limit, so if there is no room the lowest-priority
    group is dropped. Opening week (taper) is left alone."""
    if not _ctx["today"]:
        return {}
    now = time.time()
    stamp, key, cached = _ctx["cache"]
    today = _ctx["today"]()
    k = (today.isoformat(), tuple(goals))
    if key == k and now - stamp < 5:
        return cached
    result = _replan(today, goals)
    _ctx["cache"] = (now, k, result)
    return result


def _replan(today, goals):
    snow = {"skiing", "snowboarding"} & set(goals)
    season = season_info(today) if snow else None
    if season and season["phase"] in ("Taper", "Opening day"):
        return {}
    done = _ctx["done"]()
    start = monday(today)
    missed, upcoming = [], []
    for i in range(7):
        d = start + datetime.timedelta(days=i)
        day = _day_plan_base(d, goals)
        if day["focus"] != "strength":
            continue
        if d < today:
            if d.isoformat() not in done:
                missed.append(day["theme"])
        elif d.isoformat() not in done and not day.get("changed"):
            upcoming.append((d, day["theme"]))
    if not missed or not upcoming:
        return {}
    first = [t for t in THEME_PRIORITY if t in missed][:len(upcoming)]
    original = [t for _, t in upcoming]
    room = len(upcoming) - len(first)
    rest = [t for t in original if t not in first]
    # when there is no room for everything, the lowest-priority groups are the ones left out
    kept = set(sorted(rest, key=THEME_PRIORITY.index)[:room])
    order = first + [t for t in rest if t in kept]
    dropped = [t for t in THEME_PRIORITY if (t in missed or t in original) and t not in order]
    themes = {d.isoformat(): order[i] for i, (d, _) in enumerate(upcoming)}
    return {"themes": themes, "missed": first, "dropped": dropped}


def day_plan(date, goals):
    """Plan for one date: the pattern, any change the coach made, and the re-plan after a skipped day."""
    day = _day_plan_base(date, goals)
    if day["focus"] == "strength":
        rp = replan_map(goals)
        theme = (rp.get("themes") or {}).get(date.isoformat())
        if theme and theme != day["theme"]:
            day["theme"], day["theme_label"] = theme, THEME_LABELS[theme]
            day["replanned"] = True
        # the day after skiing or snowboarding, the legs get a break: core instead
        if day["theme"] in ("legs", "full") and _ctx["snow"]:
            yesterday = (date - datetime.timedelta(days=1)).isoformat()
            if yesterday in _ctx["snow"]():
                day["theme"], day["theme_label"] = "core", THEME_LABELS["core"]
                day["after_snow"] = True
    if day["focus"] == "cardio" and not day.get("changed") and "triathlon" not in goals:
        # Peloton and rower come back once your scores unlock them (readiness.py); they rotate with walking
        st = machines()
        unlocked = [m for m in ("bike", "row") if (st.get(m) or {}).get("ok")]
        if unlocked:
            options = unlocked + ["walk"]
            choice = options[(week_number(date) + date.weekday()) % len(options)]
            day["cardio_type"] = choice
            if choice in unlocked:
                day["cardio_minutes"] = st[choice]["minutes"]
                day["machine"] = st[choice]["name"]
    return day


def _day_plan_base(date, goals):
    """Plan for one date without the skipped-day re-plan."""
    day = _base(date, goals)
    ov = overrides().get(date.isoformat())
    if ov:
        day.update({k: v for k, v in ov.items() if k in ("focus", "cardio_type", "cardio_minutes", "note")})
        day["changed"] = True
        if day["focus"] in ("rest", "recovery"):
            day["cardio_type"], day["cardio_minutes"] = None, None
        elif day["focus"] == "cardio" and not day["cardio_type"]:
            base = _base(date, goals)
            day["cardio_type"] = base["cardio_type"] or _cardio_type("a", goals)
    day["theme"] = theme_for(date, day["focus"], goals)
    day["theme_label"] = THEME_LABELS.get(day["theme"]) if day["theme"] else None
    day["phase"] = phase(date)
    snow = {"skiing", "snowboarding"} & set(goals)
    season = season_info(date) if snow else None
    day["season_phase"] = season["phase"] if season else None
    # the last days before opening day are easy whatever the cycle says
    if season and season["phase"] in ("Taper", "Opening day") and day["focus"] == "cardio":
        day["theme"], day["theme_label"] = "mobility", THEME_LABELS["mobility"]
    if season and season["phase"] == "Opening day" and not day.get("changed"):
        day.update(focus="rest", cardio_type=None, cardio_minutes=None, theme=None, theme_label=None)
    return day


def mind_suggestion(focus):
    return {"strength": "8-minute yoga cool-down after your sets",
            "cardio": "Baduanjin qigong or breathing practice afterwards",
            "recovery": "Gentle yoga and a guided meditation",
            "rest": "Optional: a short yoga flow, qigong or a meditation"}[focus]


def week(start, today, goals, done_dates):
    """Seven days from `start` (a Monday), each with a status: done, today, missed or upcoming."""
    days = []
    for i in range(7):
        d = start + datetime.timedelta(days=i)
        plan = day_plan(d, goals)
        if d.isoformat() in done_dates:
            status = "done"
        elif d == today:
            status = "today"
        elif d < today:
            status = "missed" if plan["focus"] not in ("rest",) else "past"
        else:
            status = "upcoming"
        days.append({"date": d.isoformat(), "weekday": DAY_NAMES[d.weekday()], "label": LABELS[plan["focus"]],
                     "mind": mind_suggestion(plan["focus"]), "status": status, **plan})
    return days


# --- Saving the coach's changes -------------------------------------------------------------------------------

def save_changes(changes):
    all_ov = overrides()
    for c in changes:
        entry = {"focus": c["focus"], "note": c.get("why", "")}
        if c["focus"] == "cardio":
            entry.update(cardio_type=c.get("type"), cardio_minutes=c.get("minutes"))
        all_ov[c["date"]] = entry
    for old in sorted(all_ov)[:-KEEP_DAYS]:
        all_ov.pop(old, None)
    library.save_settings({"week_overrides": all_ov})


def clear_week(start):
    all_ov = overrides()
    for i in range(14):
        all_ov.pop((start + datetime.timedelta(days=i)).isoformat(), None)
    library.save_settings({"week_overrides": all_ov})
