"""render_user_context: pure text rendering of the user's own data for the chat model."""

from __future__ import annotations

from datetime import UTC, date, datetime

from src.application.chat_context import WINDOW_DAYS, render_user_context
from src.domain.entities.daily_goal import DailyGoal
from src.domain.entities.food_entry import FoodEntry
from src.domain.entities.user import User
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
    assert window[-1] == "- 2026-10-05: 1150 kcal, C 100 g, P 60 g, F 20 g"
    assert "999" not in text


def test_day_without_entries_is_not_logged_not_zero():
    text = render_user_context(_user(), [], [_entry("A", TODAY, 450)], TODAY)

    assert "- 2026-10-04: not logged" in text
    assert "- 2026-10-04: 0 kcal" not in text
