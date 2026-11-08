"""ai_trial_limits: admin-editable free AI trial limits (single row, seeded 3 guest / 5 signed-in)

Revision ID: 0035
Revises: 0034
Create Date: 2026-11-08
"""
from __future__ import annotations

from collections.abc import Sequence
from uuid import uuid4

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0035"
down_revision: str | None = "0034"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    table = op.create_table(
        "ai_trial_limits",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("guest_limit", sa.Integer(), nullable=False),
        sa.Column("signed_in_limit", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_ai_trial_limits"),
        # Bare names: the naming convention prefixes ck_<table>_.
        sa.CheckConstraint("guest_limit BETWEEN 0 AND 100", name="guest_limit"),
        sa.CheckConstraint("signed_in_limit BETWEEN 0 AND 100", name="signed_in_limit"),
    )
    op.bulk_insert(table, [{"id": uuid4(), "guest_limit": 3, "signed_in_limit": 5}])


def downgrade() -> None:
    op.drop_table("ai_trial_limits")
