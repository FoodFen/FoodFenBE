"""add payments table

Revision ID: 0009
Revises: 0008
Create Date: 2026-09-24
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0009"
down_revision: str | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_PLAN_TYPE = ("monthly", "annual")
_PAYMENT_STATUS = ("pending", "paid", "cancelled", "expired", "failed")


def upgrade() -> None:
    op.create_table(
        "payments",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("order_code", sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column("plan_type", sa.String(length=7), nullable=False),
        sa.Column("amount", sa.Numeric(12, 0), nullable=False),
        sa.Column("status", sa.String(length=9), nullable=False),
        sa.Column("payment_link_id", sa.String(length=64), nullable=True),
        sa.Column("checkout_url", sa.String(length=512), nullable=True),
        sa.Column("qr_code", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_payments"),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_payments_user_id_users", ondelete="CASCADE"
        ),
        sa.UniqueConstraint("order_code", name="uq_payments_order_code"),
        sa.CheckConstraint(f"plan_type IN {_PLAN_TYPE}", name="plan_type"),
        sa.CheckConstraint(f"status IN {_PAYMENT_STATUS}", name="payment_status"),
    )


def downgrade() -> None:
    op.drop_table("payments")
