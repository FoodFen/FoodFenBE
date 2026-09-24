"""Ingredient entity — a component of a FoodEntry, never standalone."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID, uuid4

from src.domain.validation import require_non_empty, require_non_negative, require_positive


@dataclass
class Ingredient:
    id: UUID
    food_entry_id: UUID
    name: str
    quantity_g: float
    kcal: int
    carbs_g: float
    protein_g: float
    fat_g: float
    # Premium-only, mirroring FoodEntry.fiber_g: None means "not tracked", not zero.
    fiber_g: float | None = None

    def __post_init__(self) -> None:
        self.name = require_non_empty(self.name, "name")
        require_positive(self.quantity_g, "quantity_g")
        for value, label in (
            (self.kcal, "kcal"),
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
        food_entry_id: UUID,
        name: str,
        quantity_g: float,
        kcal: int,
        carbs_g: float,
        protein_g: float,
        fat_g: float,
        fiber_g: float | None = None,
    ) -> Ingredient:
        return cls(
            id=uuid4(),
            food_entry_id=food_entry_id,
            name=name,
            quantity_g=quantity_g,
            kcal=kcal,
            carbs_g=carbs_g,
            protein_g=protein_g,
            fat_g=fat_g,
            fiber_g=fiber_g,
        )
