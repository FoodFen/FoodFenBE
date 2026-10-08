"""ORM model for payments — one row per PayOS checkout attempt."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import BigInteger, DateTime, Identity, Numeric, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from src.domain.entities.payment import Payment
from src.domain.enums import PaymentProvider, PaymentStatus, PlanType
from src.infrastructure.db.base import Base
from src.infrastructure.db.mixins import UUIDPrimaryKey, UserOwned
from src.infrastructure.db.types import enum_column


class PaymentORM(UUIDPrimaryKey, UserOwned, Base):
    __tablename__ = "payments"
    __table_args__ = (UniqueConstraint("order_code", name="uq_payments_order_code"),)

    # DB-native identity column: PayOS needs a numeric order id, and this is
    # the only way to hand one out with no collision risk (not the PK — every
    # other table here keeps a UUID PK).
    order_code: Mapped[int] = mapped_column(BigInteger, Identity(), nullable=False)
    plan_type: Mapped[PlanType] = mapped_column(enum_column(PlanType, "plan_type"), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 0), nullable=False)  # VND has no minor unit
    status: Mapped[PaymentStatus] = mapped_column(
        enum_column(PaymentStatus, "payment_status"), nullable=False
    )
    provider: Mapped[PaymentProvider] = mapped_column(
        enum_column(PaymentProvider, "payment_provider"),
        nullable=False,
        server_default=PaymentProvider.PAYOS.value,
    )
    payment_link_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    checkout_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    qr_code: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    def to_domain(self) -> Payment:
        return Payment(
            id=self.id,
            user_id=self.user_id,
            order_code=self.order_code,
            plan_type=self.plan_type,
            amount=self.amount,
            status=self.status,
            provider=self.provider,
            payment_link_id=self.payment_link_id,
            checkout_url=self.checkout_url,
            qr_code=self.qr_code,
            created_at=self.created_at,
            paid_at=self.paid_at,
        )

    @staticmethod
    def from_domain(payment: Payment) -> PaymentORM:
        row = PaymentORM(
            id=payment.id,
            user_id=payment.user_id,
            plan_type=payment.plan_type,
            amount=payment.amount,
            status=payment.status,
            provider=payment.provider,
            payment_link_id=payment.payment_link_id,
            checkout_url=payment.checkout_url,
            qr_code=payment.qr_code,
            created_at=payment.created_at,
            paid_at=payment.paid_at,
        )
        # Identity column: only set it when the entity already has one (an
        # update), never on insert — leave it unset so Postgres assigns it.
        if payment.order_code is not None:
            row.order_code = payment.order_code
        return row
