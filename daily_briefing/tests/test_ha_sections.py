"""ha.py and sections_ha.py (Today, Shopping) against a fake Home Assistant."""
import datetime
import urllib.error

import config
import ha
import sections_ha
from conftest import MONDAY_8AM, TZ


def ev(summary, start, end=None, all_day=False):
    if all_day:
        d = start
        return {"summary": summary, "start": {"date": d}, "end": {"date": end or (datetime.date.fromisoformat(d) + datetime.timedelta(days=1)).isoformat()}}
    return {"summary": summary, "start": {"dateTime": start}, "end": {"dateTime": end or start}}


# ---------------------------------------------------------------- config
def test_options_defaults_and_clamps(set_options):
    o = config.options()
    assert o["morning_time"] == "07:00" and o["refresh_seconds"] == 60 and o["calendars"] == []
    set_options(refresh_seconds=5, calendars=[" calendar.family ", "", 3], api_token="  abc\n")
    o = config.options()
    assert o["refresh_seconds"] == 30 and o["calendars"] == ["calendar.family"] and o["api_token"] == "abc"
    set_options(refresh_seconds="oops")
    assert config.options()["refresh_seconds"] == 60


# ---------------------------------------------------------------- ha
def test_state_none_when_missing(fake_ha):
    assert ha.state("sensor.nope") is None
    fake_ha.states["sensor.x"] = {"state": "1", "attributes": {}}
    assert ha.state("sensor.x")["state"] == "1"


def test_state_raises_other_errors(monkeypatch, fake_ha):
    def boom(*a, **k):
        raise urllib.error.HTTPError("u", 500, "err", {}, None)
    monkeypatch.setattr(ha, "_call", boom)
    try:
        ha.state("sensor.x")
    except urllib.error.HTTPError as e:
        assert e.code == 500
    else:
        raise AssertionError("a 500 must not look like a missing entity")


def test_publish_only_writes_changes(fake_ha, monkeypatch):
    assert ha.publish("sensor.daily_briefing_a", "x", {"lines": ["1"]}) is True
    assert ha.publish("sensor.daily_briefing_a", "x", {"lines": ["1"]}) is False
    assert ha.publish("sensor.daily_briefing_a", "y", {"lines": ["1"]}) is True
    assert ha.publish("sensor.daily_briefing_a", "y", {"lines": ["2"]}) is True
    assert len(fake_ha.writes) == 3
    # Home Assistant forgets API-made sensors on restart, so an unchanged value is rewritten every 15 minutes
    sig, _ = ha._published["sensor.daily_briefing_a"]
    ha._published["sensor.daily_briefing_a"] = (sig, 0.0)
    assert ha.publish("sensor.daily_briefing_a", "y", {"lines": ["2"]}) is True


def test_publish_truncates_state_to_255(fake_ha):
    ha.publish("sensor.daily_briefing_a", "z" * 400, {})
    assert len(fake_ha.writes[0][1]) == 255


def test_notify_service_option_wins_and_strips_prefix(fake_ha, set_options):
    set_options(notify_service="notify.mobile_app_pixel_9")
    assert ha.notify_service() == "mobile_app_pixel_9"


def test_notify_service_finds_the_only_phone(fake_ha):
    fake_ha.phones = ["mobile_app_pixel_9"]
    assert ha.notify_service() == "mobile_app_pixel_9"


def test_notify_service_two_phones_is_ambiguous(fake_ha):
    fake_ha.phones = ["mobile_app_a", "mobile_app_b"]
    assert ha.notify_service() == ""


def test_send_summary_opens_the_add_on_page(fake_ha):
    ha.send_summary("mobile_app_pixel_9", "Good morning", "text")
    svc, body = fake_ha.notifications[0]
    assert svc == "mobile_app_pixel_9" and body["message"] == "text"
    assert body["data"]["clickAction"] == "/hassio/ingress/c0a16a5a_daily_briefing" and body["data"]["tag"] == "daily-briefing"


def test_send_summary_unknown_service_is_explained(monkeypatch, fake_ha):
    real = ha._call

    def deny(method, url, body=None, timeout=10):
        if "/services/notify/" in url:
            raise urllib.error.HTTPError(url, 404, "nf", {}, None)
        return real(method, url, body, timeout)
    monkeypatch.setattr(ha, "_call", deny)
    try:
        ha.send_summary("nope", "t", "m")
    except RuntimeError as e:
        assert "notify.nope" in str(e)
    else:
        raise AssertionError("expected RuntimeError")


# ---------------------------------------------------------------- Today
def test_clock_formats():
    assert sections_ha.clock(MONDAY_8AM.replace(hour=0, minute=5)) == "12:05 AM"
    assert sections_ha.clock(MONDAY_8AM.replace(hour=12)) == "12:00 PM"
    assert sections_ha.clock(MONDAY_8AM.replace(hour=15, minute=30)) == "3:30 PM"


def test_today_lists_events_all_day_first_then_by_time(fake_ha):
    fake_ha.states.update({"calendar.family": {"state": "off", "attributes": {}},
                           "calendar.me": {"state": "off", "attributes": {}}})
    fake_ha.calendars["calendar.family"] = [ev("Dentist", "2026-10-19T14:00:00-06:00"), ev("Trash day", "2026-10-19", all_day=True)]
    fake_ha.calendars["calendar.me"] = [ev("Standup", "2026-10-19T09:30:00-06:00"),
                                        ev("Dentist", "2026-10-19T14:00:00-06:00")]       # same event on two calendars
    s = sections_ha.today_section()
    assert s["lines"][0] == "Monday, October 19"
    events = s["lines"][s["lines"].index("") + 1:]
    assert events == ["Trash day", "9:30 AM  Standup", "2:00 PM  Dentist"]
    assert s["events"] == 3 and s["headline"] == "Mon Oct 19"


def test_today_ignores_events_of_other_days(fake_ha):
    fake_ha.states["calendar.me"] = {"state": "off", "attributes": {}}
    fake_ha.calendars["calendar.me"] = [ev("Yesterday thing", "2026-10-18T09:00:00-06:00"),
                                        ev("Multi-day trip", "2026-10-17", end="2026-10-19", all_day=True),   # ended Oct 18
                                        ev("Away", "2026-10-18", end="2026-10-21", all_day=True)]              # covers today
    s = sections_ha.today_section()
    assert [l for l in s["lines"][2:] if l] == ["Away"]


def test_today_skips_holiday_and_birthday_calendars_by_default(fake_ha):
    for c in ("calendar.family", "calendar.holidays_in_united_states", "calendar.birthdays"):
        fake_ha.states[c] = {"state": "off", "attributes": {}}
        fake_ha.calendars[c] = [ev(c, "2026-10-19T10:00:00-06:00")]
    s = sections_ha.today_section()
    assert any("calendar.family" in l for l in s["lines"])
    assert not any("birthdays" in l or "holidays" in l for l in s["lines"])


def test_today_uses_the_chosen_calendars(fake_ha, set_options):
    set_options(calendars=["calendar.birthdays"])
    fake_ha.states["calendar.birthdays"] = {"state": "off", "attributes": {}}
    fake_ha.calendars["calendar.birthdays"] = [ev("Sam's birthday", "2026-10-19", all_day=True)]
    assert "Sam's birthday" in sections_ha.today_section()["lines"]


def test_today_one_broken_calendar_does_not_hide_the_others(fake_ha):
    fake_ha.states.update({"calendar.a": {"state": "off", "attributes": {}}, "calendar.b": {"state": "off", "attributes": {}}})
    fake_ha.calendars["calendar.a"] = RuntimeError("down")
    fake_ha.calendars["calendar.b"] = [ev("Lunch", "2026-10-19T12:00:00-06:00")]
    assert "12:00 PM  Lunch" in sections_ha.today_section()["lines"]


def test_today_says_so_when_every_calendar_fails(fake_ha):
    fake_ha.states["calendar.a"] = {"state": "off", "attributes": {}}
    fake_ha.calendars["calendar.a"] = RuntimeError("down")
    assert "calendar unavailable" in sections_ha.today_section()["lines"]


def test_today_empty_calendar(fake_ha):
    fake_ha.states["calendar.a"] = {"state": "off", "attributes": {}}
    fake_ha.calendars["calendar.a"] = []
    assert "Nothing on the calendar" in sections_ha.today_section()["lines"]


def test_today_weather_forecast_and_sun(fake_ha):
    fake_ha.states["weather.home"] = {"state": "partlycloudy", "attributes": {"temperature": 63.4, "temperature_unit": "°F"}}
    fake_ha.states["sun.sun"] = {"state": "above_horizon", "attributes": {
        "next_rising": "2026-10-20T13:10:00+00:00", "next_setting": "2026-10-20T00:20:00+00:00"}}
    fake_ha.responses[("weather", "get_forecasts")] = {"weather.home": {"forecast": [
        {"temperature": 71, "templow": 44, "precipitation_probability": 20}]}}
    lines = sections_ha.today_section()["lines"]
    assert lines[1] == "Partly cloudy, 63°F, high 71°F, low 44°F, 20% chance of rain"
    assert lines[2] == "Sunrise 7:10 AM · Sunset 6:20 PM"


def test_today_weather_without_forecast_still_shows_current(monkeypatch, fake_ha):
    fake_ha.states["weather.home"] = {"state": "sunny", "attributes": {"temperature": 70, "temperature_unit": "°F"}}
    real = ha._call

    def no_forecast(method, url, body=None, timeout=10):
        if "return_response" in url:
            raise RuntimeError("no forecast")
        return real(method, url, body, timeout)
    monkeypatch.setattr(ha, "_call", no_forecast)
    assert sections_ha.today_section()["lines"][1] == "Sunny, 70°F"


def test_today_picks_the_configured_weather_entity(fake_ha, set_options):
    set_options(weather_entity="weather.forecast_home")
    fake_ha.states["weather.home"] = {"state": "sunny", "attributes": {}}
    fake_ha.states["weather.forecast_home"] = {"state": "snowy", "attributes": {}}
    assert sections_ha.today_section()["lines"][1] == "Snow"


# ---------------------------------------------------------------- Shopping
def test_shopping_lists_top_items(fake_ha):
    items = [{"summary": f"item {i}", "status": "needs_action"} for i in range(11)]
    fake_ha.responses[("todo", "get_items")] = {"todo.shopping_list": {"items": items}}
    s = sections_ha.shopping_section()
    assert s["headline"] == "11 items" and s["lines"][:2] == ["item 0", "item 1"] and s["lines"][-1] == "+ 3 more" and len(s["lines"]) == 9


def test_shopping_empty_and_single(fake_ha):
    fake_ha.responses[("todo", "get_items")] = {"todo.shopping_list": {"items": []}}
    assert sections_ha.shopping_section()["headline"] == "Nothing to buy"
    fake_ha.responses[("todo", "get_items")] = {"todo.shopping_list": {"items": [{"summary": "milk"}]}}
    assert sections_ha.shopping_section()["headline"] == "1 item"
