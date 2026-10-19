"""iCalendar export: every task's next due date and every warranty end as an all-day event, to import into a calendar."""
import datetime

import appliances
import tasks


def _esc(text):
    return str(text).replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")


def _event(uid, day, summary, stamp):
    d = datetime.date.fromisoformat(day)
    return ["BEGIN:VEVENT", f"UID:{uid}@home-maintenance", f"DTSTAMP:{stamp}",
            f"DTSTART;VALUE=DATE:{d:%Y%m%d}", f"DTEND;VALUE=DATE:{d + datetime.timedelta(days=1):%Y%m%d}",
            f"SUMMARY:{_esc(summary)}", "END:VEVENT"]


def calendar(on=None):
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Home Maintenance Log//EN", "CALSCALE:GREGORIAN"]
    for t in tasks.all_rows(on):
        lines += _event(f"task-{t['id']}", t["next_due"], t["name"], stamp)
    for a in appliances.all_rows(on):
        if a["warranty_end"]:
            lines += _event(f"warranty-{a['id']}", a["warranty_end"], f"Warranty ends: {a['name']}", stamp)
    lines.append("END:VCALENDAR")
    return "\r\n".join(lines) + "\r\n"
