"""ranking.py: pure functions over friend dicts (no database)."""
import datetime

import pytest

import ranking

TODAY = datetime.date(2026, 10, 16)


def ago(days, today=TODAY):
    return (today - datetime.timedelta(days=days)).isoformat()


def F(id=1, name="Alex", tier="good", **kw):
    f = {"id": id, "name": name, "tier": tier, "interval_days": None, "last_contact": None,
         "birthday": None, "snoozed_until": None, "added": ago(1000)}
    f.update(kw)
    return f


def names(friends):
    return [f["name"] for f in friends]


# ---------------------------------------------------------------- interval

@pytest.mark.parametrize("tier,days", [("close", 14), ("good", 30), ("casual", 90)])
def test_interval_from_tier(tier, days):
    assert ranking.interval(F(tier=tier)) == days


def test_interval_override_beats_tier():
    assert ranking.interval(F(tier="casual", interval_days=7)) == 7
    assert ranking.interval(F(tier="close", interval_days=365)) == 365


@pytest.mark.parametrize("bad", [None, 0, -5, "", "abc"])
def test_interval_ignores_unusable_override(bad):
    assert ranking.interval(F(tier="close", interval_days=bad)) == 14


def test_interval_unknown_or_missing_tier_falls_back_to_good():
    assert ranking.interval(F(tier="mystery")) == 30
    assert ranking.interval({"interval_days": None}) == 30


def test_interval_override_given_as_numeric_string():
    assert ranking.interval(F(interval_days="21")) == 21


# ---------------------------------------------------------------- score and due

def test_exactly_interval_days_is_due():
    a = ranking.assess(F(tier="good", last_contact=ago(30)), TODAY)
    assert a["days_since"] == 30
    assert a["score"] == 1.0
    assert a["due"] is True


def test_one_day_short_is_not_due():
    a = ranking.assess(F(tier="good", last_contact=ago(29)), TODAY)
    assert a["due"] is False
    assert a["score"] == pytest.approx(0.967, abs=0.001)


def test_past_the_interval_scores_above_one():
    a = ranking.assess(F(tier="close", last_contact=ago(28)), TODAY)
    assert a["score"] == 2.0 and a["due"] is True


def test_boundary_uses_the_override_interval():
    assert ranking.assess(F(tier="casual", interval_days=10, last_contact=ago(10)), TODAY)["due"] is True
    assert ranking.assess(F(tier="casual", interval_days=10, last_contact=ago(9)), TODAY)["due"] is False


def test_talked_today_scores_zero():
    a = ranking.assess(F(last_contact=TODAY.isoformat()), TODAY)
    assert (a["days_since"], a["score"], a["due"]) == (0, 0.0, False)


def test_last_contact_in_the_future_never_goes_negative():
    a = ranking.assess(F(last_contact=(TODAY + datetime.timedelta(days=5)).isoformat()), TODAY)
    assert a["days_since"] == 0 and a["score"] == 0.0 and a["due"] is False


def test_never_logged_friend_counts_from_added():
    a = ranking.assess(F(tier="good", last_contact=None, added=ago(40)), TODAY)
    assert a["never_logged"] is True
    assert a["days_since"] == 40 and a["due"] is True
    fresh = ranking.assess(F(tier="good", last_contact=None, added=ago(5)), TODAY)
    assert fresh["never_logged"] is True and fresh["due"] is False and fresh["days_since"] == 5


def test_last_contact_wins_over_added():
    a = ranking.assess(F(last_contact=ago(3), added=ago(400)), TODAY)
    assert a["days_since"] == 3 and a["never_logged"] is False


def test_no_dates_at_all_counts_from_today():
    a = ranking.assess({"id": 1, "name": "X", "tier": "good"}, TODAY)
    assert a["days_since"] == 0 and a["due"] is False


def test_assess_keeps_the_row_and_adds_the_derived_fields():
    a = ranking.assess(F(name="Mike", tier="close", last_contact=ago(7)), TODAY)
    assert a["name"] == "Mike" and a["id"] == 1
    assert a["tier_label"] == "Close" and a["interval"] == 14
    assert {"score", "due", "never_logged", "talked_today", "birthday_in", "birthday_today", "snoozed",
            "next_due", "days_since"} <= set(a)


def test_assess_does_not_mutate_its_input():
    f = F(last_contact=ago(7))
    before = dict(f)
    ranking.assess(f, TODAY)
    assert f == before


# ---------------------------------------------------------------- birthday parsing

@pytest.mark.parametrize("text,expected", [
    ("03-14", (3, 14)),
    ("1990-03-14", (3, 14)),
    ("12-31", (12, 31)),
    ("01-01", (1, 1)),
    ("02-29", (2, 29)),            # accepted: someone can be born on Feb 29
    ("2000-02-29", (2, 29)),
    ("  03-14  ", (3, 14)),
])
def test_parse_birthday_valid(text, expected):
    assert ranking.parse_birthday(text) == expected


@pytest.mark.parametrize("text", [
    None, "", "   ", "13-01", "00-10", "02-30", "04-31", "03-00", "1990-02-30", "2023-02-29",
    "abc", "03/14", "1990-13-01", "1-2-3-4", "-3-14", "12",
])
def test_parse_birthday_invalid_or_empty(text):
    assert ranking.parse_birthday(text) is None


def test_days_to_birthday_today_and_tomorrow():
    assert ranking.days_to_birthday("10-16", TODAY) == 0
    assert ranking.days_to_birthday("10-17", TODAY) == 1


def test_days_to_birthday_already_passed_this_year_counts_to_next_year():
    assert ranking.days_to_birthday("10-15", TODAY) == 364          # 2026-10-16 -> 2027-10-15


def test_birth_year_is_ignored():
    assert ranking.days_to_birthday("1990-10-16", TODAY) == 0


def test_days_to_birthday_none_when_missing_or_invalid():
    assert ranking.days_to_birthday(None, TODAY) is None
    assert ranking.days_to_birthday("13-45", TODAY) is None


def test_year_rollover_dec_31_to_jan_1():
    assert ranking.days_to_birthday("01-01", datetime.date(2026, 12, 31)) == 1
    assert ranking.days_to_birthday("12-31", datetime.date(2026, 12, 31)) == 0
    a = ranking.assess(F(birthday="01-01"), datetime.date(2026, 12, 31))
    assert a["birthday_in"] == 1 and a["birthday_today"] is False


def test_year_rollover_leap_year_length():
    assert ranking.days_to_birthday("01-01", datetime.date(2027, 12, 31)) == 1
    assert ranking.days_to_birthday("12-30", datetime.date(2028, 12, 31)) == 364   # 2029 is not a leap year


def test_feb_29_in_a_common_year_falls_on_feb_28():
    assert ranking.days_to_birthday("02-29", datetime.date(2026, 2, 28)) == 0
    assert ranking.days_to_birthday("02-29", datetime.date(2026, 2, 27)) == 1
    a = ranking.assess(F(birthday="02-29"), datetime.date(2026, 2, 28))
    assert a["birthday_today"] is True


def test_feb_29_after_feb_28_in_a_common_year_rolls_to_next_year():
    assert ranking.days_to_birthday("02-29", datetime.date(2026, 3, 1)) == 364      # 2027-02-28


def test_feb_29_in_a_leap_year_is_feb_29():
    assert ranking.days_to_birthday("02-29", datetime.date(2028, 2, 29)) == 0
    assert ranking.days_to_birthday("02-29", datetime.date(2028, 2, 28)) == 1       # not today on the 28th


def test_feb_29_before_a_leap_year_waits_for_the_29th():
    assert ranking.days_to_birthday("02-29", datetime.date(2027, 3, 1)) == 365      # 2028-02-29


def test_birthday_today_false_when_already_talked_today():
    a = ranking.assess(F(birthday="10-16", last_contact=TODAY.isoformat()), TODAY)
    assert a["birthday_in"] == 0
    assert a["talked_today"] is True
    assert a["birthday_today"] is False


def test_birthday_today_true_when_talked_yesterday():
    a = ranking.assess(F(birthday="10-16", last_contact=ago(1)), TODAY)
    assert a["birthday_today"] is True and a["talked_today"] is False


def test_birthday_today_does_not_need_the_friend_to_be_due():
    a = ranking.assess(F(tier="casual", birthday="10-16", last_contact=ago(2)), TODAY)
    assert a["due"] is False and a["birthday_today"] is True


# ---------------------------------------------------------------- ordering

def test_birthday_today_jumps_the_queue():
    friends = [
        F(1, "Overdue", tier="close", last_contact=ago(100)),
        F(2, "Birthday", tier="casual", last_contact=ago(2), birthday="10-16"),
        F(3, "Mid", tier="good", last_contact=ago(40)),
    ]
    assert names(ranking.rank(friends, TODAY)) == ["Birthday", "Overdue", "Mid"]


def test_rank_sorts_by_score_descending():
    friends = [
        F(1, "A", tier="good", last_contact=ago(15)),        # 0.5
        F(2, "B", tier="good", last_contact=ago(60)),        # 2.0
        F(3, "C", tier="close", last_contact=ago(14)),       # 1.0
        F(4, "D", tier="casual", last_contact=ago(9)),       # 0.1
    ]
    assert names(ranking.rank(friends, TODAY)) == ["B", "C", "A", "D"]


def test_score_ties_break_close_then_good_then_casual():
    friends = [
        F(1, "Casual", tier="casual", last_contact=ago(90)),
        F(2, "Close", tier="close", last_contact=ago(14)),
        F(3, "Good", tier="good", last_contact=ago(30)),
    ]
    ranked = ranking.rank(friends, TODAY)
    assert {a["score"] for a in ranked} == {1.0}
    assert names(ranked) == ["Close", "Good", "Casual"]


def test_same_score_and_tier_orders_by_name_ignoring_case():
    friends = [
        F(1, "zoe", last_contact=ago(30)),
        F(2, "Bob", last_contact=ago(30)),
        F(3, "alice", last_contact=ago(30)),
    ]
    assert names(ranking.rank(friends, TODAY)) == ["alice", "Bob", "zoe"]


def test_identical_name_tier_and_score_falls_back_to_id():
    friends = [F(7, "Sam", last_contact=ago(30)), F(3, "Sam", last_contact=ago(30))]
    assert [a["id"] for a in ranking.rank(friends, TODAY)] == [3, 7]


def test_several_birthdays_today_are_ordered_by_score():
    friends = [
        F(1, "LowScore", birthday="10-16", last_contact=ago(5)),
        F(2, "HighScore", birthday="10-16", last_contact=ago(60)),
        F(3, "Overdue", last_contact=ago(500)),
    ]
    assert names(ranking.rank(friends, TODAY)) == ["HighScore", "LowScore", "Overdue"]


def test_overdue_friends_rank_ahead_of_not_due_ones():
    friends = [F(1, "Fresh", last_contact=ago(1)), F(2, "Stale", last_contact=ago(31))]
    ranked = ranking.rank(friends, TODAY)
    assert names(ranked) == ["Stale", "Fresh"]
    assert [a["due"] for a in ranked] == [True, False]


def test_rank_returns_everyone_and_handles_an_empty_list():
    assert ranking.rank([], TODAY) == []
    assert len(ranking.rank([F(1), F(2, "B"), F(3, "C")], TODAY)) == 3


# ---------------------------------------------------------------- snooze

def test_snoozed_until_is_exclusive_of_today():
    tomorrow = (TODAY + datetime.timedelta(days=1)).isoformat()
    assert ranking.assess(F(snoozed_until=tomorrow), TODAY)["snoozed"] is True
    assert ranking.assess(F(snoozed_until=TODAY.isoformat()), TODAY)["snoozed"] is False
    assert ranking.assess(F(snoozed_until=ago(1)), TODAY)["snoozed"] is False
    assert ranking.assess(F(snoozed_until=None), TODAY)["snoozed"] is False


def test_snoozed_friend_is_left_out_of_nudges_but_still_ranked():
    tomorrow = (TODAY + datetime.timedelta(days=1)).isoformat()
    friends = [F(1, "Snoozed", last_contact=ago(90), snoozed_until=tomorrow),
               F(2, "Awake", last_contact=ago(31))]
    assert names(ranking.nudge_candidates(friends, TODAY)) == ["Awake"]
    assert names(ranking.rank(friends, TODAY)) == ["Snoozed", "Awake"]


def test_birthday_still_nudges_while_snoozed():
    tomorrow = (TODAY + datetime.timedelta(days=1)).isoformat()
    friends = [F(1, "Bday", last_contact=ago(2), birthday="10-16", snoozed_until=tomorrow),
               F(2, "Awake", last_contact=ago(31))]
    assert names(ranking.nudge_candidates(friends, TODAY)) == ["Bday", "Awake"]


def test_expired_snooze_makes_the_friend_nudgeable_again():
    friends = [F(1, "Back", last_contact=ago(40), snoozed_until=TODAY.isoformat())]
    assert names(ranking.nudge_candidates(friends, TODAY)) == ["Back"]


def test_not_due_friends_are_never_nudged():
    friends = [F(1, "Fine", last_contact=ago(29)), F(2, "AlsoFine", tier="casual", last_contact=ago(89))]
    assert ranking.nudge_candidates(friends, TODAY) == []


def test_birthday_friend_who_was_talked_to_today_is_not_nudged():
    friends = [F(1, "Done", birthday="10-16", last_contact=TODAY.isoformat())]
    assert ranking.nudge_candidates(friends, TODAY) == []


# ---------------------------------------------------------------- next_due

def test_next_due_is_last_contact_plus_interval():
    a = ranking.assess(F(tier="good", last_contact=ago(10)), TODAY)
    assert a["next_due"] == (TODAY + datetime.timedelta(days=20)).isoformat()


def test_next_due_is_today_when_already_overdue():
    a = ranking.assess(F(tier="good", last_contact=ago(45)), TODAY)
    assert a["next_due"] == TODAY.isoformat()


def test_next_due_with_a_snooze_later_than_the_interval():
    until = TODAY + datetime.timedelta(days=3)
    a = ranking.assess(F(tier="good", last_contact=ago(45), snoozed_until=until.isoformat()), TODAY)
    assert a["snoozed"] is True and a["next_due"] == until.isoformat()


def test_next_due_ignores_a_snooze_earlier_than_the_interval():
    a = ranking.assess(F(tier="good", last_contact=ago(5),
                         snoozed_until=(TODAY + datetime.timedelta(days=2)).isoformat()), TODAY)
    assert a["next_due"] == (TODAY + datetime.timedelta(days=25)).isoformat()


def test_next_due_ignores_an_expired_snooze():
    a = ranking.assess(F(tier="good", last_contact=ago(45), snoozed_until=ago(2)), TODAY)
    assert a["snoozed"] is False and a["next_due"] == TODAY.isoformat()


def test_next_due_uses_the_override_interval():
    a = ranking.assess(F(tier="casual", interval_days=7, last_contact=ago(2)), TODAY)
    assert a["next_due"] == (TODAY + datetime.timedelta(days=5)).isoformat()


def test_next_due_for_a_never_logged_friend_counts_from_added():
    a = ranking.assess(F(tier="close", last_contact=None, added=ago(4)), TODAY)
    assert a["next_due"] == (TODAY + datetime.timedelta(days=10)).isoformat()


# ---------------------------------------------------------------- pick_nudges

def _three_due():
    return [F(1, "A", last_contact=ago(31)), F(2, "B", last_contact=ago(60)), F(3, "C", last_contact=ago(45))]


def test_pick_nudges_n_zero_sends_nobody():
    assert ranking.pick_nudges(_three_due(), TODAY, 0) == []


def test_pick_nudges_n_one_is_the_most_overdue():
    assert names(ranking.pick_nudges(_three_due(), TODAY, 1)) == ["B"]


def test_pick_nudges_n_two_is_the_top_two_in_order():
    assert names(ranking.pick_nudges(_three_due(), TODAY, 2)) == ["B", "C"]


def test_pick_nudges_with_fewer_candidates_than_n():
    assert names(ranking.pick_nudges([F(1, "Only", last_contact=ago(31))], TODAY, 2)) == ["Only"]
    assert ranking.pick_nudges([], TODAY, 2) == []


def test_pick_nudges_negative_n_is_treated_as_zero():
    assert ranking.pick_nudges(_three_due(), TODAY, -1) == []


def test_pick_nudges_puts_the_birthday_first_even_when_n_is_one():
    friends = _three_due() + [F(4, "Bday", tier="casual", last_contact=ago(1), birthday="10-16")]
    assert names(ranking.pick_nudges(friends, TODAY, 1)) == ["Bday"]
    assert names(ranking.pick_nudges(friends, TODAY, 2)) == ["Bday", "B"]
