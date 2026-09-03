"""extend users with profile fields and add the CalSnap ERD tables

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-03
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UUID = postgresql.UUID(as_uuid=True)

# Enum value sets, kept literal here on purpose: a migration must describe the
# schema as it was at this revision, not follow later edits to src.domain.enums.
GENDER = ("male", "female", "other")
UNIT_SYSTEM = ("metric", "imperial")
ACTIVITY_LEVEL = ("sedentary", "light", "moderate", "active", "very_active")
DIET_TYPE = ("balanced", "keto", "low_carb", "high_protein", "vegetarian", "vegan")
CALORIE_CALC_MODE = ("auto", "manual")
SUBSCRIPTION_TIER = ("free", "premium")
INPUT_METHOD = ("voice", "image", "type", "manual")
AI_FEEDBACK = ("up", "down")
ACTIVITY_SOURCE = ("manual", "apple_health", "google_fit")
PLAN_TYPE = ("monthly", "annual")
SUBSCRIPTION_STATUS = ("active", "cancelled", "expired")
QUEST_TYPE = ("log_food", "log_water", "log_weight", "log_activity")
COIN_REASON = ("quest_reward", "streak_bonus", "purchase", "adjustment")


def _enum(values: tuple[str, ...]) -> sa.String:
    """VARCHAR wide enough for the longest member; the CHECK does the constraining."""
    return sa.String(length=max(len(v) for v in values))


def _in_check(column: str, values: tuple[str, ...]) -> str:
    rendered = ", ".join(f"'{v}'" for v in values)
    return f"{column} IN ({rendered})"


def upgrade() -> None:
    # --- users: onboarding profile + auth ------------------------------------
    for column, values in (
        ("gender", GENDER),
        ("activity_level", ACTIVITY_LEVEL),
        ("diet_type", DIET_TYPE),
    ):
        op.add_column("users", sa.Column(column, _enum(values), nullable=True))

    op.add_column("users", sa.Column("password_hash", sa.String(length=255), nullable=True))
    op.add_column("users", sa.Column("birth_year", sa.Integer(), nullable=True))
    op.add_column("users", sa.Column("height", sa.Float(), nullable=True))
    op.add_column("users", sa.Column("weight_current", sa.Float(), nullable=True))
    op.add_column("users", sa.Column("weight_goal", sa.Float(), nullable=True))
    op.add_column(
        "users",
        sa.Column(
            "unit_system", _enum(UNIT_SYSTEM), nullable=False, server_default="metric"
        ),
    )
    op.add_column(
        "users",
        sa.Column(
            "calorie_calc_mode",
            _enum(CALORIE_CALC_MODE),
            nullable=False,
            server_default="auto",
        ),
    )
    op.add_column(
        "users",
        sa.Column(
            "subscription_tier",
            _enum(SUBSCRIPTION_TIER),
            nullable=False,
            server_default="free",
        ),
    )

    for column, values in (
        ("gender", GENDER),
        ("unit_system", UNIT_SYSTEM),
        ("activity_level", ACTIVITY_LEVEL),
        ("diet_type", DIET_TYPE),
        ("calorie_calc_mode", CALORIE_CALC_MODE),
        ("subscription_tier", SUBSCRIPTION_TIER),
    ):
        op.create_check_constraint(column, "users", _in_check(column, values))

    # --- daily_goals ---------------------------------------------------------
    op.create_table(
        "daily_goals",
        sa.Column("id", UUID, nullable=False),
        sa.Column("user_id", UUID, nullable=False),
        sa.Column("target_kcal", sa.Integer(), nullable=False),
        sa.Column("target_carbs_g", sa.Float(), nullable=False),
        sa.Column("target_protein_g", sa.Float(), nullable=False),
        sa.Column("target_fat_g", sa.Float(), nullable=False),
        sa.Column("target_water_ml", sa.Integer(), nullable=False),
        sa.Column("effective_date", sa.Date(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_daily_goals"),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_daily_goals_user_id_users", ondelete="CASCADE"
        ),
        sa.UniqueConstraint("user_id", "effective_date", name="uq_daily_goals_user_date"),
    )

    # --- food_entries + ingredients -----------------------------------------
    op.create_table(
        "food_entries",
        sa.Column("id", UUID, nullable=False),
        sa.Column("user_id", UUID, nullable=False),
        sa.Column("input_method", _enum(INPUT_METHOD), nullable=False),
        sa.Column("image_url", sa.String(length=2048), nullable=True),
        sa.Column("total_kcal", sa.Integer(), nullable=False),
        sa.Column("carbs_g", sa.Float(), nullable=False),
        sa.Column("protein_g", sa.Float(), nullable=False),
        sa.Column("fat_g", sa.Float(), nullable=False),
        # Premium-only: NULL means "not tracked", distinct from 0.0 g.
        sa.Column("fiber_g", sa.Float(), nullable=True),
        sa.Column("ai_feedback", _enum(AI_FEEDBACK), nullable=True),
        sa.Column("logged_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_food_entries"),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_food_entries_user_id_users", ondelete="CASCADE"
        ),
        sa.CheckConstraint(
            _in_check("input_method", INPUT_METHOD), name="input_method"
        ),
        sa.CheckConstraint(
            _in_check("ai_feedback", AI_FEEDBACK), name="ai_feedback"
        ),
    )
    op.create_index("ix_food_entries_user_logged_at", "food_entries", ["user_id", "logged_at"])

    op.create_table(
        "ingredients",
        sa.Column("id", UUID, nullable=False),
        sa.Column("food_entry_id", UUID, nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("quantity_g", sa.Float(), nullable=False),
        sa.Column("kcal", sa.Integer(), nullable=False),
        sa.Column("carbs_g", sa.Float(), nullable=False),
        sa.Column("protein_g", sa.Float(), nullable=False),
        sa.Column("fat_g", sa.Float(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_ingredients"),
        sa.ForeignKeyConstraint(
            ["food_entry_id"],
            ["food_entries.id"],
            name="fk_ingredients_food_entry_id_food_entries",
            ondelete="CASCADE",
        ),
    )
    op.create_index("ix_ingredients_food_entry_id", "ingredients", ["food_entry_id"])

    # --- activity_logs -------------------------------------------------------
    op.create_table(
        "activity_logs",
        sa.Column("id", UUID, nullable=False),
        sa.Column("user_id", UUID, nullable=False),
        sa.Column("activity_type", sa.String(length=120), nullable=False),
        sa.Column("calories_burned", sa.Integer(), nullable=False),
        sa.Column(
            "source", _enum(ACTIVITY_SOURCE), nullable=False, server_default="manual"
        ),
        sa.Column("logged_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_activity_logs"),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_activity_logs_user_id_users", ondelete="CASCADE"
        ),
        sa.CheckConstraint(
            _in_check("source", ACTIVITY_SOURCE), name="activity_source"
        ),
    )
    op.create_index("ix_activity_logs_user_logged_at", "activity_logs", ["user_id", "logged_at"])

    # --- weight_logs ---------------------------------------------------------
    op.create_table(
        "weight_logs",
        sa.Column("id", UUID, nullable=False),
        sa.Column("user_id", UUID, nullable=False),
        sa.Column("weight", sa.Float(), nullable=False),
        sa.Column("recorded_at", sa.Date(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_weight_logs"),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_weight_logs_user_id_users", ondelete="CASCADE"
        ),
    )
    op.create_index("ix_weight_logs_user_recorded_at", "weight_logs", ["user_id", "recorded_at"])

    # --- water_logs ----------------------------------------------------------
    op.create_table(
        "water_logs",
        sa.Column("id", UUID, nullable=False),
        sa.Column("user_id", UUID, nullable=False),
        sa.Column("amount_ml", sa.Integer(), nullable=False),
        sa.Column("logged_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_water_logs"),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_water_logs_user_id_users", ondelete="CASCADE"
        ),
    )
    op.create_index("ix_water_logs_user_logged_at", "water_logs", ["user_id", "logged_at"])

    # --- streaks (one row per user) -----------------------------------------
    op.create_table(
        "streaks",
        sa.Column("id", UUID, nullable=False),
        sa.Column("user_id", UUID, nullable=False),
        sa.Column("current_streak", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("longest_streak", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("last_active_date", sa.Date(), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_streaks"),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_streaks_user_id_users", ondelete="CASCADE"
        ),
        sa.UniqueConstraint("user_id", name="uq_streaks_user"),
    )

    # --- quests --------------------------------------------------------------
    op.create_table(
        "quests",
        sa.Column("id", UUID, nullable=False),
        sa.Column("user_id", UUID, nullable=False),
        sa.Column("quest_type", _enum(QUEST_TYPE), nullable=False),
        sa.Column("progress", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("target", sa.Integer(), nullable=False),
        sa.Column("reward_coins", sa.Integer(), nullable=False),
        sa.Column("completed", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("quest_date", sa.Date(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_quests"),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_quests_user_id_users", ondelete="CASCADE"
        ),
        sa.UniqueConstraint(
            "user_id", "quest_type", "quest_date", name="uq_quests_user_type_date"
        ),
        sa.CheckConstraint(_in_check("quest_type", QUEST_TYPE), name="quest_type"),
    )

    # --- coin_transactions ---------------------------------------------------
    op.create_table(
        "coin_transactions",
        sa.Column("id", UUID, nullable=False),
        sa.Column("user_id", UUID, nullable=False),
        # Signed: positive credits, negative debits. Balance = SUM(amount).
        sa.Column("amount", sa.Integer(), nullable=False),
        sa.Column("reason", _enum(COIN_REASON), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_coin_transactions"),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_coin_transactions_user_id_users",
            ondelete="CASCADE",
        ),
        sa.CheckConstraint(
            _in_check("reason", COIN_REASON), name="coin_reason"
        ),
    )
    op.create_index(
        "ix_coin_transactions_user_created_at", "coin_transactions", ["user_id", "created_at"]
    )

    # --- subscriptions (one row per user) ------------------------------------
    op.create_table(
        "subscriptions",
        sa.Column("id", UUID, nullable=False),
        sa.Column("user_id", UUID, nullable=False),
        sa.Column("plan_type", _enum(PLAN_TYPE), nullable=False),
        sa.Column("status", _enum(SUBSCRIPTION_STATUS), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        # NUMERIC, not float: money must round-trip exactly.
        sa.Column("price", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_subscriptions"),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_subscriptions_user_id_users", ondelete="CASCADE"
        ),
        sa.UniqueConstraint("user_id", name="uq_subscriptions_user"),
        sa.CheckConstraint(
            _in_check("plan_type", PLAN_TYPE), name="plan_type"
        ),
        sa.CheckConstraint(
            _in_check("status", SUBSCRIPTION_STATUS),
            name="subscription_status",
        ),
    )


def downgrade() -> None:
    op.drop_table("subscriptions")
    op.drop_index("ix_coin_transactions_user_created_at", table_name="coin_transactions")
    op.drop_table("coin_transactions")
    op.drop_table("quests")
    op.drop_table("streaks")
    op.drop_index("ix_water_logs_user_logged_at", table_name="water_logs")
    op.drop_table("water_logs")
    op.drop_index("ix_weight_logs_user_recorded_at", table_name="weight_logs")
    op.drop_table("weight_logs")
    op.drop_index("ix_activity_logs_user_logged_at", table_name="activity_logs")
    op.drop_table("activity_logs")
    op.drop_index("ix_ingredients_food_entry_id", table_name="ingredients")
    op.drop_table("ingredients")
    op.drop_index("ix_food_entries_user_logged_at", table_name="food_entries")
    op.drop_table("food_entries")
    op.drop_table("daily_goals")

    for column in (
        "gender",
        "unit_system",
        "activity_level",
        "diet_type",
        "calorie_calc_mode",
        "subscription_tier",
    ):
        # Bare name: the metadata naming convention prefixes "ck_users_" itself.
        op.drop_constraint(column, "users", type_="check")

    for column in (
        "subscription_tier",
        "calorie_calc_mode",
        "diet_type",
        "activity_level",
        "weight_goal",
        "weight_current",
        "height",
        "unit_system",
        "birth_year",
        "gender",
        "password_hash",
    ):
        op.drop_column("users", column)
