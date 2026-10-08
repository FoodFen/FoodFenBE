"""Payment entity — one row per checkout attempt."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from src.domain.enums import PaymentProvider, PaymentStatus, PlanType
from src.domain.exceptions import InvalidPaymentStateException
from src.domain.validation import require_positive


@dataclass
class Payment:
    """A single checkout attempt for one plan purchase.

    ``order_code`` is ``None`` until the row is inserted: PayOS requires a
    numeric order id, and the database's identity column is the only way to
    hand one out with no collision risk — the same reason ``User.id`` is
    ``None`` until insert.
    """

    id: UUID
    user_id: int
    plan_type: PlanType
    amount: Decimal
    status: PaymentStatus
    provider: PaymentProvider = PaymentProvider.PAYOS
    order_code: int | None = None
    payment_link_id: str | None = None
    checkout_url: str | None = None
    qr_code: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    paid_at: datetime | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.amount, Decimal):
            self.amount = Decimal(str(self.amount))
        require_positive(self.amount, "amount")

    @classmethod
    def create(
        cls,
        user_id: int,
        plan_type: PlanType,
        amount: Decimal | int | str,
        provider: PaymentProvider = PaymentProvider.PAYOS,
    ) -> Payment:
        return cls(
            id=uuid4(),
            user_id=user_id,
            plan_type=plan_type,
            amount=Decimal(str(amount)),
            status=PaymentStatus.PENDING,
            provider=provider,
        )

    def attach_checkout(self, payment_link_id: str, checkout_url: str, qr_code: str | None) -> None:
        if self.status is not PaymentStatus.PENDING:
            raise InvalidPaymentStateException(
                f"cannot attach checkout info to a payment in status {self.status}"
            )
        self.payment_link_id = payment_link_id
        self.checkout_url = checkout_url
        self.qr_code = qr_code

    def mark_paid(self) -> None:
        """Idempotent: a webhook retry after we've already recorded PAID is a no-op.

        Money the provider confirmed always counts, even after a local cancel (some
        providers, e.g. MoMo, have no cancel API, so a cancelled order can still be paid).
        """
        if self.status not in (PaymentStatus.PENDING, PaymentStatus.CANCELLED):
            return
        self.status = PaymentStatus.PAID
        self.paid_at = datetime.now(UTC)

    def mark_failed(self) -> None:
        if self.status is not PaymentStatus.PENDING:
            return
        self.status = PaymentStatus.FAILED

    def mark_cancelled(self) -> None:
        if self.status is not PaymentStatus.PENDING:
            raise InvalidPaymentStateException(
                f"cannot cancel a payment in status {self.status}"
            )
        self.status = PaymentStatus.CANCELLED
