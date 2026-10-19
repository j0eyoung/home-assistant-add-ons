"""Appliance and warranty register, plus the emergency shutoffs list. Receipt and photo files live in the S3 bucket
(see files.py); only their metadata is kept here."""
import datetime

import db

LIFESPAN_AGING = 0.8        # an appliance is "aging" from 80% of its expected lifespan
WARRANTY_SOON = 30          # days
FIELDS = ("name", "brand", "model", "serial", "purchase_date", "warranty_end", "store", "price", "lifespan_years", "notes")
SHUTOFF_KINDS = ("water", "gas", "electric", "other")


def today():
    return datetime.date.today()


def _date(v):
    return datetime.date.fromisoformat(v) if v else None


def assess(row, on=None):
    """Adds age_years, warranty_days_left, warranty_status (none / active / expiring / expired) and lifespan_status
    (unknown / ok / aging / past)."""
    on = on or today()
    bought, ends = _date(row["purchase_date"]), _date(row["warranty_end"])
    age = round((on - bought).days / 365.25, 1) if bought else None
    left = (ends - on).days if ends else None
    wstatus = "none" if left is None else "expired" if left < 0 else "expiring" if left <= WARRANTY_SOON else "active"
    life = row["lifespan_years"]
    lstatus = "unknown" if not (age is not None and life) else "past" if age >= life else "aging" if age >= life * LIFESPAN_AGING else "ok"
    return {**row, "age_years": age, "warranty_days_left": left, "warranty_status": wstatus, "lifespan_status": lstatus}


def all_rows(on=None):
    return sorted((assess(r, on) for r in db.rows("SELECT * FROM appliances")), key=lambda a: a["name"].lower())


def get(appliance_id, on=None):
    r = db.rows("SELECT * FROM appliances WHERE id=?", (appliance_id,))
    return assess(r[0], on) if r else None


def add(name, on=None, **fields):
    data = {k: fields.get(k) for k in FIELDS[1:]}
    aid = db.run(f"INSERT INTO appliances({','.join(FIELDS)}) VALUES({','.join('?' * len(FIELDS))})",
                 (name.strip(), *(data[k] if data[k] is not None else ("" if k in ("brand", "model", "serial", "store", "notes") else None)
                                  for k in FIELDS[1:])))
    return get(aid, on)


def update(appliance_id, **fields):
    data = {k: v for k, v in fields.items() if k in FIELDS}
    if data:
        # a changed warranty date is a new warranty: remind about it again
        extra = ", warranty_notified=NULL" if "warranty_end" in data else ""
        db.changed(f"UPDATE appliances SET {','.join(k + '=?' for k in data)}{extra} WHERE id=?", (*data.values(), appliance_id))
    return get(appliance_id)


def remove(appliance_id):
    import files
    for a in db.rows("SELECT id FROM attachments WHERE owner_type='appliance' AND owner_id=?", (appliance_id,)):
        files.remove(a["id"])
    return db.changed("DELETE FROM appliances WHERE id=?", (appliance_id,)) > 0


def warranty_reminders(on=None):
    """Appliances whose warranty ends within 30 days (or just did not get its reminder yet) and have not been reminded."""
    return [a for a in all_rows(on)
            if a["warranty_status"] == "expiring" and a["warranty_notified"] != a["warranty_end"]]


def mark_reminded(appliance_id, warranty_end):
    db.run("UPDATE appliances SET warranty_notified=? WHERE id=?", (warranty_end, appliance_id))


# --- emergency shutoffs ---------------------------------------------------------------------------------------------
def shutoffs():
    return db.rows("SELECT * FROM shutoffs ORDER BY kind, name")


def add_shutoff(kind, name, location="", notes=""):
    if kind not in SHUTOFF_KINDS:
        raise ValueError("Kind is water, gas, electric or other.")
    sid = db.run("INSERT INTO shutoffs(kind,name,location,notes) VALUES(?,?,?,?)", (kind, name.strip(), location, notes))
    return db.rows("SELECT * FROM shutoffs WHERE id=?", (sid,))[0]


def update_shutoff(shutoff_id, **fields):
    data = {k: v for k, v in fields.items() if k in ("kind", "name", "location", "notes")}
    if data.get("kind", "water") not in SHUTOFF_KINDS:
        raise ValueError("Kind is water, gas, electric or other.")
    if data:
        db.changed(f"UPDATE shutoffs SET {','.join(k + '=?' for k in data)} WHERE id=?", (*data.values(), shutoff_id))
    r = db.rows("SELECT * FROM shutoffs WHERE id=?", (shutoff_id,))
    return r[0] if r else None


def remove_shutoff(shutoff_id):
    import files
    for a in db.rows("SELECT id FROM attachments WHERE owner_type='shutoff' AND owner_id=?", (shutoff_id,)):
        files.remove(a["id"])
    return db.changed("DELETE FROM shutoffs WHERE id=?", (shutoff_id,)) > 0
