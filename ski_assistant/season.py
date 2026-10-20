"""Season log, season summary and gear upkeep, all from the SQLite tables in db.py."""
import datetime as dt

import db
import resorts
import settings
import util


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
    # A deleted Garmin day stays deleted: remember its activity ids so the next sync skips them
    for row in db.q("SELECT garmin_ids FROM days WHERE id = ?", (day_id,)):
        for gid in filter(None, (row["garmin_ids"] or "").split(",")):
            db.once(f"garmin_skip:{gid}")
    db.x("DELETE FROM days WHERE id = ?", (day_id,))


def set_equipment(day_id, equipment):
    db.x("UPDATE days SET equipment = ? WHERE id = ?", (equipment, day_id))


# Season summary (context for Ask Claude, and the days sensor in Home Assistant)
def pass_summary(since=None):
    by_id = {r["id"]: r for r in resorts.load()}
    days = list_days(since)
    per_resort = {}
    for d in days:
        per_resort[d["resort_id"]] = per_resort.get(d["resort_id"], 0) + 1
    passes = {name: sum(n for rid, n in per_resort.items() if by_id.get(rid, {}).get("pass") == name)
              for name in ("ikon", "keystone")}
    limits = [{"resort": by_id[rid]["name"], "used": per_resort.get(rid, 0), "limit": r["pass_days"]}
              for rid, r in by_id.items() if r.get("pass_days")]
    return {"total_days": len(days), "per_resort": [{"resort": by_id.get(k, {}).get("name", k), "days": v}
                                                    for k, v in sorted(per_resort.items(), key=lambda kv: -kv[1])],
            "passes": passes, "limited_days": limits,
            "vertical_ft": sum(d["vertical_ft"] or 0 for d in days)}


# Season stats (Garmin days carry vertical, top speed, distance and hours)
def _totals(rows):
    return {"days": len(rows), "board_days": sum(1 for d in rows if d["equipment"] == "board"),
            "ski_days": sum(1 for d in rows if d["equipment"] == "ski"),
            "vertical_ft": sum(d["vertical_ft"] or 0 for d in rows),
            "top_speed_mph": max([d["top_speed_mph"] or 0 for d in rows] or [0]) or None,
            "distance_mi": round(sum(d["distance_mi"] or 0 for d in rows), 1),
            "hours": round(sum(d["hours"] or 0 for d in rows), 1)}


def stats():
    """This season against last season to the same date, the full last season, and your ski days in order
    (vertical and top speed) to show progress while learning."""
    start = season_start()
    today = util.today()
    last_start = (dt.date.fromisoformat(start) - dt.timedelta(days=365)).isoformat()
    same_day_last_year = (today - dt.timedelta(days=365)).isoformat()
    this = db.q("SELECT * FROM days WHERE date >= ? ORDER BY date", (start,))
    last_all = db.q("SELECT * FROM days WHERE date >= ? AND date < ? ORDER BY date", (last_start, start))
    last_to_date = [d for d in last_all if d["date"] <= same_day_last_year]
    ski = [{"date": d["date"], "vertical_ft": d["vertical_ft"], "top_speed_mph": d["top_speed_mph"]}
           for d in db.q("SELECT * FROM days WHERE equipment = 'ski' AND date >= ? ORDER BY date", (last_start,))]
    return {"this_season": _totals(this), "last_season_to_date": _totals(last_to_date),
            "last_season": _totals(last_all), "ski_progress": ski}


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
