"""FoodEntry entity — the aggregate root for one logged meal, owning its Ingredients."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from uuid import UUID, uuid4

from src.domain.entities.ingredient import Ingredient
from src.domain.enums import AiFeedback, InputMethod, MealType
from src.domain.validation import require_non_empty, require_non_negative


@dataclass
class FoodEntry:
    """One logged meal.

    ``fiber_g`` is a Premium-only field: it stays ``None`` for free-tier users
    rather than being stored as zero, so "not tracked" and "zero fibre" stay
    distinguishable. ``logged_on`` is the user's local calendar day, distinct
    from ``logged_at`` (a UTC instant) — the client supplies it, because only
    the device knows the user's actual local day at write time; deriving it
    from ``logged_at`` server-side would get the wrong day near midnight.
    """

    id: UUID
    user_id: int
    name: str
    input_method: InputMethod
    total_kcal: int
    carbs_g: float
    protein_g: float
    fat_g: float
    meal_type: MealType
    client_id: str
    image_url: str | None = None
    fiber_g: float | None = None
    ai_feedback: AiFeedback | None = None
    logged_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    logged_on: date = field(default_factory=lambda: datetime.now(UTC).date())
    ingredients: list[Ingredient] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.name = require_non_empty(self.name, "name")
        for value, label in (
            (self.total_kcal, "total_kcal"),
            (self.carbs_g, "carbs_g"),
            (self.protein_g, "protein_g"),
            (self.fat_g, "fat_g"),
        ):
            require_non_negative(value, label)
        if self.fiber_g is not None:
            require_non_negative(self.fiber_g, "fiber_g")
        self.client_id = require_non_empty(self.client_id, "client_id")

    @classmethod
    def create(
        cls,
        user_id: int,
        name: str,
        input_method: InputMethod,
        total_kcal: int,
        carbs_g: float,
        protein_g: float,
        fat_g: float,
        meal_type: MealType,
        *,
        client_id: str,
        image_url: str | None = None,
        fiber_g: float | None = None,
        ingredients: list[Ingredient] | None = None,
        logged_at: datetime | None = None,
        logged_on: date | None = None,
    ) -> FoodEntry:
        logged_at = logged_at or datetime.now(UTC)
        return cls(
            id=uuid4(),
            user_id=user_id,
            name=name,
            input_method=input_method,
            total_kcal=total_kcal,
            carbs_g=carbs_g,
            protein_g=protein_g,
            fat_g=fat_g,
            meal_type=meal_type,
            client_id=client_id,
            image_url=image_url,
            fiber_g=fiber_g,
            logged_at=logged_at,
            logged_on=logged_on or logged_at.date(),
            ingredients=ingredients or [],
        )
