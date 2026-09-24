"""DailyGoal entity — the user's targets, versioned by effective_date."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime
from uuid import UUID, uuid4

from src.domain.validation import require_non_empty, require_positive


@dataclass
class DailyGoal:
    """Targets that apply from ``effective_date`` until the next row supersedes it.

    Kept as history rather than mutated in place so past days stay comparable
    against the goal that was actually in force on that day.
    """

    id: UUID
    user_id: int
    target_kcal: int
    target_carbs_g: float
    target_protein_g: float
    target_fat_g: float
    target_water_ml: int
    effective_date: date
    client_id: str

    def __post_init__(self) -> None:
        for value, label in (
            (self.target_kcal, "target_kcal"),
            (self.target_carbs_g, "target_carbs_g"),
            (self.target_protein_g, "target_protein_g"),
            (self.target_fat_g, "target_fat_g"),
            (self.target_water_ml, "target_water_ml"),
        ):
            require_positive(value, label)
        self.client_id = require_non_empty(self.client_id, "client_id")

    @classmethod
    def create(
        cls,
        user_id: int,
        target_kcal: int,
        target_carbs_g: float,
        target_protein_g: float,
        target_fat_g: float,
        target_water_ml: int,
        effective_date: date | None = None,
        *,
        client_id: str,
    ) -> DailyGoal:
        return cls(
            id=uuid4(),
            user_id=user_id,
            target_kcal=target_kcal,
            target_carbs_g=target_carbs_g,
            target_protein_g=target_protein_g,
            target_fat_g=target_fat_g,
            target_water_ml=target_water_ml,
            effective_date=effective_date or datetime.now(UTC).date(),
            client_id=client_id,
        )
