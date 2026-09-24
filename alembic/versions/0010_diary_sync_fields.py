"""add meal_type/logged_on diary sync fields

Revision ID: 0010
Revises: 0009
Create Date: 2026-09-25
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0010"
down_revision: str | None = "0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_MEAL_TYPE = ("breakfast", "lunch", "dinner", "snack")


def upgrade() -> None:
    op.add_column("food_entries", sa.Column("meal_type", sa.String(length=9), nullable=False))
    op.add_column("food_entries", sa.Column("logged_on", sa.Date(), nullable=False))
    op.create_check_constraint("meal_type", "food_entries", f"meal_type IN {_MEAL_TYPE}")
    op.create_index("ix_food_entries_user_logged_on", "food_entries", ["user_id", "logged_on"])

    op.add_column("activity_logs", sa.Column("logged_on", sa.Date(), nullable=False))
    op.create_index("ix_activity_logs_user_logged_on", "activity_logs", ["user_id", "logged_on"])

    op.add_column("water_logs", sa.Column("logged_on", sa.Date(), nullable=False))
    op.create_index("ix_water_logs_user_logged_on", "water_logs", ["user_id", "logged_on"])


def downgrade() -> None:
    op.drop_index("ix_water_logs_user_logged_on", table_name="water_logs")
    op.drop_column("water_logs", "logged_on")

    op.drop_index("ix_activity_logs_user_logged_on", table_name="activity_logs")
    op.drop_column("activity_logs", "logged_on")

    op.drop_index("ix_food_entries_user_logged_on", table_name="food_entries")
    op.drop_constraint("meal_type", "food_entries", type_="check")
    op.drop_column("food_entries", "logged_on")
    op.drop_column("food_entries", "meal_type")
