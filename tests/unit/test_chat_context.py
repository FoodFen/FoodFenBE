"""render_user_context: pure text rendering of the user's own data for the chat model."""

from __future__ import annotations

from datetime import UTC, date, datetime

from src.application.chat_context import WINDOW_DAYS, render_activity_context, render_user_context
from src.domain.entities.daily_goal import DailyGoal
from src.domain.entities.activity_log import ActivityLog
from src.domain.entities.food_entry import FoodEntry
from src.domain.entities.streak import Streak
from src.domain.entities.user import User
from src.domain.entities.water_log import WaterLog
from src.domain.entities.weight_log import WeightLog
from src.domain.enums import ActivityLevel, DietType, Gender, InputMethod, MealType

TODAY = date(2026, 10, 5)


def _user(**overrides) -> User:
    fields = dict(
        email="a@b.co",
        id=1,
        gender=Gender.FEMALE,
        birth_year=2006,
        height=160.0,
        weight_current=55.0,
        weight_goal=52.0,
        activity_level=ActivityLevel.MODERATE,
        diet_type=DietType.BALANCED,
    )
    fields.update(overrides)
    return User(**fields)


def _goal(effective: date, kcal: int) -> DailyGoal:
    return DailyGoal.create(1, kcal, 200.0, 100.0, 60.0, 2000, effective, client_id=f"g-{kcal}")


def _entry(name: str, day: date, kcal: int, meal: MealType = MealType.LUNCH, hour: int = 12) -> FoodEntry:
    return FoodEntry.create(
        1, name, InputMethod.MANUAL, kcal, 50.0, 30.0, 10.0, meal,
        client_id=f"{name}-{day}",
        logged_on=day,
        logged_at=datetime(day.year, day.month, day.day, hour, tzinfo=UTC),
    )


def test_full_profile_is_rendered():
    text = render_user_context(_user(), [], [], TODAY)

    assert "PROFILE" in text
    assert "- Age: 20" in text
    assert "- Gender: female" in text
    assert "- Height: 160" in text
    assert "- Current weight: 55" in text
    assert "- Goal weight: 52" in text
    assert "- Activity level: moderate" in text
    assert "- Diet type: balanced" in text
    assert "- Units: metric (cm, kg)" in text


def test_empty_user_renders_not_set_everywhere():
    bare = User(email="a@b.co", id=1)

    text = render_user_context(bare, [], [], TODAY)

    assert "PROFILE\n- not set" in text
    assert "DAILY GOAL\n- not set" in text
    assert f"MEALS TODAY ({TODAY.isoformat()})\n- nothing logged yet" in text
    assert text.count(": not logged") == WINDOW_DAYS


def test_missing_user_renders_profile_not_set():
    assert "PROFILE\n- not set" in render_user_context(None, [], [], TODAY)


def test_goal_in_force_is_latest_effective_on_or_before_today():
    goals = [
        _goal(date(2026, 9, 1), 1800),
        _goal(date(2026, 10, 1), 2000),
        _goal(date(2026, 10, 9), 2500),  # future: not in force yet
    ]

    text = render_user_context(_user(), goals, [], TODAY)

    assert "DAILY GOAL\n- 2000 kcal, carbs 200 g, protein 100 g, fat 60 g" in text
    assert "2500" not in text
    assert "1800" not in text


def test_meals_today_lists_only_todays_entries_in_time_order():
    entries = [
        _entry("Pho bo", TODAY, 450, MealType.BREAKFAST, hour=7),
        _entry("Com tam", TODAY, 700, MealType.LUNCH, hour=12),
        _entry("Banh mi", date(2026, 10, 4), 400),
    ]

    text = render_user_context(_user(), [], entries, TODAY)
    today_section = text.split(f"MEALS TODAY ({TODAY.isoformat()})\n")[1].split("\n\n")[0]

    assert today_section.splitlines() == [
        "- breakfast: Pho bo — 450 kcal, C 50 g, P 30 g, F 10 g",
        "- lunch: Com tam — 700 kcal, C 50 g, P 30 g, F 10 g",
    ]


def test_last_days_sums_per_day_oldest_first():
    entries = [
        _entry("A", TODAY, 450),
        _entry("B", TODAY, 700),
        _entry("C", date(2026, 9, 29), 300),  # today - 6: first line of the window
        _entry("D", date(2026, 9, 28), 999),  # outside the window
    ]

    text = render_user_context(_user(), [], entries, TODAY)
    window = text.split("LAST 7 DAYS (daily totals; 'not logged' means unknown, not zero)\n")[1].splitlines()

    assert len(window) == WINDOW_DAYS
    assert window[0] == "- 2026-09-29: 300 kcal, C 50 g, P 30 g, F 10 g"
    assert window[-1] == "- 2026-10-05: 1150 kcal, C 100 g, P 60 g, F 20 g (so far)"
    assert "999" not in text


def test_day_without_entries_is_not_logged_not_zero():
    text = render_user_context(_user(), [], [_entry("A", TODAY, 450)], TODAY)

    assert "- 2026-10-04: not logged" in text
    assert "- 2026-10-04: 0 kcal" not in text


def test_long_meal_name_is_truncated():
    text = render_user_context(_user(), [], [_entry("x" * 200, TODAY, 450)], TODAY)

    assert f"lunch: {'x' * 60} —" in text
    assert "x" * 61 not in text


def test_meals_today_is_capped_with_a_remainder_line():
    entries = [_entry(f"M{i:02d}", TODAY, 100, hour=i) for i in range(18)]

    text = render_user_context(_user(), [], entries, TODAY)
    section = text.split(f"MEALS TODAY ({TODAY.isoformat()})\n")[1].split("\n\n")[0].splitlines()

    assert len(section) == 16
    assert section[0].startswith("- lunch: M00")
    assert section[14].startswith("- lunch: M14")
    assert section[-1] == "- … and 3 more"
    assert "- 2026-10-05: 1800 kcal, C 900 g, P 540 g, F 180 g (so far)" in text


def test_age_not_rendered_when_date_precedes_birth_year():
    text = render_user_context(_user(birth_year=2006), [], [], date(2000, 1, 1))

    assert "Age" not in text


def _water(day: date, ml: int) -> WaterLog:
    return WaterLog.create(1, ml, client_id=f"w-{day}-{ml}", logged_on=day)


def _act(name: str, day: date, kcal: int) -> ActivityLog:
    return ActivityLog.create(1, name, kcal, client_id=f"a-{name}-{day}", logged_on=day)


def _weight(day: date, kg: float) -> WeightLog:
    return WeightLog.create(1, kg, day, client_id=f"k-{day}")


def _render(goals=(), water=(), acts=(), weights=(), streak=None) -> str:
    return render_activity_context(list(goals), list(water), list(acts), list(weights), streak, TODAY)


def test_empty_activity_context_has_all_four_sections_with_empty_states():
    text = _render()

    assert "WATER\n- Today (2026-10-05): not logged yet, no goal" in text
    assert "ACTIVITY (kcal burned)\n- Today: not logged yet" in text
    assert "WEIGHT (kg)\n- no weigh-ins in the last 30 days" in text
    assert "STREAK\n- none yet" in text
    assert text.count("\n\n") == 3


def test_water_today_against_the_goal_in_force_and_last_days():
    goals = [_goal(date(2026, 9, 1), 2000), _goal(date(2026, 10, 20), 1500)]  # 2nd not in force yet
    water = [_water(TODAY, 750), _water(TODAY, 500), _water(date(2026, 10, 3), 1800), _water(date(2026, 9, 1), 999)]

    text = _render(goals, water)

    assert "- Today (2026-10-05): 1250 ml of 2000 ml goal" in text
    assert "2026-10-03: 1800 ml" in text
    assert "2026-10-04: not logged" in text
    assert "2026-10-05: 1250 ml (so far)" in text
    assert "2026-09-29: not logged" in text and "999" not in text


def test_water_without_a_goal_says_no_goal():
    assert "- Today (2026-10-05): 400 ml, no goal" in _render(water=[_water(TODAY, 400)])


def test_activity_lists_todays_items_and_daily_totals():
    acts = [_act("Chạy bộ", TODAY, 250), _act("Steps", TODAY, 70), _act("Yoga", date(2026, 10, 3), 90)]

    text = _render(acts=acts)

    assert "- Today: 320 kcal — Chạy bộ 250 kcal, Steps 70 kcal" in text
    assert "2026-10-03: 90 kcal" in text
    assert "2026-10-04: not logged" in text
    assert "2026-10-05: 320 kcal (so far)" in text


def test_activity_list_is_capped_and_names_are_truncated():
    acts = [_act(f"A{i:02d}", TODAY, 10) for i in range(13)]

    line = next(l for l in _render(acts=acts).splitlines() if l.startswith("- Today: "))

    assert "A09 10 kcal" in line and "A10" not in line
    assert line.endswith("… and 3 more")
    assert "x" * 61 not in _render(acts=[_act("x" * 100, TODAY, 5)])


def test_weight_latest_and_change_over_the_window():
    weights = [
        _weight(date(2026, 9, 5), 80.0),  # 30-day window starts 09-06
        _weight(date(2026, 9, 16), 70.0),
        _weight(date(2026, 10, 3), 69.0),
        _weight(date(2026, 10, 4), 68.4),
    ]

    text = _render(weights=weights)

    assert "- Latest: 68.4 on 2026-10-04" in text
    assert "- Change over the last 30 days: -1.6 kg (70.0 on 2026-09-16 → 68.4)" in text


def test_single_weigh_in_has_no_change_line():
    text = _render(weights=[_weight(date(2026, 10, 4), 68.4)])

    assert "- Latest: 68.4 on 2026-10-04" in text
    assert "Change" not in text


def test_weight_gain_is_signed():
    assert "+1.5 kg" in _render(weights=[_weight(date(2026, 9, 20), 60.0), _weight(TODAY, 61.5)])


def test_streak_current_and_longest():
    streak = Streak(id=Streak.create(1).id, user_id=1, current_streak=5, longest_streak=12, last_active_date=TODAY)

    assert "STREAK\n- Current: 5 days (longest 12)" in _render(streak=streak)


def test_broken_streak_shows_zero():
    streak = Streak(
        id=Streak.create(1).id, user_id=1, current_streak=5, longest_streak=12, last_active_date=date(2026, 10, 1)
    )

    assert "- Current: 0 days (longest 12)" in _render(streak=streak)


def test_zeroed_streak_row_is_none_yet():
    assert "STREAK\n- none yet" in _render(streak=Streak.create(1))
