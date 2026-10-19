import datetime

import db
import reminders
import tasks

D = datetime.date


def test_add_interval_clamps_month_end():
    assert tasks.add_interval(D(2026, 1, 31), 1, "months") == D(2026, 2, 28)
    assert tasks.add_interval(D(2026, 11, 15), 3, "months") == D(2027, 2, 15)
    assert tasks.add_interval(D(2026, 10, 19), 10, "days") == D(2026, 10, 29)


def test_next_due_counts_from_added_until_first_done():
    t = tasks.add("Filter", 3, "months", on=D(2026, 1, 10))
    assert t["next_due"] == "2026-04-10"
    t = tasks.done(t["id"], on=D(2026, 4, 20))
    assert t["next_due"] == "2026-07-20" and t["last_done"] == "2026-04-20"


def test_due_and_snooze():
    t = tasks.add("Gutters", 1, "days", on=D(2026, 10, 1))
    assert [x["id"] for x in tasks.due(D(2026, 10, 2))] == [t["id"]]
    tasks.snooze(t["id"], 3, on=D(2026, 10, 2))
    assert tasks.due(D(2026, 10, 4)) == []
    assert tasks.due(D(2026, 10, 5))


def test_done_logs_note_and_cost_and_clears_snooze():
    t = tasks.add("Filter", 1, "months", on=D(2026, 1, 1))
    tasks.snooze(t["id"], 30, on=D(2026, 2, 1))
    tasks.done(t["id"], "bought 2-pack", 24.5, on=D(2026, 2, 5))
    assert tasks.get(t["id"])["snoozed_until"] is None
    assert tasks.history(t["id"])[0]["cost"] == 24.5
    assert tasks.done(999) is None


def test_invalid_interval():
    for args in ((0, "days"), (1, "weeks")):
        try:
            tasks.add("x", *args)
            assert False
        except ValueError:
            pass


def test_presets_seeded_once():
    assert tasks.seed_presets() == len(tasks.PRESETS)
    tasks.remove(tasks.all_rows()[0]["id"])
    assert tasks.seed_presets() == 0
    assert len(tasks.all_rows()) == len(tasks.PRESETS) - 1


def test_reminder_once_a_day_after_time(ha_log):
    tasks.add("Filter", 1, "days", on=D(2026, 10, 1))
    early = reminders.tick(datetime.datetime(2026, 10, 20, 8, 0))
    assert early == [] and not ha_log["notify"]
    assert len(reminders.tick(datetime.datetime(2026, 10, 20, 9, 5))) == 1
    assert reminders.tick(datetime.datetime(2026, 10, 20, 15, 0)) == []
    assert db.get_setting("reminded_on") == "2026-10-20"
    assert len(ha_log["notify"]) == 1


def test_button_done_and_snooze(ha_log):
    t = tasks.add("Filter", 1, "days", on=D(2026, 10, 1))
    reminders.on_button("snooze", t["id"])
    assert tasks.get(t["id"])["snoozed_until"]
    reminders.on_button("done", t["id"])
    assert tasks.get(t["id"])["last_done"] == datetime.date.today().isoformat()
    assert ha_log["cleared"] == [t["id"], t["id"]]


def test_action_regex():
    import ha
    assert ha.ACTION.match("MAINT_DONE_12").group(2) == "12"
    assert not ha.ACTION.match("FRIEND_DONE_12")
