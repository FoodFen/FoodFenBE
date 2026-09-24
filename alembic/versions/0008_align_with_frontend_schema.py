"""align backend schema with the front-end local-db contract

Reconciles src.domain against FoodFenFE/src/db/schema.ts:
  - food_entries.name was missing entirely (a core field, not an FE extension).
  - ingredients.fiber_g was missing (mirrors food_entries.fiber_g, Premium-only).
  - subscription_status: "cancelled" -> "canceled" (FE spelling), add "trial".
  - quest_type: replaces the placeholder set with the FE's real quest catalog.
  - quests gains cadence (daily/weekly) and completion_ratio, both FE extensions.
  - coin_reason: "quest_reward" -> "quest_completed", add "spend".
  - subscriptions.end_date becomes nullable (an auto-renewing plan has no fixed end).

No use case creates FoodEntry/Ingredient/Quest/CoinTransaction/Subscription rows
yet, so the data-migrating UPDATE statements below are precautionary, not
covering known data.

Revision ID: 0008
Revises: 0007
Create Date: 2026-09-21
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0008"
down_revision: str | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

OLD_SUBSCRIPTION_STATUS = ("active", "cancelled", "expired")
NEW_SUBSCRIPTION_STATUS = ("active", "canceled", "expired", "trial")

OLD_QUEST_TYPE = ("log_food", "log_water", "log_weight", "log_activity")
NEW_QUEST_TYPE = (
    "log_breakfast",
    "log_all_meals",
    "hit_calorie_goal",
    "hit_protein_goal",
    "drink_water",
    "log_weight",
    "stay_active_week",
)

OLD_COIN_REASON = ("quest_reward", "streak_bonus", "purchase", "adjustment")
NEW_COIN_REASON = ("quest_completed", "streak_bonus", "purchase", "spend", "adjustment")

QUEST_CADENCE = ("daily", "weekly")


def _width(values: tuple[str, ...]) -> int:
    return max(len(v) for v in values)


def _in_check(column: str, values: tuple[str, ...]) -> str:
    rendered = ", ".join(f"'{v}'" for v in values)
    return f"{column} IN ({rendered})"


def upgrade() -> None:
    # --- food_entries.name: core FE field, missing since the initial port ----
    op.add_column(
        "food_entries",
        sa.Column("name", sa.String(length=255), nullable=False, server_default="Meal"),
    )
    op.alter_column("food_entries", "name", server_default=None)

    # --- ingredients.fiber_g: mirrors food_entries.fiber_g, Premium-only -----
    op.add_column("ingredients", sa.Column("fiber_g", sa.Float(), nullable=True))

    # --- subscriptions.status: "cancelled" -> "canceled", add "trial" --------
    op.drop_constraint("subscription_status", "subscriptions", type_="check")
    op.execute("UPDATE subscriptions SET status = 'canceled' WHERE status = 'cancelled'")
    # Narrow to match the new enum's shorter max length ("canceled" < "cancelled"),
    # so the column stays in sync with what enum_column() computes from the enum.
    op.alter_column(
        "subscriptions",
        "status",
        existing_type=sa.String(length=_width(OLD_SUBSCRIPTION_STATUS)),
        type_=sa.String(length=_width(NEW_SUBSCRIPTION_STATUS)),
    )
    op.create_check_constraint(
        "subscription_status", "subscriptions", _in_check("status", NEW_SUBSCRIPTION_STATUS)
    )

    # --- subscriptions.end_date: auto-renewing plans have no fixed end -------
    op.alter_column(
        "subscriptions", "end_date", existing_type=sa.Date(), nullable=True
    )

    # --- quests.quest_type: replace the placeholder set with the FE's real
    # quest catalog (FoodFenFE/src/db/schema.ts) -------------------------------
    op.drop_constraint("quest_type", "quests", type_="check")
    op.alter_column(
        "quests",
        "quest_type",
        existing_type=sa.String(length=_width(OLD_QUEST_TYPE)),
        type_=sa.String(length=_width(NEW_QUEST_TYPE)),
    )
    op.create_check_constraint("quest_type", "quests", _in_check("quest_type", NEW_QUEST_TYPE))

    # --- quests.cadence / completion_ratio: FE extensions ---------------------
    op.add_column(
        "quests",
        sa.Column(
            "cadence",
            sa.String(length=_width(QUEST_CADENCE)),
            nullable=False,
            server_default="daily",
        ),
    )
    op.create_check_constraint("cadence", "quests", _in_check("cadence", QUEST_CADENCE))
    op.add_column(
        "quests",
        sa.Column(
            "completion_ratio", sa.Float(), nullable=False, server_default=sa.text("1")
        ),
    )

    # --- coin_transactions.reason: "quest_reward" -> "quest_completed", add "spend"
    # Widen *before* writing "quest_completed" — it's longer than the old column.
    op.drop_constraint("coin_reason", "coin_transactions", type_="check")
    op.alter_column(
        "coin_transactions",
        "reason",
        existing_type=sa.String(length=_width(OLD_COIN_REASON)),
        type_=sa.String(length=_width(NEW_COIN_REASON)),
    )
    op.execute(
        "UPDATE coin_transactions SET reason = 'quest_completed' WHERE reason = 'quest_reward'"
    )
    op.create_check_constraint(
        "coin_reason", "coin_transactions", _in_check("reason", NEW_COIN_REASON)
    )


def downgrade() -> None:
    op.drop_constraint("coin_reason", "coin_transactions", type_="check")
    op.execute(
        "UPDATE coin_transactions SET reason = 'quest_reward' WHERE reason = 'quest_completed'"
    )
    op.execute("DELETE FROM coin_transactions WHERE reason = 'spend'")
    op.alter_column(
        "coin_transactions",
        "reason",
        existing_type=sa.String(length=_width(NEW_COIN_REASON)),
        type_=sa.String(length=_width(OLD_COIN_REASON)),
    )
    op.create_check_constraint(
        "coin_reason", "coin_transactions", _in_check("reason", OLD_COIN_REASON)
    )

    op.drop_column("quests", "completion_ratio")
    op.drop_constraint("cadence", "quests", type_="check")
    op.drop_column("quests", "cadence")

    op.drop_constraint("quest_type", "quests", type_="check")
    op.execute(
        "DELETE FROM quests WHERE quest_type NOT IN ({})".format(
            ", ".join(f"'{v}'" for v in OLD_QUEST_TYPE)
        )
    )
    op.alter_column(
        "quests",
        "quest_type",
        existing_type=sa.String(length=_width(NEW_QUEST_TYPE)),
        type_=sa.String(length=_width(OLD_QUEST_TYPE)),
    )
    op.create_check_constraint("quest_type", "quests", _in_check("quest_type", OLD_QUEST_TYPE))

    op.alter_column(
        "subscriptions", "end_date", existing_type=sa.Date(), nullable=False
    )

    op.drop_constraint("subscription_status", "subscriptions", type_="check")
    op.execute("DELETE FROM subscriptions WHERE status = 'trial'")
    # Widen *before* writing "cancelled" — it's longer than the current column.
    op.alter_column(
        "subscriptions",
        "status",
        existing_type=sa.String(length=_width(NEW_SUBSCRIPTION_STATUS)),
        type_=sa.String(length=_width(OLD_SUBSCRIPTION_STATUS)),
    )
    op.execute("UPDATE subscriptions SET status = 'cancelled' WHERE status = 'canceled'")
    op.create_check_constraint(
        "subscription_status", "subscriptions", _in_check("status", OLD_SUBSCRIPTION_STATUS)
    )

    op.drop_column("ingredients", "fiber_g")
    op.drop_column("food_entries", "name")
