"""ai_trial_usage: free AI analyses used per device/account and input method

Revision ID: 0013
Revises: 0012
Create Date: 2026-10-01
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0013"
down_revision: str | None = "0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_METHOD = ("image", "text", "voice")


def upgrade() -> None:
    op.create_table(
        "ai_trial_usage",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("owner_key", sa.String(length=80), nullable=False),
        sa.Column("input_method", sa.String(length=5), nullable=False),
        sa.Column("used", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_ai_trial_usage"),
        sa.UniqueConstraint("owner_key", "input_method", name="uq_ai_trial_usage_owner_method"),
        sa.CheckConstraint(f"input_method IN {_METHOD}", name="ai_trial_method"),
    )


def downgrade() -> None:
    op.drop_table("ai_trial_usage")
