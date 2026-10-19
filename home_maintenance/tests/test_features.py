import datetime

import appliances
import files
import ics
import publish
import reminders
import tasks

D = datetime.date


def test_status_ok_soon_overdue():
    t = tasks.add("Filter", 1, "months", on=D(2026, 1, 1))     # next due 2026-02-01
    assert tasks.assess(tasks.get(t["id"]), D(2026, 1, 20))["status"] == "ok"
    assert tasks.assess(tasks.get(t["id"]), D(2026, 1, 25))["status"] == "soon"
    assert tasks.assess(tasks.get(t["id"]), D(2026, 2, 2))["status"] == "overdue"


def test_seasonal_task_sleeps_until_season():
    t = tasks.add("Gutters", 6, "months", on=D(2026, 1, 1), active_months="10,11")   # nominal due 2026-07-01
    assert tasks.get(t["id"], D(2026, 7, 5))["next_due"] == "2026-10-01"
    assert not tasks.get(t["id"], D(2026, 7, 5))["due"] and not tasks.get(t["id"], D(2026, 7, 5))["in_season"]
    assert tasks.get(t["id"], D(2026, 10, 2))["due"]
    assert tasks.parse_months("11, 10,10") == "10,11" and tasks.parse_months("1,2,3,4,5,6,7,8,9,10,11,12") is None
    for bad in ("13", "0", "a"):
        try:
            tasks.parse_months(bad)
            assert False
        except ValueError:
            pass


def test_spread_moves_new_task_off_a_busy_week():
    a = tasks.add("A", 3, "months", on=D(2026, 1, 5))
    b = tasks.add("B", 3, "months", on=D(2026, 1, 5))
    assert a["shift_days"] == 0 and b["shift_days"] > 0
    assert D.fromisoformat(a["next_due"]).isocalendar()[:2] != D.fromisoformat(b["next_due"]).isocalendar()[:2]
    assert tasks.add("Tiny", 5, "days", on=D(2026, 1, 5))["shift_days"] == 0       # too short to shift


def test_done_stores_parts():
    t = tasks.add("Filter", 3, "months", on=D(2026, 1, 1))
    tasks.done(t["id"], "swapped", 18.0, on=D(2026, 4, 1), parts="MERV 11, 20x25x1")
    assert tasks.history(t["id"])[0]["parts"] == "MERV 11, 20x25x1"


def test_digest_counts_horizon():
    tasks.add("Soon", 1, "months", on=D(2026, 10, 1))      # due 2026-11-01
    tasks.add("Late", 1, "days", on=D(2026, 10, 1))
    d = tasks.digest(D(2026, 10, 25))
    assert [t["name"] for t in d["overdue"]] == ["Late"] and [t["name"] for t in d["this_week"]] == ["Soon"]
    assert list(d["horizon"])[0] == "2026-10" and len(d["horizon"]) == 12 and d["horizon"]["2026-11"] == 1
    assert "Overdue (1): Late" in reminders.digest_message(d)


def test_monday_digest_once_a_week(ha_log):
    tasks.add("Late", 1, "days", on=D(2026, 10, 1))
    assert not reminders.weekly_digest(datetime.datetime(2026, 10, 20, 10, 0))      # Tuesday
    assert not reminders.weekly_digest(datetime.datetime(2026, 10, 19, 8, 0))       # Monday, before the reminder time
    assert reminders.weekly_digest(datetime.datetime(2026, 10, 19, 10, 0))
    assert not reminders.weekly_digest(datetime.datetime(2026, 10, 19, 11, 0))
    assert ha_log["notify"][0][0] == "Home maintenance this week"


def test_appliance_assessment_and_warranty_reminder(ha_log):
    a = appliances.add("Dishwasher", brand="Bosch", purchase_date="2019-01-01", warranty_end="2026-11-10", lifespan_years=8)
    r = appliances.get(a["id"], D(2026, 10, 19))
    assert r["warranty_status"] == "expiring" and r["warranty_days_left"] == 22
    assert r["lifespan_status"] == "aging" and r["age_years"] == 7.8
    assert len(reminders.warranty_check(datetime.datetime(2026, 10, 19, 10, 0))) == 1
    assert reminders.warranty_check(datetime.datetime(2026, 10, 20, 10, 0)) == []     # once per warranty
    appliances.update(a["id"], warranty_end="2027-03-01")                               # a new warranty re-arms it
    assert appliances.get(a["id"])["warranty_notified"] is None
    assert appliances.get(a["id"], D(2026, 10, 19))["warranty_status"] == "active"


def test_task_link_survives_appliance_delete():
    a = appliances.add("Water heater")
    t = tasks.add("Flush", 12, "months", appliance_id=a["id"])
    assert appliances.remove(a["id"])
    assert tasks.get(t["id"])["appliance_id"] is None


def test_shutoffs():
    s = appliances.add_shutoff("water", "Main water", "Basement, left of the heater")
    assert appliances.update_shutoff(s["id"], location="Garage")["location"] == "Garage"
    try:
        appliances.add_shutoff("steam", "x")
        assert False
    except ValueError:
        pass
    assert appliances.remove_shutoff(s["id"]) and appliances.shutoffs() == []


class FakeS3:
    def __init__(self):
        self.objects = {}

    def put_object(self, Bucket, Key, Body, ContentType):
        self.objects[Key] = Body

    def get_object(self, Bucket, Key):
        import io
        return {"Body": io.BytesIO(self.objects[Key])}

    def delete_object(self, Bucket, Key):
        self.objects.pop(Key, None)


def test_files_go_to_bucket_not_db(options, monkeypatch):
    s3 = FakeS3()
    monkeypatch.setattr(files, "_s3", lambda: s3)
    a = appliances.add("Fridge")
    try:
        files.save("appliance", a["id"], "r.pdf", "application/pdf", b"%PDF")
        assert False
    except files.NotConfigured:
        pass
    options(s3_endpoint="https://x.r2.cloudflarestorage.com", s3_bucket="b", s3_access_key="k", s3_secret_key="s")
    m = files.save("appliance", a["id"], "my receipt (1).pdf", "application/pdf", b"%PDF")
    assert m["filename"] == "my_receipt_1_.pdf" and len(s3.objects) == 1
    assert files.fetch(m["id"])[1] == b"%PDF"
    for bad in (("text/html", b"x"), ("image/jpeg", b"")):
        try:
            files.save("appliance", a["id"], "f", *bad)
            assert False
        except ValueError:
            pass
    appliances.remove(a["id"])
    assert s3.objects == {} and files.list_for("appliance", a["id"]) == []


def test_ics_has_tasks_and_warranties():
    tasks.add("Gutters", 6, "months", on=D(2026, 1, 1))
    appliances.add("Oven", warranty_end="2027-05-01")
    text = ics.calendar()
    assert text.count("BEGIN:VEVENT") == 2 and "SUMMARY:Warranty ends: Oven" in text and "DTSTART;VALUE=DATE:20270501" in text
    assert text.startswith("BEGIN:VCALENDAR\r\n")


def test_publish_sync_only_sends_changes(monkeypatch):
    sent, removed = [], []
    monkeypatch.setattr(publish.ha, "available", lambda: True)
    monkeypatch.setattr(publish.ha, "set_state", lambda e, s, a: sent.append((e, s)))
    monkeypatch.setattr(publish.ha, "remove_state", lambda e: removed.append(e))
    publish._sent.clear()
    t = tasks.add("Fridge water filter", 1, "days", on=D(2020, 1, 1))
    assert publish.sync() == 2 and ("binary_sensor.home_maintenance_fridge_water_filter_%d" % t["id"], "on") in sent
    assert ("sensor.home_maintenance_due", "1") in sent
    assert publish.sync() == 0
    tasks.remove(t["id"])
    publish.sync()
    assert removed == ["binary_sensor.home_maintenance_fridge_water_filter_%d" % t["id"]]
