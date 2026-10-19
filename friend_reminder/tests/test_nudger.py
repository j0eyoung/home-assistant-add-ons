"""nudger.py: tick() / test() / on_button() with ha.send_nudge, ha.notify_service and ha.clear mocked."""
import datetime
import time

import pytest

import ai
import db
import friends
import ha
import nudger

NOW = datetime.datetime(2026, 10, 16, 12, 5)            # just after the default 12:00 nudge time
TODAY = NOW.date()


def at(hour, minute=0, second=0, day=NOW.date()):
    return datetime.datetime.combine(day, datetime.time(hour, minute, second))


def ago(n):
    return (TODAY - datetime.timedelta(days=n)).isoformat()


class Sent(list):
    """send_nudge calls as (service, friend, opener); `.cleared` holds the ha.clear calls as (service, friend id)."""
    def __init__(self):
        super().__init__()
        self.cleared = []


@pytest.fixture
def phone(monkeypatch):
    """A phone is available; send_nudge and clear record their calls instead of calling Home Assistant."""
    sent = Sent()
    monkeypatch.setattr(ha, "notify_service", lambda: "mobile_app_pixel")
    monkeypatch.setattr(ha, "send_nudge", lambda service, f, opener=None: sent.append((service, f, opener)))
    monkeypatch.setattr(ha, "clear", lambda service, fid: sent.cleared.append((service, fid)))
    return sent


@pytest.fixture
def three_due(make_friend):
    """Three good friends, overdue by 1.03x (Abe), 2.0x (Bea) and 1.5x (Cal). Returns their ids by name."""
    return {"Abe": make_friend("Abe", "good", last_contact=ago(31)),
            "Bea": make_friend("Bea", "good", last_contact=ago(60)),
            "Cal": make_friend("Cal", "good", last_contact=ago(45))}


def names(sent):
    return [f["name"] for _, f, _ in sent]


def names_of(friends_):
    return [f["name"] for f in friends_]


# ---------------------------------------------------------------- nudge_time / in_window

def test_nudge_time_defaults_to_noon():
    assert nudger.nudge_time() == datetime.time(12, 0)


@pytest.mark.parametrize("value,expected", [
    ("08:30", datetime.time(8, 30)), ("7:05", datetime.time(7, 5)), (" 18:45 ", datetime.time(18, 45)),
    ("12:00:30", datetime.time(12, 0)),
    ("25:00", datetime.time(12, 0)), ("noon", datetime.time(12, 0)), ("12", datetime.time(12, 0)),
    ("12:99", datetime.time(12, 0)),
])
def test_nudge_time_from_options(set_options, value, expected):
    set_options(nudge_time=value)
    assert nudger.nudge_time() == expected


def test_in_window_boundaries():
    t = datetime.time(12, 0)
    assert nudger.in_window(at(11, 59, 59), t) is False
    assert nudger.in_window(at(12, 0, 0), t) is True            # the window opens at the nudge time
    assert nudger.in_window(at(14, 59, 59), t) is True
    assert nudger.in_window(at(15, 0, 0), t) is False           # and closes three hours later
    assert nudger.in_window(at(23, 0), t) is False


# ---------------------------------------------------------------- tick: when it sends

def test_nothing_before_the_nudge_time(phone, three_due):
    assert nudger.tick(at(11, 59, 59)) == []
    assert nudger.tick(at(6, 0)) == []
    assert phone == []
    assert db.get_setting("nudged_on") is None


def test_sends_exactly_at_the_nudge_time(phone, three_due):
    assert names_of(nudger.tick(at(12, 0, 0))) == ["Bea"]
    assert len(phone) == 1


def test_sends_late_in_the_window(phone, three_due):
    assert names_of(nudger.tick(at(14, 59, 59))) == ["Bea"]


def test_nothing_after_the_window(phone, three_due):
    assert nudger.tick(at(15, 0, 0)) == []
    assert nudger.tick(at(21, 30)) == []
    assert phone == [] and db.get_setting("nudged_on") is None


def test_a_custom_nudge_time_moves_the_window(phone, three_due, set_options):
    set_options(nudge_time="18:30")
    assert nudger.tick(at(12, 5)) == []
    assert nudger.tick(at(18, 29)) == []
    assert names_of(nudger.tick(at(18, 30))) == ["Bea"]


def test_the_message_goes_to_the_notify_service_with_the_assessed_friend(phone, three_due):
    nudger.tick(NOW)
    service, f, opener = phone[0]
    assert service == "mobile_app_pixel"
    assert f["name"] == "Bea" and f["days_since"] == 60 and f["tier_label"] == "Good" and f["birthday_today"] is False
    assert opener is None                                         # Claude is not set up


# ---------------------------------------------------------------- tick: how many

def test_one_nudge_per_day_by_default_the_most_overdue(phone, three_due):
    assert names_of(nudger.tick(NOW)) == ["Bea"]
    assert names(phone) == ["Bea"]


def test_two_nudges_when_the_option_says_so(phone, three_due, set_options):
    set_options(nudges_per_day=2)
    assert names_of(nudger.tick(NOW)) == ["Bea", "Cal"]
    assert names(phone) == ["Bea", "Cal"]


def test_never_more_than_two_even_if_configured_higher(phone, three_due, set_options):
    set_options(nudges_per_day=5)
    assert len(nudger.tick(NOW)) == 2
    assert len(phone) == 2


def test_fewer_due_friends_than_the_limit(phone, make_friend, set_options):
    set_options(nudges_per_day=2)
    make_friend("Only", "good", last_contact=ago(40))
    make_friend("Fine", "good", last_contact=ago(3))
    assert names_of(nudger.tick(NOW)) == ["Only"]


def test_nobody_due_sends_nothing(phone, make_friend):
    make_friend("Fine", "good", last_contact=ago(3))
    assert nudger.tick(NOW) == []
    assert phone == []


def test_snoozed_friends_are_skipped(phone, make_friend, set_options):
    set_options(nudges_per_day=2)
    tomorrow = (TODAY + datetime.timedelta(days=1)).isoformat()
    make_friend("Snoozed", "good", last_contact=ago(90), snoozed_until=tomorrow)
    make_friend("Awake", "good", last_contact=ago(31))
    assert names_of(nudger.tick(NOW)) == ["Awake"]


def test_birthdays_are_nudged_first_and_even_when_snoozed(phone, make_friend):
    tomorrow = (TODAY + datetime.timedelta(days=1)).isoformat()
    make_friend("Bday", "casual", last_contact=ago(2), birthday="10-16", snoozed_until=tomorrow)
    make_friend("Overdue", "close", last_contact=ago(200))
    sent = nudger.tick(NOW)
    assert names_of(sent) == ["Bday"]                             # one a day: the birthday wins
    assert sent[0]["birthday_today"] is True


def test_birthday_and_the_most_overdue_when_two_are_allowed(phone, make_friend, set_options):
    set_options(nudges_per_day=2)
    make_friend("Bday", "casual", last_contact=ago(2), birthday="10-16")
    make_friend("Overdue", "close", last_contact=ago(200))
    make_friend("Less", "good", last_contact=ago(31))
    assert names_of(nudger.tick(NOW)) == ["Bday", "Overdue"]
    assert names(phone) == ["Bday", "Overdue"]


# ---------------------------------------------------------------- tick: once per day

def test_only_once_per_day(phone, three_due):
    assert len(nudger.tick(at(12, 5))) == 1
    assert nudger.tick(at(12, 6)) == []
    assert nudger.tick(at(14, 59)) == []
    assert len(phone) == 1


def test_the_day_is_remembered_in_the_database(phone, three_due):
    nudger.tick(NOW)
    assert db.get_setting("nudged_on") == "2026-10-16"
    assert db.get_setting("last_nudge") == {"date": "2026-10-16", "ids": [three_due["Bea"]], "names": ["Bea"]}


def test_still_once_per_day_across_a_restart(phone, three_due):
    nudger.tick(at(12, 5))
    nudger._state["sent_on"] = None                              # a new process starts with an empty memory
    nudger._state["retry_at"] = 0.0
    assert nudger.tick(at(12, 30)) == []
    assert len(phone) == 1
    assert nudger._state["sent_on"] == "2026-10-16"               # reloaded from the stored 'nudged_on'


def test_a_stored_nudged_on_for_today_blocks_a_fresh_process(phone, three_due):
    db.set_setting("nudged_on", "2026-10-16")
    assert nudger.tick(NOW) == []
    assert phone == []


def test_yesterdays_nudged_on_does_not_block_today(phone, three_due):
    db.set_setting("nudged_on", "2026-10-15")
    assert names_of(nudger.tick(NOW)) == ["Bea"]
    assert db.get_setting("nudged_on") == "2026-10-16"


def test_nudges_again_the_next_day(phone, three_due):
    nudger.tick(at(12, 5))
    tomorrow = TODAY + datetime.timedelta(days=1)
    assert names_of(nudger.tick(at(12, 5, day=tomorrow))) == ["Bea"]     # still unanswered, so still on top
    assert len(phone) == 2
    assert db.get_setting("nudged_on") == "2026-10-17"


def test_answering_the_nudge_moves_on_to_the_next_friend_tomorrow(phone, three_due):
    first = nudger.tick(at(12, 5))
    friends.done(first[0]["id"], TODAY)
    tomorrow = TODAY + datetime.timedelta(days=1)
    assert names_of(nudger.tick(at(12, 5, day=tomorrow))) == ["Cal"]


# ---------------------------------------------------------------- tick: failures

def test_no_phone_sends_nothing_and_does_not_mark_the_day(monkeypatch, three_due):
    sent = []
    monkeypatch.setattr(ha, "notify_service", lambda: "")
    monkeypatch.setattr(ha, "send_nudge", lambda *a, **k: sent.append(a))
    assert nudger.tick(NOW) == []
    assert sent == []
    assert db.get_setting("nudged_on") is None and db.get_setting("last_nudge") is None
    assert nudger._state["sent_on"] is None


def test_a_phone_that_shows_up_later_in_the_window_is_used(monkeypatch, three_due):
    service = {"value": ""}
    sent = []
    monkeypatch.setattr(ha, "notify_service", lambda: service["value"])
    monkeypatch.setattr(ha, "send_nudge", lambda svc, f, opener=None: sent.append(f["name"]))
    assert nudger.tick(at(12, 5)) == []
    service["value"] = "mobile_app_pixel"
    assert names_of(nudger.tick(at(12, 6))) == ["Bea"]
    assert sent == ["Bea"]


def test_a_failed_first_send_sets_a_retry_delay_and_does_not_mark_the_day(monkeypatch, three_due):
    attempts = []

    def failing(service, f, opener=None):
        attempts.append(f["name"])
        raise OSError("Home Assistant is restarting")
    monkeypatch.setattr(ha, "notify_service", lambda: "mobile_app_pixel")
    monkeypatch.setattr(ha, "send_nudge", failing)

    before = time.time()
    assert nudger.tick(NOW) == []
    assert attempts == ["Bea"]
    assert before + nudger.RETRY - 1 <= nudger._state["retry_at"] <= time.time() + nudger.RETRY + 1
    assert db.get_setting("nudged_on") is None and db.get_setting("last_nudge") is None

    assert nudger.tick(at(12, 6)) == []                           # inside the retry delay: not even tried
    assert attempts == ["Bea"]


def test_the_retry_after_a_failure_succeeds_once_the_delay_is_over(monkeypatch, three_due):
    outcomes = iter([OSError("down"), None])
    sent = []

    def flaky(service, f, opener=None):
        out = next(outcomes)
        if out:
            raise out
        sent.append(f["name"])
    monkeypatch.setattr(ha, "notify_service", lambda: "mobile_app_pixel")
    monkeypatch.setattr(ha, "send_nudge", flaky)

    assert nudger.tick(at(12, 5)) == []
    nudger._state["retry_at"] = 0.0                               # ten minutes later
    assert names_of(nudger.tick(at(12, 15))) == ["Bea"]
    assert sent == ["Bea"]
    assert db.get_setting("nudged_on") == "2026-10-16"
    assert nudger.tick(at(12, 16)) == []                          # and now it is done for the day


def test_a_partial_failure_marks_the_day(monkeypatch, three_due, set_options):
    set_options(nudges_per_day=2)
    sent = []

    def second_fails(service, f, opener=None):
        if sent:
            raise OSError("second send failed")
        sent.append(f)
    monkeypatch.setattr(ha, "notify_service", lambda: "mobile_app_pixel")
    monkeypatch.setattr(ha, "send_nudge", second_fails)

    result = nudger.tick(NOW)
    assert names_of(result) == ["Bea"]
    assert db.get_setting("nudged_on") == "2026-10-16"
    assert db.get_setting("last_nudge")["names"] == ["Bea"]
    assert nudger._state["retry_at"] == 0.0                       # no retry: the day is done
    assert nudger.tick(at(12, 30)) == []
    assert len(sent) == 1


# ---------------------------------------------------------------- tick: the Claude opener

def test_opener_is_drafted_for_a_friend_with_notes_and_saved(phone, make_friend, monkeypatch):
    fid = make_friend("Mike", "good", last_contact=ago(40), notes="new job")
    monkeypatch.setattr(ai, "available", lambda: True)
    monkeypatch.setattr(ai, "opener", lambda f: f"Hey {f['name']}, how is the new job?")
    nudger.tick(NOW)
    assert phone[0][2] == "Hey Mike, how is the new job?"
    assert friends.get(fid)["opener"] == "Hey Mike, how is the new job?"


def test_no_opener_is_drafted_without_notes_unless_it_is_a_birthday(phone, make_friend, monkeypatch, set_options):
    set_options(nudges_per_day=2)
    make_friend("NoNotes", "good", last_contact=ago(40))
    make_friend("Bday", "good", last_contact=ago(2), birthday="10-16")
    drafted = []
    monkeypatch.setattr(ai, "available", lambda: True)
    monkeypatch.setattr(ai, "opener", lambda f: drafted.append(f["name"]) or "text")
    nudger.tick(NOW)
    assert drafted == ["Bday"]


def test_a_failed_opener_does_not_stop_the_nudge(phone, make_friend, monkeypatch):
    make_friend("Mike", "good", last_contact=ago(40), notes="new job")
    monkeypatch.setattr(ai, "available", lambda: True)

    def boom(f):
        raise RuntimeError("Claude is down")
    monkeypatch.setattr(ai, "opener", boom)
    assert names_of(nudger.tick(NOW)) == ["Mike"]
    assert phone[0][2] is None


# ---------------------------------------------------------------- on_button

def test_done_button_resets_the_clock_and_clears_the_notification(phone, make_friend):
    fid = make_friend("Mike", "good", last_contact="2020-01-01", snoozed_until="2999-01-01")
    nudger.on_button("done", fid)
    f = friends.get(fid)
    assert f["last_contact"] == datetime.date.today().isoformat() and f["snoozed_until"] is None
    assert phone.cleared == [("mobile_app_pixel", fid)]


def test_snooze_button_snoozes_for_three_days(phone, make_friend):
    fid = make_friend("Mike", "good", last_contact="2020-01-01")
    nudger.on_button("snooze", fid)
    f = friends.get(fid)
    assert f["snoozed_until"] == (datetime.date.today() + datetime.timedelta(days=3)).isoformat()
    assert f["last_contact"] == "2020-01-01"
    assert phone.cleared == [("mobile_app_pixel", fid)]


def test_skip_button_snoozes_for_one_interval_without_resetting_the_clock(phone, make_friend):
    fid = make_friend("Mike", "close", last_contact="2020-01-01")
    nudger.on_button("skip", fid)
    f = friends.get(fid)
    assert f["snoozed_until"] == (datetime.date.today() + datetime.timedelta(days=14)).isoformat()
    assert f["last_contact"] == "2020-01-01"
    assert phone.cleared == [("mobile_app_pixel", fid)]


def test_button_for_a_deleted_friend_is_harmless(phone):
    nudger.on_button("done", 999)
    assert phone.cleared == [("mobile_app_pixel", 999)]


def test_button_without_a_phone_still_applies_the_action(monkeypatch, make_friend):
    cleared = []
    monkeypatch.setattr(ha, "notify_service", lambda: "")
    monkeypatch.setattr(ha, "clear", lambda *a: cleared.append(a))
    fid = make_friend("Mike", "good", last_contact="2020-01-01")
    nudger.on_button("done", fid)
    assert friends.get(fid)["last_contact"] == datetime.date.today().isoformat()
    assert cleared == []


def test_a_failing_clear_is_swallowed(monkeypatch, make_friend):
    monkeypatch.setattr(ha, "notify_service", lambda: "mobile_app_pixel")

    def boom(service, fid):
        raise OSError("HA unreachable")
    monkeypatch.setattr(ha, "clear", boom)
    fid = make_friend("Mike", "good", last_contact="2020-01-01")
    nudger.on_button("snooze", fid)                              # must not raise
    assert friends.get(fid)["snoozed_until"] is not None


def test_a_button_tap_does_not_count_as_the_days_nudge(phone, make_friend):
    fid = make_friend("Mike", "good", last_contact="2020-01-01")
    nudger.on_button("snooze", fid)
    assert db.get_setting("nudged_on") is None


# ---------------------------------------------------------------- test() (the "Send a test nudge" button)

def test_test_sends_the_top_friend(phone, make_friend, today):
    make_friend("Fresh", "good", last_contact=(today - datetime.timedelta(days=1)).isoformat())
    make_friend("Stale", "good", last_contact=(today - datetime.timedelta(days=90)).isoformat())
    make_friend("Mid", "good", last_contact=(today - datetime.timedelta(days=40)).isoformat())
    f = nudger.test()
    assert f["name"] == "Stale"
    assert names(phone) == ["Stale"]
    assert phone[0][0] == "mobile_app_pixel"


def test_test_puts_a_birthday_on_top(phone, make_friend, today):
    make_friend("Stale", "close", last_contact=(today - datetime.timedelta(days=300)).isoformat())
    make_friend("Bday", "casual", last_contact=(today - datetime.timedelta(days=1)).isoformat(),
                birthday=f"{today.month:02d}-{today.day:02d}")
    assert nudger.test()["name"] == "Bday"


def test_test_can_pick_a_specific_friend(phone, make_friend, today):
    make_friend("Stale", "good", last_contact=(today - datetime.timedelta(days=90)).isoformat())
    other = make_friend("Other", "good", last_contact=(today - datetime.timedelta(days=2)).isoformat())
    assert nudger.test(other)["name"] == "Other"
    assert names(phone) == ["Other"]


def test_test_does_not_count_as_todays_nudge(phone, make_friend, today):
    make_friend("Stale", "good", last_contact=(today - datetime.timedelta(days=90)).isoformat())
    nudger.test()
    assert db.get_setting("nudged_on") is None and db.get_setting("last_nudge") is None
    assert nudger._state["sent_on"] is None


def test_test_unknown_friend_and_empty_list_are_lookup_errors(phone, make_friend):
    with pytest.raises(LookupError, match="Add a friend first"):
        nudger.test()
    make_friend("Mike")
    with pytest.raises(LookupError, match="No such friend"):
        nudger.test(12345)
    assert phone == []


def test_test_without_a_phone_is_a_runtime_error(monkeypatch, make_friend):
    monkeypatch.setattr(ha, "notify_service", lambda: "")
    make_friend("Mike")
    with pytest.raises(RuntimeError, match="No phone found"):
        nudger.test()


def test_test_lets_a_send_failure_through(monkeypatch, make_friend):
    monkeypatch.setattr(ha, "notify_service", lambda: "mobile_app_pixel")

    def boom(service, f, opener=None):
        raise OSError("HA is down")
    monkeypatch.setattr(ha, "send_nudge", boom)
    make_friend("Mike")
    with pytest.raises(OSError):
        nudger.test()


# ---------------------------------------------------------------- review fixes

def test_a_late_nudge_time_keeps_its_window_past_midnight(set_options, phone, three_due):
    set_options(nudge_time="23:30")
    assert nudger.in_window(at(0, 10, day=TODAY + datetime.timedelta(days=1)), datetime.time(23, 30)) is True
    assert nudger.tick(at(0, 10, day=TODAY + datetime.timedelta(days=1))) != []      # missed at 23:30, sent at 00:10
    assert db.get_setting("nudged_on") == TODAY.isoformat()                         # counted for the day it was due
    assert nudger.tick(at(0, 40, day=TODAY + datetime.timedelta(days=1))) == []      # not sent twice
    assert nudger.tick(at(23, 35, day=TODAY + datetime.timedelta(days=1))) != []     # the next evening sends again


def test_retries_reuse_the_opener_drafted_that_day(monkeypatch, make_friend):
    make_friend("Bea", "good", last_contact=ago(60), notes="New job")
    drafts = []
    monkeypatch.setattr(ai, "available", lambda: True)
    monkeypatch.setattr(ai, "opener", lambda f: drafts.append(f["name"]) or "Hey Bea!")
    monkeypatch.setattr(ha, "notify_service", lambda: "mobile_app_pixel")

    def down(service, f, opener=None):
        raise OSError("phone offline")
    monkeypatch.setattr(ha, "send_nudge", down)
    real_now = datetime.datetime.now()
    assert nudger.tick(datetime.datetime.combine(real_now.date(), datetime.time(12, 5))) == []
    nudger._state["retry_at"] = 0.0                                               # ten minutes later
    assert nudger.tick(datetime.datetime.combine(real_now.date(), datetime.time(12, 15))) == []
    assert drafts == ["Bea"]                                                      # drafted once, reused on the retry