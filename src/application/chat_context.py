"""Render the user's own data as grounding text for the chat model. Standard library only.

One section of the chat context assembled by ``SendChatMessageUseCase._build_context``.
Pure: the caller reads the repositories, so this needs no fakes to test.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta

from src.domain.entities.daily_goal import DailyGoal
from src.domain.entities.food_entry import FoodEntry
from src.domain.entities.user import User
from src.domain.enums import UnitSystem

WINDOW_DAYS = 7
MAX_MEALS_LISTED = 15
MAX_NAME_CHARS = 60


def render_user_context(
    user: User | None, goals: list[DailyGoal], entries: list[FoodEntry], today: date
) -> str:
    """``entries`` should cover ``today - (WINDOW_DAYS - 1) .. today``; anything outside is ignored."""
    return "\n\n".join(
        [_profile(user, today), _goal(goals, today), _meals_today(entries, today), _last_days(entries, today)]
    )


def _age(user: User, today: date) -> int | None:
    age = today.year - user.birth_year if user.birth_year else 0
    return age if age > 0 else None


def _profile(user: User | None, today: date) -> str:
    if user is None:
        return "PROFILE\n- not set"
    fields = [
        ("Age", _age(user, today)),
        ("Gender", user.gender),
        ("Height", user.height),
        ("Current weight", user.weight_current),
        ("Goal weight", user.weight_goal),
        ("Target weekly change (kg)", user.weekly_rate_kg),
        ("Activity level", user.activity_level),
        ("Diet type", user.diet_type),
    ]
    lines = [f"- {label}: {value:g}" if isinstance(value, float) else f"- {label}: {value}"
             for label, value in fields if value is not None]
    if not lines:
        return "PROFILE\n- not set"
    units = "metric (cm, kg)" if user.unit_system == UnitSystem.METRIC else "imperial"
    return "\n".join(["PROFILE", *lines, f"- Units: {units}"])


def _goal(goals: list[DailyGoal], today: date) -> str:
    in_force = [g for g in goals if g.effective_date <= today]
    if not in_force:
        return "DAILY GOAL\n- not set"
    g = max(in_force, key=lambda g: g.effective_date)
    return (
        f"DAILY GOAL\n- {g.target_kcal} kcal, carbs {g.target_carbs_g:.0f} g, "
        f"protein {g.target_protein_g:.0f} g, fat {g.target_fat_g:.0f} g"
    )


def _macros(kcal: int, carbs: float, protein: float, fat: float) -> str:
    return f"{kcal} kcal, C {carbs:.0f} g, P {protein:.0f} g, F {fat:.0f} g"


def _meals_today(entries: list[FoodEntry], today: date) -> str:
    header = f"MEALS TODAY ({today.isoformat()})"
    meals = sorted((e for e in entries if e.logged_on == today), key=lambda e: e.logged_at)
    if not meals:
        return f"{header}\n- nothing logged yet"
    lines = [
        f"- {e.meal_type}: {e.name[:MAX_NAME_CHARS]} — {_macros(e.total_kcal, e.carbs_g, e.protein_g, e.fat_g)}"
        for e in meals[:MAX_MEALS_LISTED]
    ]
    if len(meals) > MAX_MEALS_LISTED:
        lines.append(f"- … and {len(meals) - MAX_MEALS_LISTED} more")
    return "\n".join([header, *lines])


def _last_days(entries: list[FoodEntry], today: date) -> str:
    by_day: dict[date, list[FoodEntry]] = defaultdict(list)
    for e in entries:
        by_day[e.logged_on].append(e)
    lines = []
    for offset in range(WINDOW_DAYS - 1, -1, -1):
        day = today - timedelta(days=offset)
        day_entries = by_day.get(day)
        if not day_entries:
            lines.append(f"- {day.isoformat()}: not logged")
            continue
        totals = _macros(
            sum(e.total_kcal for e in day_entries),
            sum(e.carbs_g for e in day_entries),
            sum(e.protein_g for e in day_entries),
            sum(e.fat_g for e in day_entries),
        )
        partial = " (so far)" if day == today else ""
        lines.append(f"- {day.isoformat()}: {totals}{partial}")
    return "\n".join([f"LAST {WINDOW_DAYS} DAYS (daily totals; 'not logged' means unknown, not zero)", *lines])
