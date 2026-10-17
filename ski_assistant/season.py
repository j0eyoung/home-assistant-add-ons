"""Season log, pass tracking, learning-to-ski log and gear upkeep, all from the SQLite tables in db.py."""
import datetime as dt

import db
import resorts
import settings
import util

SKILLS = ["stance and balance", "straight run", "pizza / wedge stop", "wedge turns", "traverse", "sideslip",
          "linking turns", "parallel turns", "pole plant", "hockey stop", "riding the chairlift", "getting off the lift"]


def season_start(today=None):
    """Season runs from Sept 1 (so an October day counts in the coming season)."""
    t = today or util.today()
    return dt.date(t.year if t.month >= 9 else t.year - 1, 9, 1).isoformat()


# Ride days
def add_day(date, resort_id, equipment, vertical_ft=None, notes=""):
    return db.x("INSERT INTO days(date, resort_id, equipment, vertical_ft, notes) VALUES (?,?,?,?,?)",
                (date, resort_id, equipment, vertical_ft, notes))


def list_days(since=None):
    return db.q("SELECT * FROM days WHERE date >= ? ORDER BY date DESC, id DESC", (since or season_start(),))


def delete_day(day_id):
    db.x("DELETE FROM days WHERE id = ?", (day_id,))


# Pass tracking
def pass_summary(since=None):
    s = settings.load()
    by_id = {r["id"]: r for r in resorts.load()}
    days = list_days(since)
    per_resort = {}
    for d in days:
        per_resort[d["resort_id"]] = per_resort.get(d["resort_id"], 0) + 1
    passes = {}
    for pass_name, price in (("ikon", s["ikon_price"]), ("keystone", s["keystone_price"])):
        used = sum(n for rid, n in per_resort.items() if by_id.get(rid, {}).get("pass") == pass_name)
        passes[pass_name] = {"price": price, "days": used, "cost_per_day": round(price / used, 2) if used and price else None}
    limits = [{"resort": by_id[rid]["name"], "used": per_resort.get(rid, 0), "limit": r["pass_days"]}
              for rid, r in by_id.items() if r.get("pass_days")]
    return {"total_days": len(days), "per_resort": [{"resort": by_id.get(k, {}).get("name", k), "days": v}
                                                    for k, v in sorted(per_resort.items(), key=lambda kv: -kv[1])],
            "passes": passes, "limited_days": limits,
            "vertical_ft": sum(d["vertical_ft"] or 0 for d in days)}


# Learning to ski
def add_lesson(date, resort_id="", skills="", notes=""):
    return db.x("INSERT INTO lessons(date, resort_id, skills, notes) VALUES (?,?,?,?)", (date, resort_id, skills, notes))


def list_lessons():
    return db.q("SELECT * FROM lessons ORDER BY date DESC, id DESC")


def delete_lesson(lesson_id):
    db.x("DELETE FROM lessons WHERE id = ?", (lesson_id,))


def learning_summary():
    lessons = list_lessons()
    practiced = {}
    for l in lessons:
        for sk in filter(None, (x.strip() for x in (l["skills"] or "").split(","))):
            practiced[sk] = practiced.get(sk, 0) + 1
    ski_days = db.q("SELECT COUNT(*) AS n FROM days WHERE equipment = 'ski' AND date >= ?", (season_start(),))[0]["n"]
    return {"ski_days": ski_days, "lessons": len(lessons), "skills": practiced,
            "not_yet": [s for s in SKILLS if s not in practiced]}


# Gear upkeep
def add_service(date, equipment, kind):
    return db.x("INSERT INTO service(date, equipment, kind) VALUES (?,?,?)", (date, equipment, kind))


def upkeep():
    s = settings.load()
    out = {}
    for eq in ("board", "ski"):
        out[eq] = {}
        for kind, every in (("wax", s["wax_every_days"][eq]), ("tune", s["tune_every_days"][eq])):
            last = db.q("SELECT MAX(date) AS d FROM service WHERE equipment = ? AND kind = ?", (eq, kind))[0]["d"]
            n = db.q("SELECT COUNT(*) AS n FROM days WHERE equipment = ? AND date > ?", (eq, last or "0000"))[0]["n"]
            out[eq][kind] = {"last": last, "days_since": n, "every": every, "due": n >= every}
    return out
