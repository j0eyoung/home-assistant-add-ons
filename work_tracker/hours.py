"""Hours: the running timer, manual entries, totals and the timesheet export.

Times are local and stored as text. The running timer is the one entry with no `end`, so it survives restarts.
An entry counts toward the day it started. Timesheet hours are rounded up to the next 0.25 h per
(day, client, case), because each case is one Salesforce entry."""
import csv
import datetime
import io
import re

import db

FMT = "%Y-%m-%d %H:%M:%S"
CLIENT = re.compile(r"^[A-Z0-9][A-Z0-9_-]{0,19}$")
CASE = re.compile(r"^[A-Za-z0-9_-]{0,20}$")


def now():
    return datetime.datetime.now().replace(microsecond=0)


def today():
    return now().date()


def clean(client, case_no=""):
    client = str(client or "").strip().upper()
    case_no = str(case_no or "").strip()
    if not CLIENT.match(client):
        raise ValueError("Client must be a short code such as KISS (letters, digits, - or _).")
    if not CASE.match(case_no):
        raise ValueError("Case number can only hold letters, digits, - or _.")
    return client, case_no


def _dt(s):
    return datetime.datetime.strptime(s, FMT)


def minutes_of(e, at=None):
    end = _dt(e["end"]) if e["end"] else (at or now())
    return max(0, int((end - _dt(e["start"])).total_seconds() // 60))


def round_hours(minutes):
    """Up to the next 0.25 h (any part of a quarter hour counts as a whole one)."""
    return -(-int(minutes) // 15) / 4


def running():
    r = db.rows("SELECT * FROM entries WHERE end IS NULL ORDER BY id DESC LIMIT 1")
    return r[0] if r else None


def start(client, case_no="", note="", billable=True):
    """Starts a timer; a running one is stopped first (switching clients). Returns (new entry, stopped entry)."""
    client, case_no = clean(client, case_no)
    stopped = stop()
    t = now().strftime(FMT)
    eid = db.run("INSERT INTO entries(client,case_no,note,start,billable) VALUES(?,?,?,?,?)",
                 (client, case_no, str(note or "").strip(), t, 1 if billable else 0))
    return get(eid), stopped


def stop():
    """Stops every running timer (normally one). Returns the stopped entry, or None."""
    e = running()
    if e:
        db.run("UPDATE entries SET end=? WHERE end IS NULL", (now().strftime(FMT),))
        return get(e["id"])
    return None


def add_manual(client, case_no, note, day, minutes, start_time="00:00", billable=True):
    client, case_no = clean(client, case_no)
    minutes = int(minutes)
    if not 1 <= minutes <= 24 * 60:
        raise ValueError("Minutes must be between 1 and 1440.")
    s = datetime.datetime.strptime(f"{day} {start_time}", "%Y-%m-%d %H:%M")
    eid = db.run("INSERT INTO entries(client,case_no,note,start,end,billable) VALUES(?,?,?,?,?,?)",
                 (client, case_no, str(note or "").strip(), s.strftime(FMT),
                  (s + datetime.timedelta(minutes=minutes)).strftime(FMT), 1 if billable else 0))
    return get(eid)


def get(eid):
    r = db.rows("SELECT * FROM entries WHERE id=?", (eid,))
    return r[0] if r else None


def update(eid, **fields):
    e = get(eid)
    if not e:
        return None
    client, case_no = clean(fields.get("client", e["client"]), fields.get("case_no", e["case_no"]))
    note = str(fields.get("note", e["note"]) or "").strip()
    billable = 1 if fields.get("billable", bool(e["billable"])) else 0
    start_s, end_s = fields.get("start", e["start"]), fields.get("end", e["end"])
    if end_s is not None and _dt(end_s) < _dt(start_s):
        raise ValueError("End is before start.")
    db.run("UPDATE entries SET client=?,case_no=?,note=?,billable=?,start=?,end=? WHERE id=?",
           (client, case_no, note, billable, start_s, end_s, eid))
    return get(eid)


def delete(eid):
    return db.changed("DELETE FROM entries WHERE id=?", (eid,)) > 0


def entries(frm, to):
    """Entries that started on frm..to (dates, inclusive), oldest first."""
    return db.rows("SELECT * FROM entries WHERE start >= ? AND start < ? ORDER BY start",
                   (f"{frm} 00:00:00", f"{to + datetime.timedelta(days=1)} 00:00:00"))


def lines(frm, to, at=None):
    """One line per (day, client, case, billable): minutes, rounded hours, joined notes."""
    groups = {}
    for e in entries(frm, to):
        key = (e["start"][:10], e["client"], e["case_no"], e["billable"])
        g = groups.setdefault(key, {"date": key[0], "client": key[1], "case_no": key[2],
                                    "billable": bool(key[3]), "minutes": 0, "notes": []})
        g["minutes"] += minutes_of(e, at)
        if e["note"] and e["note"] not in g["notes"]:
            g["notes"].append(e["note"])
    out = []
    for g in groups.values():
        g["hours"] = round_hours(g["minutes"])
        g["notes"] = "; ".join(g.pop("notes"))
        out.append(g)
    return sorted(out, key=lambda g: (g["date"], g["client"], g["case_no"]))


def week_start(d):
    return d - datetime.timedelta(days=d.weekday())


def per_client(frm, to, at=None):
    """Actual (unrounded) minutes and rounded timesheet hours per client."""
    tot = {}
    for g in lines(frm, to, at):
        c = tot.setdefault(g["client"], {"client": g["client"], "minutes": 0, "hours": 0.0})
        c["minutes"] += g["minutes"]
        c["hours"] += g["hours"]
    return sorted(tot.values(), key=lambda c: -c["minutes"])


def total_minutes(frm, to, at=None):
    return sum(minutes_of(e, at) for e in entries(frm, to))


def totals(day=None, at=None):
    day = day or today()
    ws = week_start(day)
    we = ws + datetime.timedelta(days=6)
    return {"date": day.isoformat(), "week_start": ws.isoformat(),
            "day_minutes": total_minutes(day, day, at), "week_minutes": total_minutes(ws, we, at),
            "day": per_client(day, day, at), "week": per_client(ws, we, at)}


def recent_clients(limit=12):
    r = db.rows("SELECT client, case_no, MAX(start) AS last FROM entries GROUP BY client, case_no "
                "ORDER BY last DESC LIMIT ?", (limit,))
    return [{"client": x["client"], "case_no": x["case_no"]} for x in r]


def export_csv(frm, to):
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\r\n")
    w.writerow(["Date", "Client", "Case", "Billable", "Minutes", "Hours (0.25)", "Notes"])
    for g in lines(frm, to):
        w.writerow([g["date"], g["client"], g["case_no"], "Y" if g["billable"] else "N",
                    g["minutes"], f"{g['hours']:.2f}", g["notes"]])
    return buf.getvalue()
