"""Who to reach out to next.

Overdue score = days since you last talked / the friend's target interval. A friend is due at 1.0 or more.
The list is ranked highest score first; a birthday today jumps to the front of the queue.
Pure functions over plain dicts (rows of the friends table), so they are easy to test."""
import datetime

TIERS = {
    "close": {"label": "Close", "days": 14},
    "good": {"label": "Good", "days": 30},
    "casual": {"label": "Casual", "days": 90},   # every 3 months
}
TIER_ORDER = {"close": 0, "good": 1, "casual": 2}
SNOOZE_DAYS = 3        # Snooze: ask again in a few days


def _date(s):
    return datetime.date.fromisoformat(str(s)[:10])


def interval(f):
    """Target days between contacts: the friend's own override, else the tier's."""
    try:
        d = int(f.get("interval_days") or 0)
    except (TypeError, ValueError):
        d = 0
    return d if d > 0 else TIERS.get(f.get("tier"), TIERS["good"])["days"]


def parse_birthday(s):
    """'MM-DD' or 'YYYY-MM-DD' -> (month, day), or None when empty or invalid."""
    s = str(s or "").strip()
    if not s:
        return None
    parts = s.split("-")
    try:
        if len(parts) == 3:
            datetime.date(int(parts[0]), int(parts[1]), int(parts[2]))
            m, d = int(parts[1]), int(parts[2])
        elif len(parts) == 2:
            m, d = int(parts[0]), int(parts[1])
            datetime.date(2000, m, d)            # leap year, so 02-29 is accepted
        else:
            return None
    except ValueError:
        return None
    return m, d


def _birthday_on(year, m, d):
    try:
        return datetime.date(year, m, d)
    except ValueError:                           # Feb 29 in a common year: celebrate on Feb 28
        return datetime.date(year, 2, 28)


def days_to_birthday(birthday, today):
    """Days until the next birthday (0 = today), or None when no birthday is set."""
    md = parse_birthday(birthday)
    if not md:
        return None
    nxt = _birthday_on(today.year, *md)
    if nxt < today:
        nxt = _birthday_on(today.year + 1, *md)
    return (nxt - today).days


def assess(f, today):
    """The friend plus everything the UI and the nudger need: score, due, birthday, snooze, next due date."""
    iso = today.isoformat()
    base = _date(f.get("last_contact") or f.get("added") or iso)
    days = max(0, (today - base).days)
    iv = interval(f)
    bd = days_to_birthday(f.get("birthday"), today)
    talked_today = (f.get("last_contact") or "")[:10] == iso
    snoozed_until = f.get("snoozed_until") or None
    snoozed = bool(snoozed_until) and snoozed_until > iso
    next_due = base + datetime.timedelta(days=iv)
    if snoozed and _date(snoozed_until) > next_due:
        next_due = _date(snoozed_until)
    return {
        **f,
        "tier_label": TIERS.get(f.get("tier"), TIERS["good"])["label"],
        "interval": iv,
        "days_since": days,
        "score": round(days / iv, 3),
        "due": days >= iv,
        "never_logged": not f.get("last_contact"),
        "talked_today": talked_today,
        "birthday_in": bd,
        "birthday_today": bd == 0 and not talked_today,
        "snoozed": snoozed,
        "next_due": max(next_due, today).isoformat(),
    }


def _key(a):
    return (not a["birthday_today"], -(a["days_since"] / a["interval"]), TIER_ORDER.get(a.get("tier"), 9),
            str(a.get("name") or "").lower(), a.get("id") or 0)


def rank(friends, today):
    """Everyone, most overdue first (birthday today first of all)."""
    return sorted((assess(f, today) for f in friends), key=_key)


def nudge_candidates(friends, today):
    """Friends worth a nudge today, in order: birthdays today, then due friends who are not snoozed."""
    return [a for a in rank(friends, today) if a["birthday_today"] or (a["due"] and not a["snoozed"])]


def pick_nudges(friends, today, n):
    return nudge_candidates(friends, today)[:max(0, int(n))]
