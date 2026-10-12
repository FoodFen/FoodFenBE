"""ORM model for payments — one row per PayOS checkout attempt."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger, CheckConstraint, DateTime, Identity, Integer, Numeric, String, Text, UniqueConstraint, func,
)
from sqlalchemy.orm import Mapped, mapped_column

from src.domain.entities.payment import Payment
from src.domain.enums import PaymentProvider, PaymentStatus, PlanType
from src.infrastructure.db.base import Base
from src.infrastructure.db.mixins import UUIDPrimaryKey, UserOwned
from src.infrastructure.db.types import enum_column


class PaymentORM(UUIDPrimaryKey, UserOwned, Base):
    __tablename__ = "payments"
    __table_args__ = (
        UniqueConstraint("order_code", name="uq_payments_order_code"),
        # ad_days is set (> 0) iff this is an ad_package payment; the entity checks the same.
        CheckConstraint(
            "(plan_type = 'ad_package') = (ad_days IS NOT NULL) AND (ad_days IS NULL OR ad_days > 0)",
            name="ad_days",
        ),
    )

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
    ad_days: Mapped[int | None] = mapped_column(Integer, nullable=True)  # placement days snapshotted at checkout

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
            ad_days=self.ad_days,
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
            ad_days=payment.ad_days,
        )
        # Identity column: only set it when the entity already has one (an
        # update), never on insert — leave it unset so Postgres assigns it.
        if payment.order_code is not None:
            row.order_code = payment.order_code
        return row
