"""ai_trial_usage: count per day, so free trials reset at Vietnam midnight

Existing rows are stamped with today's Vietnam date, so counters used so far stay in force until
the next midnight and then reset.

Revision ID: 0014
Revises: 0013
Create Date: 2026-10-01
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0014"
down_revision: str | None = "0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_VN_TODAY = "(now() AT TIME ZONE 'Asia/Ho_Chi_Minh')::date"


def upgrade() -> None:
    # The default backfills existing rows; it is dropped again so the app must always pass a day.
    op.add_column(
        "ai_trial_usage",
        sa.Column("day", sa.Date(), server_default=sa.text(_VN_TODAY), nullable=False),
    )
    op.alter_column("ai_trial_usage", "day", server_default=None)
    op.drop_constraint("uq_ai_trial_usage_owner_method", "ai_trial_usage", type_="unique")
    op.create_unique_constraint(
        "uq_ai_trial_usage_owner_method_day", "ai_trial_usage", ["owner_key", "input_method", "day"]
    )


def downgrade() -> None:
    # One row per (owner, method) again: per-day history can't be kept, and trial counters are
    # disposable, so start empty.
    op.execute("DELETE FROM ai_trial_usage")
    op.drop_constraint("uq_ai_trial_usage_owner_method_day", "ai_trial_usage", type_="unique")
    op.drop_column("ai_trial_usage", "day")
    op.create_unique_constraint(
        "uq_ai_trial_usage_owner_method", "ai_trial_usage", ["owner_key", "input_method"]
    )
