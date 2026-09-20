"""users.id UUID -> integer identity PK; add calorie_left_mode/weekly_rate_kg;
users.name becomes nullable

The front-end API contract types ``User.id`` as a number, not a UUID string.
Changing a referenced PK's type has no meaningful "preserve the data" path
(old UUID values have no correspondence to new integers), so this migration
truncates ``users`` (cascading to every table that references it) rather than
attempt an in-place value conversion. Acceptable pre-launch; there is no
production data yet.

Revision ID: 0005
Revises: 0004
Create Date: 2026-09-19
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Every table with a `user_id` FK into `users.id` (the UserOwned mixin).
_OWNED_TABLES = (
    "activity_logs",
    "coin_transactions",
    "daily_goals",
    "food_entries",
    "quests",
    "refresh_tokens",
    "streaks",
    "subscriptions",
    "water_logs",
    "weight_logs",
)


def _recreate_user_id_indexes() -> None:
    """Dropping `user_id` (either direction of this migration) auto-drops every
    index/unique constraint that includes it — Postgres cascades that as part
    of DROP COLUMN. Put them back."""
    op.create_index("ix_activity_logs_user_logged_at", "activity_logs", ["user_id", "logged_at"])
    op.create_index(
        "ix_coin_transactions_user_created_at", "coin_transactions", ["user_id", "created_at"]
    )
    op.create_unique_constraint(
        "uq_daily_goals_user_date", "daily_goals", ["user_id", "effective_date"]
    )
    op.create_index("ix_food_entries_user_logged_at", "food_entries", ["user_id", "logged_at"])
    op.create_unique_constraint(
        "uq_quests_user_type_date", "quests", ["user_id", "quest_type", "quest_date"]
    )
    op.create_unique_constraint("uq_streaks_user", "streaks", ["user_id"])
    op.create_unique_constraint("uq_subscriptions_user", "subscriptions", ["user_id"])
    op.create_index("ix_water_logs_user_logged_at", "water_logs", ["user_id", "logged_at"])
    op.create_index("ix_weight_logs_user_recorded_at", "weight_logs", ["user_id", "recorded_at"])


def upgrade() -> None:
    # Wipes users and, via ON DELETE CASCADE / TRUNCATE ... CASCADE, every row
    # that depends on it (transitively: food_entries -> ingredients too).
    op.execute("TRUNCATE TABLE users CASCADE")

    for table in _OWNED_TABLES:
        op.drop_constraint(f"fk_{table}_user_id_users", table, type_="foreignkey")
        op.drop_column(table, "user_id")

    op.drop_constraint("pk_users", "users", type_="primary")
    op.drop_column("users", "id")
    op.add_column(
        "users",
        sa.Column("id", sa.Integer(), sa.Identity(always=False), nullable=False),
    )
    op.create_primary_key("pk_users", "users", ["id"])

    for table in _OWNED_TABLES:
        op.add_column(table, sa.Column("user_id", sa.Integer(), nullable=False))
        op.create_foreign_key(
            f"fk_{table}_user_id_users",
            table,
            "users",
            ["user_id"],
            ["id"],
            ondelete="CASCADE",
        )

    op.alter_column("users", "name", existing_type=sa.String(length=255), nullable=True)
    op.add_column(
        "users", sa.Column("calorie_left_mode", sa.String(length=12), nullable=True)
    )
    op.create_check_constraint(
        "calorie_left_mode", "users", "calorie_left_mode IN ('smart', 'all_calories')"
    )
    op.add_column("users", sa.Column("weekly_rate_kg", sa.Float(), nullable=True))

    _recreate_user_id_indexes()


def downgrade() -> None:
    op.drop_column("users", "weekly_rate_kg")
    op.drop_constraint("calorie_left_mode", "users", type_="check")
    op.drop_column("users", "calorie_left_mode")
    op.alter_column("users", "name", existing_type=sa.String(length=255), nullable=False)

    op.execute("TRUNCATE TABLE users CASCADE")

    for table in _OWNED_TABLES:
        op.drop_constraint(f"fk_{table}_user_id_users", table, type_="foreignkey")
        op.drop_column(table, "user_id")

    op.drop_constraint("pk_users", "users", type_="primary")
    op.drop_column("users", "id")
    op.add_column(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
    )
    op.create_primary_key("pk_users", "users", ["id"])

    for table in _OWNED_TABLES:
        op.add_column(
            table,
            sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        )
        op.create_foreign_key(
            f"fk_{table}_user_id_users",
            table,
            "users",
            ["user_id"],
            ["id"],
            ondelete="CASCADE",
        )

    _recreate_user_id_indexes()
