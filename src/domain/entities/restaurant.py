"""Restaurant entity: one per owner, moderated before it is public. See docs/marketplace.md."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import UUID, uuid4

from src.domain.enums import ModerationStatus, ReviewDecision
from src.domain.exceptions import InvalidRestaurantAttributeException
from src.domain.moderation import checked_reason
from src.domain.validation import require_non_empty


def _now() -> datetime:
    return datetime.now(UTC)


@dataclass
class Restaurant:
    id: UUID
    user_id: int  # the owner
    name: str
    address: str
    phone: str
    opening_hours: str  # free text, e.g. "7:00-21:00"
    latitude: float
    longitude: float
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
        self.address = require_non_empty(self.address, "address", exc)
        self.phone = require_non_empty(self.phone, "phone", exc)
        self.opening_hours = require_non_empty(self.opening_hours, "opening_hours", exc)
        self.description = (self.description or "").strip() or None
        if not -90 <= self.latitude <= 90:
            raise exc(f"latitude must be between -90 and 90, got {self.latitude!r}")
        if not -180 <= self.longitude <= 180:
            raise exc(f"longitude must be between -180 and 180, got {self.longitude!r}")
        self.rejection_reason = checked_reason(self.status, self.rejection_reason)

    @classmethod
    def create(
        cls,
        *,
        user_id: int,
        name: str,
        address: str,
        phone: str,
        opening_hours: str,
        latitude: float,
        longitude: float,
        description: str | None = None,
        image_url: str | None = None,
    ) -> Restaurant:
        now = _now()
        return cls(
            id=uuid4(), user_id=user_id, name=name, address=address, phone=phone,
            opening_hours=opening_hours, latitude=latitude, longitude=longitude,
            description=description, image_url=image_url, created_at=now, updated_at=now,
        )

    def review(self, decision: ReviewDecision, reason: str | None, now: datetime) -> None:
        """Approve, reject, or take down (reject an approved one). Idempotent."""
        status = ModerationStatus(decision.value)
        self.rejection_reason = checked_reason(status, reason)  # raises before any change
        self.status = status
        self.reviewed_at = now

    def mark_edited(self, now: datetime) -> None:
        """Profile edits go live without re-review; editing a rejected restaurant resubmits it."""
        self.updated_at = now
        if self.status == ModerationStatus.REJECTED:
            self.status = ModerationStatus.PENDING
            self.rejection_reason = None
