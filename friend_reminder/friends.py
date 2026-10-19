"""The friend list: storage, and what Done / Snooze / Skip do (from the web page or a notification button)."""
import datetime
import re

import db
import ranking

FIELDS = ("name", "phone", "email", "tier", "interval_days", "last_contact", "birthday", "notes")


def today():
    return datetime.date.today()


def all_rows():
    return db.rows("SELECT * FROM friends")


def get(fid):
    r = db.rows("SELECT * FROM friends WHERE id=?", (fid,))
    return r[0] if r else None


def ranked():
    return ranking.rank(all_rows(), today())


def assessed(fid):
    f = get(fid)
    return ranking.assess(f, today()) if f else None


def _phone_key(p):
    digits = re.sub(r"\D", "", p or "")
    return digits[-10:] if len(digits) >= 7 else ""


class Known:
    """Who is already on the list: same phone number, or same name when either has no phone."""

    def __init__(self, rows):
        self.phones, self.names, self.names_without_phone = set(), set(), set()
        for f in rows:
            self.add(f["name"], f.get("phone"))

    def has(self, name, phone):
        pk, nk = _phone_key(phone), name.casefold()
        return bool(pk and pk in self.phones) or (nk in self.names and (not pk or nk in self.names_without_phone))

    def add(self, name, phone):
        pk, nk = _phone_key(phone), name.casefold()
        self.names.add(nk)
        if pk:
            self.phones.add(pk)
        else:
            self.names_without_phone.add(nk)


def on_list(contacts):
    """For each contact (dict with name and phone), whether that person is already a friend."""
    known = Known(all_rows())
    return [known.has(c["name"], c.get("phone")) for c in contacts]


def add_many(items):
    """Adds friends (dicts of FIELDS). Skips anyone already on the list (see Known), so picking or
    importing the same contacts twice does not create duplicates."""
    known = Known(all_rows())
    added, skipped, stmts = [], [], []
    iso = today().isoformat()
    for it in items:
        if known.has(it["name"], it.get("phone")):
            skipped.append(it["name"])
            continue
        known.add(it["name"], it.get("phone"))
        stmts.append(("INSERT INTO friends(name, phone, email, tier, interval_days, last_contact, birthday, notes, added) "
                      "VALUES(?,?,?,?,?,?,?,?,?)",
                      (it["name"], it.get("phone"), it.get("email"), it.get("tier") or "good", it.get("interval_days"),
                       it.get("last_contact"), it.get("birthday"), it.get("notes") or "", iso)))
        added.append(it["name"])
    ids = db.run_many(stmts) if stmts else []
    return {"added": added, "ids": ids, "skipped": skipped}


def update(fid, changes):
    changes = {k: v for k, v in changes.items() if k in FIELDS}
    if not changes:
        return bool(get(fid))
    if "notes" in changes and changes["notes"] is None:
        changes["notes"] = ""
    cols = ", ".join(f"{k}=?" for k in changes)
    return db.changed(f"UPDATE friends SET {cols} WHERE id=?", (*changes.values(), fid)) > 0


def delete(fid):
    return db.changed("DELETE FROM friends WHERE id=?", (fid,)) > 0


def save_opener(fid, text):
    db.changed("UPDATE friends SET opener=?, opener_at=? WHERE id=?",
               (text, datetime.datetime.now().isoformat(timespec="minutes"), fid))


def done(fid, on=None):
    """You talked: the clock restarts from that day. A date earlier than the one already logged changes nothing;
    a newer one also clears any snooze and the old opener, which was written for catching up."""
    on = on or today()
    on = on if isinstance(on, str) else on.isoformat()
    newer = "last_contact IS NULL OR last_contact < ?"     # SET expressions all see the row as it was before
    return db.changed(f"UPDATE friends SET snoozed_until = CASE WHEN {newer} THEN NULL ELSE snoozed_until END, "
                      f"opener = CASE WHEN {newer} THEN NULL ELSE opener END, "
                      f"opener_at = CASE WHEN {newer} THEN NULL ELSE opener_at END, "
                      f"last_contact = CASE WHEN {newer} THEN ? ELSE last_contact END WHERE id=?",
                      (on, on, on, on, on, fid)) > 0


def _put_off(fid, days_for):
    """Snooze / Skip. Only a friend who is due has a round to put off: one who is on today's list just for a
    birthday is left alone, so their regular nudge is not pushed back."""
    f = get(fid)
    if not f:
        return False
    if ranking.assess(f, today())["due"]:
        until = (today() + datetime.timedelta(days=days_for(f))).isoformat()
        db.changed("UPDATE friends SET snoozed_until=? WHERE id=?", (until, fid))
    return True


def snooze(fid):
    """Not today: ask again in a few days."""
    return _put_off(fid, lambda f: ranking.SNOOZE_DAYS)


def skip(fid):
    """Not this round: no nudges about this friend for one full interval (their clock is not reset)."""
    return _put_off(fid, ranking.interval)


ACTIONS = {"done": done, "snooze": snooze, "skip": skip}


def apply(kind, fid):
    return ACTIONS[kind](fid)
