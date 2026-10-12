"""AdPackage entity: N days of paid placement for a whole restaurant. See docs/marketplace.md."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from src.domain.exceptions import InvalidAdPackageException
from src.domain.validation import require_positive


@dataclass
class AdPackage:
    id: UUID
    days: int
    price_vnd: Decimal
    active: bool = True
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        if not isinstance(self.price_vnd, Decimal):
            self.price_vnd = Decimal(str(self.price_vnd))
        require_positive(self.days, "days", InvalidAdPackageException)
        require_positive(self.price_vnd, "price_vnd", InvalidAdPackageException)

    @classmethod
    def create(cls, days: int, price_vnd: Decimal | int | str, active: bool = True) -> AdPackage:
        return cls(id=uuid4(), days=days, price_vnd=price_vnd, active=active)

    def update(self, days: int | None = None, price_vnd: Decimal | int | str | None = None, active: bool | None = None) -> None:
        """Only the given fields change; invalid values raise before anything does."""
        changed = replace(
            self,
            days=self.days if days is None else days,
            price_vnd=self.price_vnd if price_vnd is None else price_vnd,
            active=self.active if active is None else active,
        )  # replace() re-runs __post_init__
        self.days, self.price_vnd, self.active = changed.days, changed.price_vnd, changed.active
