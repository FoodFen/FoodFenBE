"""quest copy (vi/en) on quest_definitions + coin_bundles price list

Revision ID: 0019
Revises: 0018
Create Date: 2026-10-04
"""
from __future__ import annotations

import uuid
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0019"
down_revision: str | None = "0018"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_COPY_COLUMNS = ("title_vi", "title_en", "description_vi", "description_en")
_WIDTHS = {"title_vi": 80, "title_en": 80, "description_vi": 200, "description_en": 200}

# quest_type -> (title_vi, title_en, description_vi, description_en). Static text: when a target
# or completion_ratio is changed with SQL, change the matching description with it.
_COPY = {
    "log_breakfast": (
        "Ghi bữa sáng", "Log breakfast",
        "Ghi lại bữa sáng của bạn hôm nay.", "Log your breakfast today.",
    ),
    "log_all_meals": (
        "Ghi đủ 3 bữa chính", "Log all 3 main meals",
        "Ghi lại bữa sáng, bữa trưa và bữa tối hôm nay.", "Log breakfast, lunch and dinner today.",
    ),
    "hit_calorie_goal": (
        "Đạt mục tiêu calo", "Hit your calorie goal",
        "Ăn đạt ít nhất 90% mục tiêu calo hôm nay.", "Reach at least 90% of your calorie goal today.",
    ),
    "hit_protein_goal": (
        "Đạt mục tiêu đạm", "Hit your protein goal",
        "Ăn đạt ít nhất 90% mục tiêu đạm hôm nay.", "Reach at least 90% of your protein goal today.",
    ),
    "drink_water": (
        "Uống đủ nước", "Drink enough water",
        "Uống đủ 100% mục tiêu nước hôm nay.", "Reach 100% of your daily water goal today.",
    ),
    "log_weight": (
        "Ghi cân nặng", "Log your weight",
        "Ghi lại cân nặng của bạn hôm nay.", "Log your weight today.",
    ),
    "stay_active_week": (
        "Duy trì cả tuần", "Stay active all week",
        "Ghi món ăn ít nhất 5 ngày trong tuần này.", "Log your food on at least 5 days this week.",
    ),
}

# (days, coin_cost) — what was hard-coded as COIN_BUNDLES in redeem_coins.py.
_BUNDLES = [(10, 600), (30, 1500)]

_quest_definitions = sa.table(
    "quest_definitions", sa.column("quest_type", sa.String), *(sa.column(c, sa.String) for c in _COPY_COLUMNS)
)
_coin_bundles = sa.table(
    "coin_bundles",
    sa.column("id", postgresql.UUID(as_uuid=True)),
    sa.column("days", sa.Integer),
    sa.column("coin_cost", sa.Integer),
)


def upgrade() -> None:
    # Add with an empty default so existing rows are valid, fill them, then drop the default:
    # a quest definition added later must come with its text.
    for column in _COPY_COLUMNS:
        op.add_column(
            "quest_definitions",
            sa.Column(column, sa.String(length=_WIDTHS[column]), nullable=False, server_default=""),
        )
    for quest_type, texts in _COPY.items():
        op.execute(
            _quest_definitions.update()
            .where(_quest_definitions.c.quest_type == quest_type)
            .values(dict(zip(_COPY_COLUMNS, texts)))
        )
    for column in _COPY_COLUMNS:
        op.alter_column("quest_definitions", column, server_default=None)

    op.create_table(
        "coin_bundles",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("days", sa.Integer(), nullable=False),
        sa.Column("coin_cost", sa.Integer(), nullable=False),
        sa.Column("active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_coin_bundles"),
        sa.UniqueConstraint("days", name="uq_coin_bundles_days"),
    )
    op.bulk_insert(
        _coin_bundles,
        [{"id": uuid.uuid4(), "days": days, "coin_cost": cost} for days, cost in _BUNDLES],
    )


def downgrade() -> None:
    op.drop_table("coin_bundles")
    for column in _COPY_COLUMNS:
        op.drop_column("quest_definitions", column)
