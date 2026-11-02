"""coin_transactions.client_id: idempotency key for redeem

Revision ID: 0027
Revises: 0026
Create Date: 2026-10-20
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0027"
down_revision: str | None = "0026"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("coin_transactions", sa.Column("client_id", sa.String(64), nullable=True))
    op.create_unique_constraint(
        "uq_coin_transactions_client_id", "coin_transactions", ["user_id", "client_id"]
    )


def downgrade() -> None:
    op.drop_constraint("uq_coin_transactions_client_id", "coin_transactions", type_="unique")
    op.drop_column("coin_transactions", "client_id")
