"""FoodEntry entity — the aggregate root for one logged meal, owning its Ingredients."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import UUID, uuid4

from src.domain.entities.ingredient import Ingredient
from src.domain.enums import AiFeedback, InputMethod
from src.domain.validation import require_non_empty, require_non_negative


@dataclass
class FoodEntry:
    """One logged meal.

    ``fiber_g`` is a Premium-only field: it stays ``None`` for free-tier users
    rather than being stored as zero, so "not tracked" and "zero fibre" stay
    distinguishable.
    """

    id: UUID
    user_id: int
    name: str
    input_method: InputMethod
    total_kcal: int
    carbs_g: float
    protein_g: float
    fat_g: float
    image_url: str | None = None
    fiber_g: float | None = None
    ai_feedback: AiFeedback | None = None
    logged_at: datetime = field(default_factory=lambda: datetime.now(UTC))
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
        image_url: str | None = None,
        fiber_g: float | None = None,
        ingredients: list[Ingredient] | None = None,
    ) -> FoodEntry:
        return cls(
            id=uuid4(),
            user_id=user_id,
            name=name,
            input_method=input_method,
            total_kcal=total_kcal,
            carbs_g=carbs_g,
            protein_g=protein_g,
            fat_g=fat_g,
            image_url=image_url,
            fiber_g=fiber_g,
            logged_at=datetime.now(UTC),
            ingredients=ingredients or [],
        )
