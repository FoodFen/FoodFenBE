"""add client_id idempotency + soft delete for diary sync push

Revision ID: 0011
Revises: 0010
Create Date: 2026-09-24
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0011"
down_revision: str | None = "0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_CLIENT_ID_TABLES = ("food_entries", "daily_goals", "activity_logs", "weight_logs", "water_logs")
_SOFT_DELETE_TABLES = ("food_entries", "water_logs")


def upgrade() -> None:
    # client_id is NOT NULL with no default. Existing rows (local dev/demo
    # data — no real users yet, confirmed this session) have no
    # client-generated id to backfill honestly, so this clears them rather
    # than invent a synthetic value. CASCADE also clears `ingredients`
    # (FK to food_entries).
    for table in _CLIENT_ID_TABLES:
        op.execute(f"TRUNCATE TABLE {table} CASCADE")

    for table in _CLIENT_ID_TABLES:
        op.add_column(table, sa.Column("client_id", sa.String(length=64), nullable=False))
        op.create_unique_constraint(f"uq_{table}_client_id", table, ["user_id", "client_id"])

    for table in _SOFT_DELETE_TABLES:
        op.add_column(table, sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    for table in _SOFT_DELETE_TABLES:
        op.drop_column(table, "deleted_at")

    for table in _CLIENT_ID_TABLES:
        op.drop_constraint(f"uq_{table}_client_id", table, type_="unique")
        op.drop_column(table, "client_id")
