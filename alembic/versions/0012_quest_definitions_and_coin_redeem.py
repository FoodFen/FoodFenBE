"""quest_definitions catalog + coin_redeem plan type

Revision ID: 0012
Revises: 0011
Create Date: 2026-09-30
"""
from __future__ import annotations

import uuid
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0012"
down_revision: str | None = "0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_OLD_PLAN_TYPE = ("monthly", "annual")
_NEW_PLAN_TYPE = ("monthly", "annual", "coin_redeem")
_QUEST_TYPE = (
    "log_breakfast",
    "log_all_meals",
    "hit_calorie_goal",
    "hit_protein_goal",
    "drink_water",
    "log_weight",
    "stay_active_week",
)
_CADENCE = ("daily", "weekly")

# (quest_type, target, reward_coins, cadence, completion_ratio) — placeholders, tune with an UPDATE.
_SEED = [
    ("log_breakfast", 1, 10, "daily", 1.0),
    ("log_all_meals", 3, 20, "daily", 1.0),
    ("hit_calorie_goal", 100, 20, "daily", 0.9),
    ("hit_protein_goal", 100, 20, "daily", 0.9),
    ("drink_water", 100, 10, "daily", 1.0),
    ("log_weight", 1, 10, "daily", 1.0),
    ("stay_active_week", 5, 50, "weekly", 1.0),
]


def _in_check(column: str, values: tuple[str, ...]) -> str:
    return f"{column} IN ({', '.join(repr(v) for v in values)})"


def _retype_plan_type(values: tuple[str, ...]) -> None:
    for table in ("subscriptions", "payments"):
        op.drop_constraint("plan_type", table, type_="check")
        op.alter_column(
            table,
            "plan_type",
            type_=sa.String(length=max(len(v) for v in values)),
            existing_nullable=False,
        )
        op.create_check_constraint("plan_type", table, _in_check("plan_type", values))


def upgrade() -> None:
    _retype_plan_type(_NEW_PLAN_TYPE)
    definitions = op.create_table(
        "quest_definitions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("quest_type", sa.String(length=16), nullable=False),
        sa.Column("target", sa.Integer(), nullable=False),
        sa.Column("reward_coins", sa.Integer(), nullable=False),
        sa.Column("cadence", sa.String(length=6), nullable=False),
        sa.Column("completion_ratio", sa.Float(), server_default=sa.text("1"), nullable=False),
        sa.Column("active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_quest_definitions"),
        sa.UniqueConstraint("quest_type", name="uq_quest_definitions_quest_type"),
        sa.CheckConstraint(_in_check("quest_type", _QUEST_TYPE), name="quest_type"),
        sa.CheckConstraint(_in_check("cadence", _CADENCE), name="cadence"),
    )
    op.bulk_insert(
        definitions,
        [
            {
                "id": uuid.uuid4(),
                "quest_type": q,
                "target": t,
                "reward_coins": r,
                "cadence": c,
                "completion_ratio": ratio,
            }
            for q, t, r, c, ratio in _SEED
        ],
    )


def downgrade() -> None:
    op.drop_table("quest_definitions")
    # Coin-funded rows have no place under the old constraint.
    op.execute("DELETE FROM subscriptions WHERE plan_type = 'coin_redeem'")
    _retype_plan_type(_OLD_PLAN_TYPE)
