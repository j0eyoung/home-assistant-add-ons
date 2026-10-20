import datetime

import db
import hours
import nudger
import tasks


def at(s):
    return datetime.datetime.strptime(s, "%Y-%m-%d %H:%M")


def test_stop_nudge_when_timer_running(clock, sent):
    clock("2026-10-19 09:00")                         # Monday
    hours.start("KISS", "111")
    clock("2026-10-19 17:31")
    assert nudger.tick(at("2026-10-19 17:31")) == ["stop"]
    m = sent["send"][0]
    assert m["tag"] == "wt-stop" and m["actions"] == ["WT_STOP", "WT_LATER"] and "KISS case 111" in m["msg"]
    assert nudger.tick(at("2026-10-19 17:40")) == []   # once a day, also after a restart (persisted)
    nudger._state["stop_on"] = None
    assert nudger.tick(at("2026-10-19 17:45")) == []


def test_no_stop_nudge_outside_window_weekend_or_nothing_to_say(clock, sent):
    clock("2026-10-19 09:00")
    hours.start("KISS")
    clock("2026-10-19 16:00")
    assert nudger.tick(at("2026-10-19 16:00")) == []   # before stop time
    assert nudger.tick(at("2026-10-19 21:00")) == []   # window (3 h) over
    assert nudger.tick(at("2026-10-24 17:31")) == []   # Saturday
    hours.stop()
    assert nudger.tick(at("2026-10-20 17:31")) == []   # nothing running, no target
    assert sent["send"] == []


def test_below_daily_target(clock, sent, set_options):
    set_options(daily_target=8)
    clock("2026-10-20 17:31")
    hours.add_manual("KISS", "", "", "2026-10-20", 330)
    assert nudger.tick(at("2026-10-20 17:31")) == ["stop"]
    assert "5.5 h of 8 h" in sent["send"][0]["msg"]


def test_weekly_target_only_on_friday(clock, sent, set_options):
    set_options(weekly_target=40, summary_day="sun")
    clock("2026-10-21 17:31")
    hours.add_manual("KISS", "", "", "2026-10-21", 60)
    assert nudger.tick(at("2026-10-21 17:31")) == []
    assert nudger.tick(at("2026-10-23 17:31")) == ["stop"]
    assert "of 40 h" in sent["send"][0]["msg"]


def test_later_button_delays_and_stop_button_stops(clock, sent):
    clock("2026-10-19 09:00")
    hours.start("KISS")
    nudger.on_button("later", None)
    assert nudger.tick(at("2026-10-19 17:31")) == []
    nudger.on_button("stop", None)
    assert hours.running() is None and "wt-stop" in sent["clear"]


def test_task_reminders_once_a_day_with_buttons(clock, sent):
    clock("2026-10-19 08:00")
    t1 = tasks.add("Call client", "2026-10-19", "KISS", "111")
    tasks.add("Later", "2026-10-25")
    tasks.add("No date")
    assert nudger.tick(at("2026-10-19 08:30")) == []   # before 09:00
    assert nudger.tick(at("2026-10-19 09:01")) == ["tasks:1"]
    assert sent["send"][0]["actions"] == [f"WT_TASKDONE_{t1['id']}", f"WT_TASKSNOOZE_{t1['id']}"]
    assert nudger.tick(at("2026-10-19 12:00")) == []
    assert nudger.tick(at("2026-10-20 09:01")) == ["tasks:1"]   # still open: overdue reminder next day


def test_task_buttons(clock, sent):
    clock("2026-10-19 09:00")
    a = tasks.add("A", "2026-10-19")
    b = tasks.add("B", "2026-10-19")
    nudger.on_button("taskdone", a["id"])
    nudger.on_button("tasksnooze", b["id"])
    assert tasks.get(a["id"])["done_at"] and tasks.get(b["id"])["snoozed_until"] == "2026-10-20"
    assert tasks.due_now(datetime.date(2026, 10, 19)) == []
    assert [t["id"] for t in tasks.due_now(datetime.date(2026, 10, 20))] == [b["id"]]


def test_weekly_summary_once(clock, sent):
    clock("2026-10-23 10:00")                         # Friday
    hours.add_manual("KISS", "1", "", "2026-10-19", 50)
    hours.add_manual("TORR", "", "", "2026-10-20", 30)
    assert nudger.tick(at("2026-10-23 16:00")) == []
    assert nudger.tick(at("2026-10-23 17:01")) == ["summary"]
    msg = sent["send"][0]["msg"]
    assert "KISS: 1.00 h" in msg and "TORR: 0.50 h" in msg and "Total 1.50 h" in msg
    assert nudger.tick(at("2026-10-23 17:10")) == []
    assert db.get_setting("summary_week") == "2026-10-19"


def test_failed_send_retries_later(clock, sent, monkeypatch):
    import ha
    clock("2026-10-19 09:00")
    hours.start("KISS")
    monkeypatch.setattr(ha, "send", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("down")))
    assert nudger.tick(at("2026-10-19 17:31")) == []
    assert nudger._state["retry_at"] > 0 and db.get_setting("stop_nudged_on") is None
