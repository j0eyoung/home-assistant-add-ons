"""friends.py + api.py through fastapi's TestClient (real SQLite file per test, no Home Assistant, no network)."""
import datetime
import os

import pytest

import ai
import api
import config
import db
import friends
import ha
import nudger

SERVICE = "notify.mobile_app_test_phone"


def iso(d):
    return d.isoformat()


def ago(today, n):
    return iso(today - datetime.timedelta(days=n))


def ahead(today, n):
    return iso(today + datetime.timedelta(days=n))


def add(client, *items):
    r = client.post("/api/friends", json={"friends": list(items)})
    assert r.status_code == 200, r.text
    return r.json()


def add_one(client, name="Alex", **fields):
    out = add(client, {"name": name, **fields})
    return out["ids"][0]


def state(client):
    r = client.get("/api/state")
    assert r.status_code == 200, r.text
    return r.json()


def by_name(st, name):
    return next(f for f in st["friends"] if f["name"] == name)


def row(fid):
    return friends.get(fid)


# ================================================================ add (bulk)

def test_bulk_add_returns_names_and_ids_and_stores_defaults(client, today):
    out = add(client, {"name": "Mike"}, {"name": "Sara", "tier": "close"}, {"name": "Tom", "tier": "casual"})
    assert out["added"] == ["Mike", "Sara", "Tom"]
    assert out["skipped"] == []
    assert len(out["ids"]) == 3 and len(set(out["ids"])) == 3
    st = state(client)
    assert len(st["friends"]) == 3
    mike = by_name(st, "Mike")
    assert mike["id"] == out["ids"][0]
    assert mike["tier"] == "good" and mike["interval"] == 30
    assert mike["added"] == iso(today)
    assert mike["last_contact"] is None and mike["never_logged"] is True
    assert mike["notes"] == "" and mike["snoozed_until"] is None
    assert by_name(st, "Sara")["interval"] == 14
    assert by_name(st, "Tom")["interval"] == 90


def test_add_stores_every_field_and_trims_text(client):
    fid = add_one(client, "  Priya  ", phone=" +1 555 123 4567 ", email=" p@example.com ", tier="close",
                  interval_days=10, last_contact="2026-01-02", birthday="1990-03-14", notes="  new job  ")
    f = row(fid)
    assert f["name"] == "Priya"
    assert f["phone"] == "+1 555 123 4567" and f["email"] == "p@example.com"
    assert (f["tier"], f["interval_days"], f["last_contact"], f["birthday"]) == ("close", 10, "2026-01-02", "1990-03-14")
    assert f["notes"] == "new job"


def test_blank_optional_fields_are_stored_as_null(client):
    fid = add_one(client, "Blank", phone="  ", email="", birthday="", last_contact="")
    f = row(fid)
    assert f["phone"] is None and f["email"] is None and f["birthday"] is None and f["last_contact"] is None


def test_add_accepts_boundary_values(client, today):
    out = add(client,
              {"name": "A", "interval_days": 1},
              {"name": "B", "interval_days": 730},
              {"name": "C", "birthday": "02-29"},
              {"name": "D", "birthday": "1990-03-14"},
              {"name": "E", "last_contact": iso(today)},
              {"name": "F" * 80})
    assert len(out["added"]) == 6


def test_duplicate_phone_digits_are_skipped_even_with_a_different_name_and_format(client):
    add(client, {"name": "Mike", "phone": "+1 (555) 123-4567"})
    out = add(client, {"name": "Michael R", "phone": "555.123.4567"})
    assert out["added"] == [] and out["skipped"] == ["Michael R"] and out["ids"] == []
    assert len(state(client)["friends"]) == 1


def test_phone_match_uses_the_last_ten_digits(client):
    add(client, {"name": "Mike", "phone": "+44 7700 900123"})
    out = add(client, {"name": "Mike again", "phone": "07700 900123"})       # same number without the country code
    assert out["skipped"] == ["Mike again"]


def test_different_phone_numbers_are_both_added(client):
    out = add(client, {"name": "Mike", "phone": "555-123-4567"}, {"name": "Mike", "phone": "555-999-0000"})
    assert out["added"] == ["Mike", "Mike"] and out["skipped"] == []


def test_duplicate_name_without_a_phone_is_skipped_ignoring_case(client):
    add(client, {"name": "Mike"})
    out = add(client, {"name": "MIKE"}, {"name": "mike", "phone": ""})
    assert out["added"] == [] and out["skipped"] == ["MIKE", "mike"]


def test_existing_phone_friend_blocks_a_same_name_contact_without_a_phone(client):
    add(client, {"name": "Mike", "phone": "555-123-4567"})
    out = add(client, {"name": "mike"})
    assert out["skipped"] == ["mike"]


def test_short_phone_numbers_are_not_used_as_keys(client):
    out = add(client, {"name": "A", "phone": "123"}, {"name": "B", "phone": "123"})
    assert out["added"] == ["A", "B"]                       # fewer than 7 digits: not treated as the same number


def test_duplicates_inside_one_request_are_skipped(client):
    out = add(client, {"name": "A", "phone": "555-123-4567"}, {"name": "B", "phone": "(555) 123 4567"},
              {"name": "C"}, {"name": "c"})
    assert out["added"] == ["A", "C"] and out["skipped"] == ["B", "c"]
    assert len(out["ids"]) == 2


def test_adding_the_same_contacts_twice_creates_no_duplicates(client):
    batch = [{"name": "A", "phone": "555-111-2222"}, {"name": "B"}]
    add(client, *batch)
    out = add(client, *batch)
    assert out["added"] == [] and out["skipped"] == ["A", "B"]
    assert len(state(client)["friends"]) == 2


def test_existing_friend_without_a_phone_blocks_a_same_name_contact_that_has_one(client):
    add(client, {"name": "Mike"})
    out = add(client, {"name": "Mike", "phone": "555-123-4567"})
    assert out["skipped"] == ["Mike"]
    assert len(state(client)["friends"]) == 1


@pytest.mark.parametrize("bad", [
    {"name": "A", "tier": "best"},
    {"name": "A", "tier": "Close"},
    {"name": "A", "tier": ""},
    {"name": ""},
    {"name": "   "},
    {"name": "x" * 81},
    {"name": "A", "interval_days": 0},
    {"name": "A", "interval_days": -3},
    {"name": "A", "interval_days": 731},
    {"name": "A", "interval_days": "often"},
    {"name": "A", "last_contact": "2999-01-01"},
    {"name": "A", "last_contact": "16/10/2026"},
    {"name": "A", "last_contact": "yesterday"},
    {"name": "A", "birthday": "13-45"},
    {"name": "A", "birthday": "02-30"},
    {"name": "A", "birthday": "3-14"},
    {"name": "A", "birthday": "1990-02-30"},
    {"name": "A", "birthday": "tomorrow"},
    {"name": "A", "notes": "n" * 2001},
    {"name": "A", "phone": "1" * 41},
    {"name": "A", "email": "e" * 121},
    {},
])
def test_add_rejects_invalid_friends(client, bad):
    r = client.post("/api/friends", json={"friends": [bad]})
    assert r.status_code == 422, r.text
    assert state(client)["friends"] == []


def test_future_last_contact_tomorrow_is_rejected(client, today):
    r = client.post("/api/friends", json={"friends": [{"name": "A", "last_contact": ahead(today, 1)}]})
    assert r.status_code == 422 and "future" in r.text


def test_one_invalid_friend_rejects_the_whole_batch(client):
    r = client.post("/api/friends", json={"friends": [{"name": "Good"}, {"name": "Bad", "tier": "nope"}]})
    assert r.status_code == 422
    assert state(client)["friends"] == []


def test_add_rejects_an_empty_or_missing_list_and_an_oversized_one(client):
    assert client.post("/api/friends", json={"friends": []}).status_code == 422
    assert client.post("/api/friends", json={}).status_code == 422
    too_many = [{"name": f"F{i}"} for i in range(501)]
    assert client.post("/api/friends", json={"friends": too_many}).status_code == 422


def test_add_accepts_500_friends_in_one_request(client):
    out = add(client, *({"name": f"F{i}"} for i in range(500)))
    assert len(out["added"]) == 500 and len(out["ids"]) == 500


# ================================================================ PUT (edit)

def test_put_changes_only_the_fields_sent(client):
    fid = add_one(client, "Mike", phone="555-123-4567", tier="good", birthday="03-14", notes="new job")
    r = client.put(f"/api/friends/{fid}", json={"tier": "close"})
    assert r.status_code == 200
    body = r.json()
    assert body["tier"] == "close" and body["tier_label"] == "Close" and body["interval"] == 14
    assert (body["name"], body["phone"], body["birthday"], body["notes"]) == ("Mike", "555-123-4567", "03-14", "new job")


def test_put_can_change_several_fields_and_returns_the_assessed_friend(client, today):
    fid = add_one(client, "Mike")
    r = client.put(f"/api/friends/{fid}", json={"name": " Michael ", "interval_days": 7, "last_contact": ago(today, 8),
                                                 "birthday": "1990-03-14", "notes": " hi ", "email": "m@x.org"})
    body = r.json()
    assert body["name"] == "Michael" and body["interval"] == 7 and body["due"] is True
    assert body["days_since"] == 8 and body["notes"] == "hi" and body["email"] == "m@x.org"


def test_put_null_clears_optional_fields(client, today):
    fid = add_one(client, "Mike", phone="555-123-4567", email="m@x.org", interval_days=10, birthday="03-14",
                  last_contact=ago(today, 3), notes="something")
    r = client.put(f"/api/friends/{fid}", json={"phone": None, "email": None, "interval_days": None,
                                                 "birthday": None, "last_contact": None, "notes": None})
    assert r.status_code == 200
    f = row(fid)
    assert f["phone"] is None and f["email"] is None and f["interval_days"] is None
    assert f["birthday"] is None and f["last_contact"] is None
    assert f["notes"] == ""                                      # notes is never NULL
    body = r.json()
    assert body["interval"] == 30 and body["never_logged"] is True and body["birthday_in"] is None


def test_put_empty_string_clears_birthday_and_last_contact(client):
    fid = add_one(client, "Mike", birthday="03-14", last_contact="2026-01-02")
    client.put(f"/api/friends/{fid}", json={"birthday": "", "last_contact": ""})
    f = row(fid)
    assert f["birthday"] is None and f["last_contact"] is None


def test_put_with_an_empty_body_changes_nothing(client):
    fid = add_one(client, "Mike", tier="close")
    r = client.put(f"/api/friends/{fid}", json={})
    assert r.status_code == 200 and r.json()["tier"] == "close"


def test_put_ignores_fields_that_are_not_editable(client, today):
    fid = add_one(client, "Mike")
    client.put(f"/api/friends/{fid}", json={"id": 999, "added": "2000-01-01", "snoozed_until": "2999-01-01",
                                             "opener": "hack"})
    f = row(fid)
    assert f["id"] == fid and f["added"] == iso(today) and f["snoozed_until"] is None and f["opener"] is None


@pytest.mark.parametrize("bad", [
    {"name": ""}, {"name": "   "}, {"name": None},
    {"tier": "best"}, {"tier": None},
    {"interval_days": 0}, {"interval_days": 731}, {"interval_days": -1},
    {"last_contact": "2999-01-01"}, {"last_contact": "not a date"},
    {"birthday": "13-45"}, {"birthday": "02-30"}, {"birthday": "3-14"},
    {"notes": "n" * 2001},
])
def test_put_rejects_invalid_values_and_leaves_the_row_alone(client, bad):
    fid = add_one(client, "Mike", tier="close", birthday="03-14")
    before = dict(row(fid))
    r = client.put(f"/api/friends/{fid}", json=bad)
    assert r.status_code == 422, r.text
    assert row(fid) == before


def test_put_unknown_friend_is_404(client):
    assert client.put("/api/friends/999", json={"tier": "close"}).status_code == 404
    assert client.put("/api/friends/999", json={}).status_code == 404


def test_put_with_a_non_numeric_id_is_422(client):
    assert client.put("/api/friends/abc", json={}).status_code == 422


# ================================================================ DELETE

def test_delete_removes_the_friend(client):
    keep = add_one(client, "Keep")
    gone = add_one(client, "Gone")
    r = client.delete(f"/api/friends/{gone}")
    assert r.status_code == 200 and r.json() == {"ok": True}
    assert [f["id"] for f in state(client)["friends"]] == [keep]
    assert row(gone) is None


def test_delete_twice_or_unknown_is_404(client):
    fid = add_one(client)
    assert client.delete(f"/api/friends/{fid}").status_code == 200
    assert client.delete(f"/api/friends/{fid}").status_code == 404
    assert client.delete("/api/friends/12345").status_code == 404


# ================================================================ done

def test_done_without_a_body_sets_last_contact_to_today(client, today):
    fid = add_one(client, "Mike", last_contact=ago(today, 60))
    r = client.post(f"/api/friends/{fid}/done")
    assert r.status_code == 200
    body = r.json()
    assert body["last_contact"] == iso(today)
    assert body["days_since"] == 0 and body["due"] is False and body["never_logged"] is False
    assert body["talked_today"] is True


def test_done_with_an_empty_json_body_or_null_date_means_today(client, today):
    a = add_one(client, "A")
    b = add_one(client, "B")
    c = add_one(client, "C")
    d = add_one(client, "D")
    json_header = {"content-type": "application/json"}
    assert client.post(f"/api/friends/{a}/done", json={}).json()["last_contact"] == iso(today)
    assert client.post(f"/api/friends/{b}/done", json={"date": None}).json()["last_contact"] == iso(today)
    assert client.post(f"/api/friends/{c}/done", headers=json_header).json()["last_contact"] == iso(today)     # no body
    assert client.post(f"/api/friends/{d}/done", content=b"null", headers=json_header).json()["last_contact"] == iso(today)


def test_done_clears_snooze_and_the_old_opener(client, today):
    fid = add_one(client, "Mike", last_contact=ago(today, 60))
    db.changed("UPDATE friends SET snoozed_until=?, opener='Hey stranger', opener_at='2026-01-01T10:00' WHERE id=?",
               (ahead(today, 5), fid))
    body = client.post(f"/api/friends/{fid}/done").json()
    assert body["snoozed_until"] is None and body["snoozed"] is False
    assert body["opener"] is None and body["opener_at"] is None


def test_done_with_a_past_date_sets_that_date(client, today):
    fid = add_one(client, "Mike")                                   # never logged
    r = client.post(f"/api/friends/{fid}/done", json={"date": ago(today, 10)})
    assert r.status_code == 200
    assert r.json()["last_contact"] == ago(today, 10) and r.json()["days_since"] == 10


def test_done_with_a_past_date_moves_an_older_last_contact_forward(client, today):
    fid = add_one(client, "Mike", last_contact=ago(today, 40))
    body = client.post(f"/api/friends/{fid}/done", json={"date": ago(today, 5)}).json()
    assert body["last_contact"] == ago(today, 5)


def test_done_with_a_past_date_never_overwrites_a_later_last_contact(client, today):
    fid = add_one(client, "Mike", last_contact=ago(today, 2))
    body = client.post(f"/api/friends/{fid}/done", json={"date": ago(today, 20)}).json()
    assert body["last_contact"] == ago(today, 2)
    assert row(fid)["last_contact"] == ago(today, 2)


def test_done_on_the_same_date_is_harmless(client, today):
    fid = add_one(client, "Mike", last_contact=ago(today, 4))
    body = client.post(f"/api/friends/{fid}/done", json={"date": ago(today, 4)}).json()
    assert body["last_contact"] == ago(today, 4)


def test_done_with_an_old_date_leaves_a_long_overdue_friend_due(client, today):
    fid = add_one(client, "Mike", tier="good")
    body = client.post(f"/api/friends/{fid}/done", json={"date": ago(today, 45)}).json()
    assert body["days_since"] == 45 and body["due"] is True


@pytest.mark.parametrize("bad", ["2999-01-01", "tomorrow", "10/16/2026", "2026-13-40"])
def test_done_rejects_a_future_or_malformed_date(client, bad):
    fid = add_one(client, "Mike")
    r = client.post(f"/api/friends/{fid}/done", json={"date": bad})
    assert r.status_code == 422
    assert row(fid)["last_contact"] is None


def test_done_unknown_friend_is_404(client):
    assert client.post("/api/friends/999/done").status_code == 404
    assert client.post("/api/friends/999/done", json={"date": "2026-01-01"}).status_code == 404


# ================================================================ snooze / skip

def test_snooze_adds_three_days_and_keeps_the_clock(client, today):
    fid = add_one(client, "Mike", last_contact=ago(today, 50))
    r = client.post(f"/api/friends/{fid}/snooze")
    assert r.status_code == 200
    body = r.json()
    assert body["snoozed_until"] == ahead(today, 3) and body["snoozed"] is True
    assert body["last_contact"] == ago(today, 50) and body["due"] is True
    assert body["next_due"] == ahead(today, 3)


def test_snooze_twice_is_not_cumulative(client, today):
    fid = add_one(client, "Mike", last_contact=(today - datetime.timedelta(days=40)).isoformat())
    client.post(f"/api/friends/{fid}/snooze")
    assert client.post(f"/api/friends/{fid}/snooze").json()["snoozed_until"] == ahead(today, 3)


def test_snooze_unknown_friend_is_404(client):
    assert client.post("/api/friends/999/snooze").status_code == 404


@pytest.mark.parametrize("fields,days", [
    ({"tier": "close"}, 14), ({"tier": "good"}, 30), ({"tier": "casual"}, 90), ({"tier": "casual", "interval_days": 10}, 10),
])
def test_skip_snoozes_for_one_interval_without_resetting_the_clock(client, today, fields, days):
    fid = add_one(client, "Mike", last_contact=ago(today, 200), **fields)
    r = client.post(f"/api/friends/{fid}/skip")
    assert r.status_code == 200
    body = r.json()
    assert body["snoozed_until"] == ahead(today, days)
    assert body["last_contact"] == ago(today, 200)              # clock not reset
    assert body["days_since"] == 200 and body["due"] is True and body["snoozed"] is True


def test_skip_does_not_invent_a_last_contact_for_a_never_logged_friend(client, today, make_friend):
    fid = make_friend("Mike", tier="close", added=(today - datetime.timedelta(days=20)).isoformat())
    body = client.post(f"/api/friends/{fid}/skip").json()
    assert body["last_contact"] is None and body["never_logged"] is True
    assert body["snoozed_until"] == ahead(today, 14)


@pytest.mark.parametrize("action", ["snooze", "skip"])
def test_snooze_and_skip_leave_a_friend_who_is_not_due_alone(client, today, action):
    """A friend on today's list only for a birthday has no round to put off; their regular nudge must not move."""
    fid = add_one(client, "Bea", last_contact=(today - datetime.timedelta(days=5)).isoformat(),
                  birthday=today.strftime("%m-%d"))
    before = client.get("/api/state").json()["friends"][0]["next_due"]
    body = client.post(f"/api/friends/{fid}/{action}").json()
    assert body["snoozed_until"] is None and body["next_due"] == before and body["birthday_today"] is True


def test_logging_an_older_talk_changes_nothing(client, today):
    fid = add_one(client, "Mike", last_contact=(today - datetime.timedelta(days=40)).isoformat())
    client.post(f"/api/friends/{fid}/snooze")
    body = client.post(f"/api/friends/{fid}/done", json={"date": (today - datetime.timedelta(days=50)).isoformat()}).json()
    assert body["snoozed_until"] == ahead(today, 3)                    # the snooze survives a no-op log
    assert body["last_contact"] == (today - datetime.timedelta(days=40)).isoformat()


def test_lone_surrogates_are_stored_safely(client):
    r = client.post("/api/friends", content='{"friends": [{"name": "Ana \\ud83d", "notes": "hi \\ude00"}]}',
                    headers={"Content-Type": "application/json"})
    assert r.status_code == 200 and r.json()["added"] == ["Ana ?"]


def test_skip_unknown_friend_is_404(client):
    assert client.post("/api/friends/999/skip").status_code == 404


def test_snoozed_friend_drops_out_of_the_due_count_and_done_brings_the_clock_back(client, today):
    fid = add_one(client, "Mike", last_contact=ago(today, 50))
    assert state(client)["due"] == 1
    client.post(f"/api/friends/{fid}/snooze")
    assert state(client)["due"] == 0
    client.post(f"/api/friends/{fid}/done")
    st = state(client)
    assert st["due"] == 0 and by_name(st, "Mike")["last_contact"] == iso(today)


# ================================================================ friends.py used directly

def test_update_with_nothing_to_change_reports_whether_the_friend_exists(make_friend):
    fid = make_friend("Mike")
    assert friends.update(fid, {}) is True
    assert friends.update(fid, {"id": 99, "added": "2000-01-01", "opener": "x"}) is True      # not editable: ignored
    assert friends.update(999, {}) is False
    assert friends.update(999, {"name": "Nobody"}) is False
    f = row(fid)
    assert f["id"] == fid and f["added"] != "2000-01-01" and f["opener"] is None


def test_update_turns_null_notes_into_an_empty_string(make_friend):
    fid = make_friend("Mike", notes="something")
    assert friends.update(fid, {"notes": None}) is True
    assert row(fid)["notes"] == ""


def test_done_accepts_a_date_object_or_a_string(make_friend, today):
    fid = make_friend("Mike", last_contact="2020-01-01")
    assert friends.done(fid, datetime.date(2026, 3, 4)) is True
    assert row(fid)["last_contact"] == "2026-03-04"
    assert friends.done(fid, "2026-05-06") is True
    assert row(fid)["last_contact"] == "2026-05-06"
    assert friends.done(fid) is True
    assert row(fid)["last_contact"] == iso(today)
    assert friends.done(999) is False


def test_apply_dispatches_the_three_button_actions(make_friend, today):
    fid = make_friend("Mike", "close", last_contact="2020-01-01")
    assert friends.apply("snooze", fid) is True and row(fid)["snoozed_until"] == ahead(today, 3)
    assert friends.apply("skip", fid) is True and row(fid)["snoozed_until"] == ahead(today, 14)
    assert friends.apply("done", fid) is True
    assert row(fid)["last_contact"] == iso(today) and row(fid)["snoozed_until"] is None
    assert friends.apply("done", 999) is False
    with pytest.raises(KeyError):
        friends.apply("delete", fid)


# ================================================================ /api/state

def test_state_shape_outside_home_assistant(client, today):
    add(client, {"name": "Mike"})
    st = state(client)
    assert set(st) == {"version", "today", "friends", "due", "tiers", "snooze_days", "settings", "panel_url",
                       "last_nudge"}
    assert st["version"] == api.VERSION
    assert st["today"] == iso(today)
    assert st["snooze_days"] == 3
    assert {k: v["days"] for k, v in st["tiers"].items()} == {"close": 14, "good": 30, "casual": 90}
    assert {k: v["label"] for k, v in st["tiers"].items()} == {"close": "Close", "good": "Good", "casual": "Casual"}
    assert st["settings"] == {"in_home_assistant": False, "notify_service": "", "phones": [], "nudge_time": "12:00",
                              "nudges_per_day": 1, "claude": False, "model": config._DEFAULTS["model"]}
    assert st["panel_url"] is None and st["last_nudge"] is None
    f = st["friends"][0]
    assert {"id", "name", "tier", "tier_label", "interval", "days_since", "score", "due", "never_logged",
            "talked_today", "birthday_in", "birthday_today", "snoozed", "next_due"} <= set(f)


def test_state_with_no_friends(client):
    st = state(client)
    assert st["friends"] == [] and st["due"] == 0


def test_state_friends_are_ranked_most_overdue_first(client, today):
    add(client,
        {"name": "Fresh", "last_contact": ago(today, 1)},
        {"name": "Stale", "last_contact": ago(today, 90)},
        {"name": "Mid", "last_contact": ago(today, 40)})
    assert [f["name"] for f in state(client)["friends"]] == ["Stale", "Mid", "Fresh"]


def test_state_due_count(client, today):
    bday = f"{today.month:02d}-{today.day:02d}"
    add(client,
        {"name": "Due", "last_contact": ago(today, 40)},                                     # counts
        {"name": "NotDue", "last_contact": ago(today, 5)},                                   # no
        {"name": "DueButSnoozed", "last_contact": ago(today, 40)},                           # no (snoozed below)
        {"name": "BirthdayNotDue", "last_contact": ago(today, 2), "birthday": bday},         # counts
        {"name": "BirthdayTalkedToday", "last_contact": iso(today), "birthday": bday},       # no
        {"name": "ExpiredSnooze", "last_contact": ago(today, 40)},                           # counts
        {"name": "NeverLoggedNew"})                                                          # no (added today)
    st = state(client)
    ids = {f["name"]: f["id"] for f in st["friends"]}
    db.changed("UPDATE friends SET snoozed_until=? WHERE id=?", (ahead(today, 2), ids["DueButSnoozed"]))
    db.changed("UPDATE friends SET snoozed_until=? WHERE id=?", (iso(today), ids["ExpiredSnooze"]))
    st = state(client)
    assert st["due"] == 3
    assert by_name(st, "BirthdayNotDue")["birthday_today"] is True
    assert by_name(st, "BirthdayTalkedToday")["birthday_today"] is False


def test_state_birthday_snoozed_friend_is_still_counted(client, today):
    fid = add_one(client, "B", last_contact=ago(today, 2), birthday=f"{today.month:02d}-{today.day:02d}")
    client.post(f"/api/friends/{fid}/snooze")
    assert state(client)["due"] == 1


def test_state_reports_the_add_on_options(client, set_options):
    set_options(nudge_time="08:30", nudges_per_day=2, anthropic_api_key="sk-test", model="claude-sonnet-5-5",
                notify_service="notify.mobile_app_pixel")
    s = state(client)["settings"]
    assert s["nudge_time"] == "08:30" and s["nudges_per_day"] == 2
    assert s["claude"] is True and s["model"] == "claude-sonnet-5-5"
    assert s["notify_service"] == "mobile_app_pixel"            # "notify." prefix stripped
    assert s["in_home_assistant"] is False


def test_state_clamps_nudges_per_day_and_falls_back_on_a_bad_time(client, set_options):
    set_options(nudge_time="25:99", nudges_per_day=9)
    s = state(client)["settings"]
    assert s["nudges_per_day"] == 2 and s["nudge_time"] == "12:00"


def fake_home_assistant(monkeypatch, *phones):
    posts = []

    def _call(method, url, body=None, timeout=10):
        if method == "GET" and url.endswith("/services"):
            return [{"domain": "notify", "services": {p: {} for p in phones}}]
        if method == "GET" and url.endswith("/addons/self/info"):
            return {"data": {"slug": "abc_friend_reminder"}}
        if method == "POST":
            posts.append((url, body))
            return []
        raise AssertionError(f"unexpected call {method} {url}")
    monkeypatch.setattr(ha, "_call", _call)
    return posts


def test_state_inside_home_assistant_lists_the_phones_when_none_is_chosen(client_from, in_home_assistant, monkeypatch):
    fake_home_assistant(monkeypatch, "mobile_app_pixel", "mobile_app_ipad")
    st = client_from("172.30.32.2").get("/api/state").json()
    assert st["settings"]["in_home_assistant"] is True
    assert st["settings"]["notify_service"] == "" and st["settings"]["phones"] == ["mobile_app_ipad", "mobile_app_pixel"]
    assert st["panel_url"] == "/hassio/ingress/abc_friend_reminder"


def test_state_inside_home_assistant_picks_the_only_phone(client_from, in_home_assistant, monkeypatch):
    fake_home_assistant(monkeypatch, "mobile_app_pixel")
    s = client_from("172.30.32.2").get("/api/state").json()["settings"]
    assert s["notify_service"] == "mobile_app_pixel" and s["phones"] == []


def test_nudge_test_inside_home_assistant_posts_the_notification(client_from, in_home_assistant, monkeypatch, today):
    posts = fake_home_assistant(monkeypatch, "mobile_app_pixel")
    c = client_from("172.30.32.2")
    add(c, {"name": "Stale", "last_contact": ago(today, 90)}, {"name": "Fresh", "last_contact": ago(today, 1)})
    r = c.post("/api/nudge/test")
    assert r.status_code == 200 and r.json() == {"sent_to": "mobile_app_pixel", "friend": "Stale"}
    (url, body), = posts
    assert url == f"{ha.CORE}/services/notify/mobile_app_pixel"
    assert body["title"] == "Reach out to Stale"
    assert [a["title"] for a in body["data"]["actions"]] == ["Done", "Snooze", "Skip"]
    assert body["data"]["clickAction"] == "/hassio/ingress/abc_friend_reminder"


def test_state_shows_the_last_nudge(client):
    db.set_setting("last_nudge", {"date": "2026-10-15", "ids": [1], "names": ["Mike"]})
    assert state(client)["last_nudge"] == {"date": "2026-10-15", "ids": [1], "names": ["Mike"]}


# ================================================================ opener

def test_opener_without_an_api_key_is_503(client):
    fid = add_one(client, "Mike", notes="new job")
    r = client.post(f"/api/friends/{fid}/opener")
    assert r.status_code == 503
    assert "API key" in r.json()["detail"]
    assert row(fid)["opener"] is None


def test_opener_for_an_unknown_friend_is_404(client):
    assert client.post("/api/friends/999/opener").status_code == 404


def test_opener_success_is_returned_and_saved(client, monkeypatch):
    seen = []
    monkeypatch.setattr(ai, "opener", lambda f: seen.append(f) or "How is the new job going?")
    fid = add_one(client, "Mike", notes="new job")
    r = client.post(f"/api/friends/{fid}/opener")
    assert r.status_code == 200 and r.json() == {"opener": "How is the new job going?"}
    assert seen[0]["name"] == "Mike" and seen[0]["tier_label"] == "Good"       # an assessed friend
    f = row(fid)
    assert f["opener"] == "How is the new job going?" and f["opener_at"]


def test_opener_failure_is_502_with_a_readable_reason(client, monkeypatch):
    def boom(f):
        raise RuntimeError("Claude declined to draft this one. Try editing the notes.")
    monkeypatch.setattr(ai, "opener", boom)
    fid = add_one(client, "Mike")
    r = client.post(f"/api/friends/{fid}/opener")
    assert r.status_code == 502 and "declined" in r.json()["detail"]
    assert row(fid)["opener"] is None


# ================================================================ /api/nudge/test

def test_nudge_test_outside_home_assistant_is_an_error(client):
    add_one(client, "Mike")
    r = client.post("/api/nudge/test")
    assert r.status_code == 502
    assert "No phone found" in r.json()["detail"]


def test_nudge_test_with_a_service_but_outside_home_assistant_fails_cleanly(client, set_options):
    set_options(notify_service=SERVICE)
    add_one(client, "Mike")
    r = client.post("/api/nudge/test")
    assert r.status_code == 502
    assert "Not running inside Home Assistant" in r.json()["detail"]


def test_nudge_test_with_no_friends_is_404(client, set_options):
    set_options(notify_service=SERVICE)
    r = client.post("/api/nudge/test")
    assert r.status_code == 404 and "Add a friend" in r.json()["detail"]


def test_nudge_test_unknown_friend_is_404(client, set_options):
    set_options(notify_service=SERVICE)
    add_one(client, "Mike")
    r = client.post("/api/nudge/test", params={"fid": 999})
    assert r.status_code == 404 and "No such friend" in r.json()["detail"]


def test_nudge_test_success_sends_the_top_friend_and_does_not_count_as_todays_nudge(client, set_options, today, monkeypatch):
    set_options(notify_service=SERVICE)
    sent = []
    monkeypatch.setattr(nudger.ha, "send_nudge", lambda svc, f, opener=None: sent.append((svc, f["name"])))
    add(client, {"name": "Fresh", "last_contact": ago(today, 1)}, {"name": "Stale", "last_contact": ago(today, 90)})
    r = client.post("/api/nudge/test")
    assert r.status_code == 200 and r.json() == {"sent_to": "mobile_app_test_phone", "friend": "Stale"}
    assert sent == [("mobile_app_test_phone", "Stale")]
    assert db.get_setting("nudged_on") is None


def test_nudge_test_can_target_a_friend(client, set_options, monkeypatch):
    set_options(notify_service=SERVICE)
    sent = []
    monkeypatch.setattr(nudger.ha, "send_nudge", lambda svc, f, opener=None: sent.append(f["name"]))
    add_one(client, "First")
    other = add_one(client, "Other")
    r = client.post("/api/nudge/test", params={"fid": other})
    assert r.status_code == 200 and r.json()["friend"] == "Other" and sent == ["Other"]


# ================================================================ /api/diag

def test_diag_is_empty_before_anything_is_saved(client):
    assert client.get("/api/diag").json() == {}


def test_diag_round_trip(client):
    report = {"secureContext": False, "hasContacts": True, "ua": "Pixel", "n": 3, "nested": {"a": [1, 2]}}
    r = client.post("/api/diag", json={"report": report})
    assert r.status_code == 200 and r.json() == {"ok": True}
    saved = client.get("/api/diag").json()
    assert saved["report"] == report
    datetime.datetime.fromisoformat(saved["at"])                    # an ISO timestamp


def test_diag_keeps_only_the_latest_report(client):
    client.post("/api/diag", json={"report": {"v": 1}})
    client.post("/api/diag", json={"report": {"v": 2}})
    assert client.get("/api/diag").json()["report"] == {"v": 2}


def test_diag_report_must_be_an_object(client):
    assert client.post("/api/diag", json={"report": "text"}).status_code == 422
    assert client.post("/api/diag", json={}).status_code == 422


def test_diag_oversized_report_is_truncated_to_4000_characters(client):
    r = client.post("/api/diag", json={"report": {"blob": "x" * 5000}})
    assert r.status_code == 200
    saved = client.get("/api/diag").json()["report"]
    assert isinstance(saved, str) and len(saved) == 4000


# ================================================================ index, static, version

def test_index_is_served_with_the_version_substituted(client):
    r = client.get("/")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/html")
    assert r.headers["cache-control"] == "no-cache"
    assert "__V__" not in r.text
    with open(os.path.join(api.HERE, "static", "index.html"), encoding="utf-8") as f:
        source = f.read()
    assert r.text == source.replace("__V__", api.VERSION)


def test_index_substitution_with_a_known_version(client, monkeypatch, tmp_path):
    (tmp_path / "static").mkdir()
    (tmp_path / "static" / "index.html").write_text("<script src=app.js?v=__V__></script><b>__V__</b>", encoding="utf-8")
    monkeypatch.setattr(api, "HERE", str(tmp_path))
    monkeypatch.setattr(api, "VERSION", "9.8.7")
    assert client.get("/").text == "<script src=app.js?v=9.8.7></script><b>9.8.7</b>"


def test_version_is_read_from_config_yaml(monkeypatch, tmp_path):
    monkeypatch.setattr(api, "HERE", str(tmp_path))
    assert api._version() == "dev"                                  # no config.yaml yet
    (tmp_path / "config.yaml").write_text('name: "Friend Reminder"\nversion: "1.2.3"\nslug: "x"\n', encoding="utf-8")
    assert api._version() == "1.2.3"
    (tmp_path / "config.yaml").write_text("version: 0.4.0\n", encoding="utf-8")
    assert api._version() == "0.4.0"


def test_static_files_are_served_with_no_cache(client):
    r = client.get("/static/index.html")
    assert r.status_code == 200 and r.headers["cache-control"] == "no-cache"
    assert client.get("/static/nope.js").status_code == 404


def test_api_docs_are_disabled(client):
    assert client.get("/docs").status_code == 404
    assert client.get("/openapi.json").status_code == 404


# ================================================================ middleware

def test_requests_not_from_ingress_get_403_when_running_in_home_assistant(client, in_home_assistant):
    for path in ("/", "/api/state", "/api/diag", "/static/index.html"):
        r = client.get(path)                                         # TestClient's address is "testclient"
        assert r.status_code == 403, path
        assert r.json() == {"detail": "Open Friend Reminder from Home Assistant."}
    assert client.post("/api/friends", json={"friends": [{"name": "A"}]}).status_code == 403
    assert friends.all_rows() == []


@pytest.mark.parametrize("host", ["127.0.0.1", "192.168.1.20", "172.30.32.1", "172.30.32.3", "::1", "not-an-ip"])
def test_other_addresses_are_refused_in_home_assistant(client_from, in_home_assistant, host):
    assert client_from(host).get("/api/diag").status_code == 403


def test_the_ingress_proxy_is_allowed_in_home_assistant(client_from, in_home_assistant):
    c = client_from("172.30.32.2")
    assert c.get("/api/diag").status_code == 200
    assert c.post("/api/friends", json={"friends": [{"name": "A"}]}).status_code == 200
    assert c.get("/").status_code == 200


def test_everyone_is_allowed_outside_home_assistant(client_from):
    assert client_from("203.0.113.9").get("/api/diag").status_code == 200


def test_oversized_request_bodies_get_413(client):
    r = client.post("/api/diag", content=b"x" * 1_000_001, headers={"content-type": "application/json"})
    assert r.status_code == 413
    assert client.get("/api/diag").json() == {}


# ---------------------------------------------------------------- other add-ons (e.g. Daily Briefing)

PEER = "172.30.33.17"          # another add-on container on Home Assistant's internal network


def test_another_add_on_can_read_a_slim_state(client_from, in_home_assistant, monkeypatch, today):
    monkeypatch.setattr(ha, "_call", lambda *a, **k: None)
    client_from("172.30.32.2").post("/api/friends", json={"friends": [
        {"name": "Mike", "phone": "303-555-0101", "email": "m@example.com", "notes": "private",
         "last_contact": (today - datetime.timedelta(days=40)).isoformat()}]})
    r = client_from(PEER).get("/api/state")
    assert r.status_code == 200
    body = r.json()
    assert body["settings"] == {"nudges_per_day": 1}
    assert body["friends"] == [{"name": "Mike", "days_since": 40, "never_logged": False,
                                "birthday_today": False, "due": True, "snoozed": False}]
    assert "private" not in r.text and "303-555" not in r.text and "m@example.com" not in r.text


@pytest.mark.parametrize("method,path", [
    ("post", "/api/friends/1/done"), ("post", "/api/friends"), ("delete", "/api/friends/1"),
    ("get", "/"), ("get", "/api/diag"), ("post", "/api/nudge/test"),
])
def test_another_add_on_cannot_write_or_open_anything_else(client_from, in_home_assistant, method, path):
    r = getattr(client_from(PEER), method)(path)
    assert r.status_code == 403


def test_outside_the_add_on_network_state_stays_closed(client_from, in_home_assistant):
    assert client_from("192.168.1.50").get("/api/state").status_code == 403


def test_the_ingress_page_still_gets_the_full_state(client_from, in_home_assistant, monkeypatch):
    monkeypatch.setattr(ha, "_call", lambda *a, **k: None)
    body = client_from("172.30.32.2").get("/api/state").json()
    assert "tiers" in body and "notify_service" in body["settings"]