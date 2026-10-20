"""addons.py: the sections built from the other add-ons (sensors and HTTP), with both faked."""
import datetime
import urllib.error

import pytest

import addons
from addons import Off
from conftest import TZ

TODAY, TOMORROW = "2026-10-19", "2026-10-20"


def sensor(fake_ha, entity, state, **attrs):
    fake_ha.states[entity] = {"state": state, "attributes": attrs}


# ---------------------------------------------------------------- workout
def test_workout_from_sensors(fake_ha):
    sensor(fake_ha, "sensor.workout_today", "Strength: Upper", exercises=["Bench 3x8", "Row 3x10"], cardio="20 min bike")
    sensor(fake_ha, "sensor.workout_streak", "5")
    s = addons.workout()
    assert s["headline"] == "Strength: Upper · 5-day streak"
    assert s["lines"] == ["Strength: Upper", "Bench 3x8", "Row 3x10", "20 min bike", "Streak: 5 days"]


def test_workout_rest_day_without_streak_sensor(fake_ha):
    sensor(fake_ha, "sensor.workout_today", "Rest day")
    assert addons.workout() == {"headline": "Rest day", "lines": ["Rest day"]}


def test_workout_singular_streak(fake_ha):
    sensor(fake_ha, "sensor.workout_today", "Done")
    sensor(fake_ha, "sensor.workout_streak", "1")
    assert addons.workout()["lines"][-1] == "Streak: 1 day"


def test_workout_missing_or_unavailable_sensor_is_off(fake_ha):
    with pytest.raises(Off):
        addons.workout()
    sensor(fake_ha, "sensor.workout_today", "unavailable")
    with pytest.raises(Off):
        addons.workout()


# ---------------------------------------------------------------- meals
def meal(slot, name, cooked=False):
    return {"slot": slot, "name": name, "cooked": cooked}


def test_meals_today_with_prep_and_use_up(fake_addons):
    fake_addons.data[("meals", f"/meals/today?date={TODAY}")] = {"meals": [meal("dinner", "Tacos"), meal("breakfast", "Oats", True)]}
    fake_addons.data[("meals", f"/meals/today?date={TOMORROW}")] = {"meals": [meal("lunch", "Soup"), meal("dinner", "Pasta")]}
    fake_addons.data[("meals", "/meals/pantry")] = {"use_soon": [
        {"name": "Spinach", "expires": TOMORROW}, {"name": "Rice", "expires": "2026-10-23"}]}
    s = addons.meals()
    assert s["headline"] == "Dinner: Tacos"
    assert s["lines"] == ["Breakfast: Oats (cooked)", "Dinner: Tacos", "Prep for tomorrow: Soup, Pasta", "Use up: Spinach"]


def test_meals_nothing_planned(fake_addons):
    fake_addons.data[("meals", f"/meals/today?date={TODAY}")] = {"meals": []}
    fake_addons.data[("meals", f"/meals/today?date={TOMORROW}")] = {"meals": []}
    fake_addons.data[("meals", "/meals/pantry")] = {"use_soon": []}
    assert addons.meals()["headline"] == "Nothing planned"


def test_meals_keep_today_when_prep_lookup_fails(fake_addons):
    fake_addons.data[("meals", f"/meals/today?date={TODAY}")] = {"meals": [meal("dinner", "Tacos")]}
    fake_addons.data[("meals", f"/meals/today?date={TOMORROW}")] = urllib.error.URLError("down")
    assert addons.meals()["lines"] == ["Dinner: Tacos"]


def test_meals_unreachable_raises(fake_addons):
    fake_addons.data[("meals", f"/meals/today?date={TODAY}")] = urllib.error.URLError("down")
    with pytest.raises(urllib.error.URLError):
        addons.meals()


# ---------------------------------------------------------------- due today
def test_due_combines_maintenance_and_work(fake_ha, fake_addons, set_options):
    set_options(api_key="wt-key")
    sensor(fake_ha, "sensor.home_maintenance_due", "2", due_tasks=["Change furnace filter", "Test smoke alarms"])
    fake_addons.data[("work", "/api/state")] = {"tasks": [
        {"title": "Send report", "client": "KISS", "due": TODAY},
        {"title": "Overdue thing", "due": "2026-10-15"},
        {"title": "Later", "due": TOMORROW},
        {"title": "Snoozed", "due": TODAY, "snoozed_until": "2026-10-21T08:00:00"},
        {"title": "Finished", "due": TODAY, "done_at": "2026-10-19T07:00:00"},
        {"title": "No date"}]}
    s = addons.due()
    assert s["headline"] == "4 due"
    assert s["lines"] == ["Home: Change furnace filter", "Home: Test smoke alarms", "Work: Send report (KISS)", "Work: Overdue thing"]
    assert fake_addons.calls == [("work", "/api/state", "wt-key")]


def test_due_nothing(fake_ha, fake_addons, set_options):
    set_options(api_key="k")
    sensor(fake_ha, "sensor.home_maintenance_due", "0", due_tasks=[])
    fake_addons.data[("work", "/api/state")] = {"tasks": []}
    assert addons.due() == {"headline": "Nothing due", "lines": ["Nothing due today"]}


def test_due_without_work_key_uses_maintenance_only(fake_ha, fake_addons):
    sensor(fake_ha, "sensor.home_maintenance_due", "1", due_tasks=["Gutters"])
    assert addons.due()["lines"] == ["Home: Gutters"] and fake_addons.calls == []


def test_due_nothing_configured_is_off(fake_ha, fake_addons):
    with pytest.raises(Off):
        addons.due()


def test_due_one_source_down_still_shows_the_other(fake_ha, fake_addons, set_options):
    set_options(api_key="k")
    sensor(fake_ha, "sensor.home_maintenance_due", "1", due_tasks=["Gutters"])
    fake_addons.data[("work", "/api/state")] = urllib.error.URLError("down")
    assert addons.due()["lines"] == ["Home: Gutters"]


def test_due_every_source_down_is_unavailable(fake_ha, fake_addons, set_options, monkeypatch):
    set_options(api_key="k")
    fake_addons.data[("work", "/api/state")] = urllib.error.URLError("down")

    def ha_down(entity_id):
        raise urllib.error.URLError("Home Assistant down")
    monkeypatch.setattr(addons.ha, "state", ha_down)
    with pytest.raises(RuntimeError, match="no source answered"):
        addons.due()

def test_due_truncates_long_lists(fake_ha, fake_addons):
    sensor(fake_ha, "sensor.home_maintenance_due", "10", due_tasks=[f"Task {i}" for i in range(10)])
    s = addons.due()
    assert s["headline"] == "10 due" and len(s["lines"]) == 9 and s["lines"][-1] == "+ 2 more"


# ---------------------------------------------------------------- ski
BEST = {"resort": "Eldora", "id": "eldora", "fresh_in": 6.0, "tmax_f": 28.4, "gust_mph": 31.2, "leave": {"leave_at": "06:45"}}


def test_ski_in_season(fake_addons, monkeypatch):
    monkeypatch.setattr(addons.sections_ha, "now", lambda: datetime.datetime(2026, 1, 15, 8, tzinfo=TZ))
    fake_addons.data[("ski", "/api/live")] = {"eldora": {"lifts_open": 9, "lifts_total": 12}, "other": None}
    fake_addons.data[("ski", "/api/best-days")] = [BEST]
    s = addons.ski()
    assert s["headline"] == "Eldora"
    assert s["lines"] == ["Best today: Eldora (6 in fresh, high 28°F, gusts 31 mph)", "Leave by 6:45 AM", "Lifts open: 9 of 12"]


def test_ski_off_season_when_no_lifts_run(fake_addons):          # the default test date is in October
    fake_addons.data[("ski", "/api/live")] = {"eldora": {"lifts_open": 0, "lifts_total": 12}}
    with pytest.raises(Off):
        addons.ski()


def test_ski_early_opening_counts_as_season(fake_addons):
    fake_addons.data[("ski", "/api/live")] = {"abasin": {"lifts_open": 3, "lifts_total": 9}}
    fake_addons.data[("ski", "/api/best-days")] = [{"resort": "Arapahoe Basin", "id": "abasin"}]
    assert addons.ski()["headline"] == "Arapahoe Basin"


def test_ski_off_season_and_unreachable_is_unavailable(fake_addons):
    fake_addons.data[("ski", "/api/live")] = urllib.error.URLError("down")
    with pytest.raises(urllib.error.URLError):
        addons.ski()


def test_hhmm_handles_iso_and_junk():
    assert addons._hhmm("2026-10-19T14:05:00-06:00") == "2:05 PM"
    assert addons._hhmm("soon") == "soon"


# ---------------------------------------------------------------- money
def test_money_summary(fake_addons, set_options):
    set_options(api_token="b-token")
    fake_addons.data[("money", "/api/summary")] = {
        "spent": 1234.5, "budgeted": 3000, "safeToSpend": {"weekly": 400, "left": 212.4, "daysLeft": 3},
        "overBudget": [{"category": "Dining"}, {"category": "Fun"}]}
    s = addons.money()
    assert s["headline"] == "$212 left to spend this week"
    assert s["lines"] == ["$212 left to spend this week", "3 days left in the week", "Spent $1,234 of $3,000 this month", "Over budget: Dining, Fun"]
    assert fake_addons.calls == [("money", "/api/summary", "b-token")]


def test_money_over_the_allowance(fake_addons, set_options):
    set_options(api_token="t")
    fake_addons.data[("money", "/api/summary")] = {"spent": 10, "budgeted": 20, "safeToSpend": {"left": -35}}
    assert addons.money()["headline"] == "$35 over the weekly allowance"


def test_money_without_allowance_falls_back_to_the_month(fake_addons, set_options):
    set_options(api_token="t")
    fake_addons.data[("money", "/api/summary")] = {"spent": 500, "budgeted": 2000, "safeToSpend": None}
    s = addons.money()
    assert s["headline"] == "$500 of $2,000 spent" and s["lines"] == ["Spent $500 of $2,000 this month"]


def test_money_without_token_is_off(fake_addons):
    with pytest.raises(Off):
        addons.money()
    assert fake_addons.calls == []


def test_money_bad_token_is_unavailable(fake_addons, set_options):
    set_options(api_token="wrong")
    fake_addons.data[("money", "/api/summary")] = urllib.error.HTTPError("u", 401, "unauthorized", {}, None)
    with pytest.raises(urllib.error.HTTPError):
        addons.money()
