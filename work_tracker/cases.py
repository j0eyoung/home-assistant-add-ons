"""Case statuses pushed from the laptop: a case number and a short status, nothing else (no titles, customers or
descriptions). The status is limited to 40 characters so nothing sensitive can ride along."""
import db
import hours

MAX_STATUS = 40


def put(case_no, status):
    case_no = str(case_no or "").strip()
    status = " ".join(str(status or "").split())
    if not case_no or not hours.CASE.match(case_no):
        raise ValueError("Case number can only hold letters, digits, - or _.")
    if not status or len(status) > MAX_STATUS:
        raise ValueError(f"Status is 1 to {MAX_STATUS} characters.")
    db.run("INSERT INTO cases(case_no,status,updated) VALUES(?,?,?) "
           "ON CONFLICT(case_no) DO UPDATE SET status=excluded.status, updated=excluded.updated",
           (case_no, status, hours.now().strftime(hours.FMT)))
    return {"case_no": case_no, "status": status}


def listing():
    return db.rows("SELECT case_no, status, updated FROM cases ORDER BY updated DESC LIMIT 200")
