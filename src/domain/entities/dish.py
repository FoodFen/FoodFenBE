"""Dish entity: a menu item with per-serving nutrition, moderated on its own."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from src.domain.enums import ModerationStatus, ReviewDecision
from src.domain.exceptions import InvalidRestaurantAttributeException
from src.domain.moderation import checked_reason
from src.domain.validation import require_non_empty, require_non_negative, require_positive


def _now() -> datetime:
    return datetime.now(UTC)


@dataclass
class Dish:
    id: UUID
    restaurant_id: UUID
    name: str
    price: Decimal  # VND
    serving_g: int
    # Per serving. Names/types match food_entries so a dish can be logged as-is.
    kcal: int
    protein_g: float
    carbs_g: float
    fat_g: float
    fiber_g: float | None = None
    description: str | None = None
    image_url: str | None = None
    status: ModerationStatus = ModerationStatus.PENDING
    rejection_reason: str | None = None
    created_at: datetime = field(default_factory=_now)
    updated_at: datetime = field(default_factory=_now)
    reviewed_at: datetime | None = None

    def __post_init__(self) -> None:
        exc = InvalidRestaurantAttributeException
        self.name = require_non_empty(self.name, "name", exc)
        self.description = (self.description or "").strip() or None
        require_non_negative(self.price, "price", exc)
        require_positive(self.serving_g, "serving_g", exc)
        for value, label in (
            (self.kcal, "kcal"), (self.protein_g, "protein_g"),
            (self.carbs_g, "carbs_g"), (self.fat_g, "fat_g"),
        ):
            require_non_negative(value, label, exc)
        if self.fiber_g is not None:
            require_non_negative(self.fiber_g, "fiber_g", exc)
        self.rejection_reason = checked_reason(self.status, self.rejection_reason)

    @classmethod
    def create(
        cls,
        *,
        restaurant_id: UUID,
        name: str,
        price: Decimal,
        serving_g: int,
        kcal: int,
        protein_g: float,
        carbs_g: float,
        fat_g: float,
        fiber_g: float | None = None,
        description: str | None = None,
        image_url: str | None = None,
    ) -> Dish:
        now = _now()
        return cls(
            id=uuid4(), restaurant_id=restaurant_id, name=name, price=price, serving_g=serving_g,
            kcal=kcal, protein_g=protein_g, carbs_g=carbs_g, fat_g=fat_g, fiber_g=fiber_g,
            description=description, image_url=image_url, created_at=now, updated_at=now,
        )

    def review(self, decision: ReviewDecision, reason: str | None, now: datetime) -> None:
        status = ModerationStatus(decision.value)
        self.rejection_reason = checked_reason(status, reason)
        self.status = status
        self.reviewed_at = now

    def mark_edited(self, now: datetime) -> None:
        """Any edit sends the dish back to review; it is hidden until re-approved."""
        self.updated_at = now
        self.status = ModerationStatus.PENDING
        self.rejection_reason = None
