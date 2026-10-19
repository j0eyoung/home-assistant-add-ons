import datetime

import pytest

import db
import hours


def test_round_hours_nearest_quarter():
    assert [hours.round_hours(m) for m in (0, 7, 8, 22, 23, 60, 67, 68)] == [0, 0, 0.25, 0.25, 0.5, 1, 1, 1.25]


def test_timer_survives_restart_and_stops(clock):
    clock("2026-10-19 09:00")
    e, stopped = hours.start("kiss", "9832911", "wave fix")
    assert e["client"] == "KISS" and stopped is None
    clock("2026-10-19 10:30")
    assert hours.running()["id"] == e["id"]          # state is in the database, not memory
    assert hours.minutes_of(hours.running()) == 90
    s = hours.stop()
    assert s["end"] == "2026-10-19 10:30:00" and hours.running() is None
    assert hours.stop() is None


def test_start_switches_running_timer(clock):
    clock("2026-10-19 09:00")
    hours.start("KISS")
    clock("2026-10-19 09:20")
    new, old = hours.start("TORR")
    assert old["client"] == "KISS" and old["end"].endswith("09:20:00")
    assert hours.running()["id"] == new["id"]


def test_validation(clock):
    clock("2026-10-19 09:00")
    for bad in ("", "has space", "x" * 30):
        with pytest.raises(ValueError):
            hours.start(bad)
    with pytest.raises(ValueError):
        hours.start("KISS", "12 34")
    with pytest.raises(ValueError):
        hours.add_manual("KISS", "", "", "2026-10-19", 0)


def test_rounding_is_per_case_per_day(clock):
    clock("2026-10-19 18:00")
    hours.add_manual("KISS", "111", "a", "2026-10-19", 10)     # 10 + 10 = 20 -> 0.25 (not 0 + 0)
    hours.add_manual("KISS", "111", "b", "2026-10-19", 10, "10:00")
    hours.add_manual("KISS", "222", "", "2026-10-19", 50)      # 50 -> 0.75
    hours.add_manual("TORR", "", "", "2026-10-20", 30)
    lines = hours.lines(datetime.date(2026, 10, 19), datetime.date(2026, 10, 20))
    got = {(g["date"], g["client"], g["case_no"]): (g["minutes"], g["hours"]) for g in lines}
    assert got == {("2026-10-19", "KISS", "111"): (20, 0.25), ("2026-10-19", "KISS", "222"): (50, 0.75),
                   ("2026-10-20", "TORR", ""): (30, 0.5)}
    assert [g["notes"] for g in lines][0] == "a; b"


def test_totals_include_running_timer_and_week(clock):
    clock("2026-10-19 09:00")                                  # a Monday
    hours.add_manual("KISS", "", "", "2026-10-18", 600)        # Sunday: previous week
    hours.add_manual("KISS", "", "", "2026-10-19", 60, "07:00")
    hours.start("TORR")
    clock("2026-10-19 09:30")
    t = hours.totals()
    assert t["week_start"] == "2026-10-19"
    assert t["day_minutes"] == 90 and t["week_minutes"] == 90
    assert {c["client"]: c["minutes"] for c in t["week"]} == {"KISS": 60, "TORR": 30}


def test_update_and_delete(clock):
    clock("2026-10-19 09:00")
    e = hours.add_manual("KISS", "", "", "2026-10-19", 30)
    u = hours.update(e["id"], client="torr", billable=False, note="x")
    assert (u["client"], u["billable"], u["note"]) == ("TORR", 0, "x")
    with pytest.raises(ValueError):
        hours.update(e["id"], end="2026-10-18 00:00:00")
    assert hours.delete(e["id"]) and not hours.delete(e["id"])


def test_csv(clock):
    clock("2026-10-19 18:00")
    hours.add_manual("KISS", "111", "wave, fix", "2026-10-19", 50, billable=False)
    out = hours.export_csv(datetime.date(2026, 10, 19), datetime.date(2026, 10, 19)).splitlines()
    assert out[0] == "Date,Client,Case,Billable,Minutes,Hours (0.25),Notes"
    assert out[1] == '2026-10-19,KISS,111,N,50,0.75,"wave, fix"'
