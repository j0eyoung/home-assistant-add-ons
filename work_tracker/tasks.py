"""Tasks and follow-ups with an optional due date. A task is reminded once a day while it is due or overdue,
until it is marked done; Snooze pushes the reminder out one day."""
import datetime

import db
import hours

SNOOZE_DAYS = 1


def _date(s):
    if s in (None, ""):
        return None
    return datetime.date.fromisoformat(str(s)).isoformat()


def add(title, due=None, client="", case_no=""):
    title = str(title or "").strip()
    if not title:
        raise ValueError("A task needs a title.")
    if client or case_no:
        client, case_no = hours.clean(client, case_no)
    tid = db.run("INSERT INTO tasks(title,client,case_no,due,created) VALUES(?,?,?,?,?)",
                 (title, client, case_no, _date(due), hours.now().strftime(hours.FMT)))
    return get(tid)


def get(tid):
    r = db.rows("SELECT * FROM tasks WHERE id=?", (tid,))
    return r[0] if r else None


def listing(include_done=False):
    sql = "SELECT * FROM tasks" + ("" if include_done else " WHERE done_at IS NULL")
    return db.rows(sql + " ORDER BY done_at IS NOT NULL, due IS NULL, due, id")


def update(tid, **fields):
    t = get(tid)
    if not t:
        return None
    title = str(fields.get("title", t["title"]) or "").strip()
    if not title:
        raise ValueError("A task needs a title.")
    client, case_no = fields.get("client", t["client"]), fields.get("case_no", t["case_no"])
    if client or case_no:
        client, case_no = hours.clean(client, case_no)
    due = _date(fields["due"]) if "due" in fields else t["due"]
    db.run("UPDATE tasks SET title=?,client=?,case_no=?,due=?,snoozed_until=NULL,notified_on=NULL WHERE id=?",
           (title, client, case_no, due, tid))
    return get(tid)


def done(tid, undo=False):
    n = db.changed("UPDATE tasks SET done_at=? WHERE id=?",
                   (None if undo else hours.now().strftime(hours.FMT), tid))
    return n > 0


def snooze(tid, day=None):
    """No reminder before tomorrow (SNOOZE_DAYS from `day`)."""
    until = ((day or hours.today()) + datetime.timedelta(days=SNOOZE_DAYS)).isoformat()
    return db.changed("UPDATE tasks SET snoozed_until=? WHERE id=? AND done_at IS NULL", (until, tid)) > 0


def delete(tid):
    return db.changed("DELETE FROM tasks WHERE id=?", (tid,)) > 0


def due_now(day):
    """Open tasks due on or before `day`, not snoozed past it and not yet reminded today."""
    d = day.isoformat()
    return db.rows("SELECT * FROM tasks WHERE done_at IS NULL AND due IS NOT NULL AND due <= ? "
                   "AND (snoozed_until IS NULL OR snoozed_until <= ?) "
                   "AND (notified_on IS NULL OR notified_on < ?) ORDER BY due, id", (d, d, d))


def mark_notified(tid, day):
    db.run("UPDATE tasks SET notified_on=? WHERE id=?", (day.isoformat(), tid))
