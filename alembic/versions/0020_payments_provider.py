"""payments.provider: which gateway a checkout went through

Revision ID: 0020
Revises: 0019
Create Date: 2026-10-05
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0020"
down_revision: str | None = "0019"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "payments",
        sa.Column("provider", sa.String(length=5), server_default="payos", nullable=False),
    )
    op.create_check_constraint("payment_provider", "payments", "provider IN ('payos', 'momo')")


def downgrade() -> None:
    op.drop_constraint("payment_provider", "payments", type_="check")
    op.drop_column("payments", "provider")
