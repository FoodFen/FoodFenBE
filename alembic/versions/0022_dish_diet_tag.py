"""dishes.diet_tag

Revision ID: 0022
Revises: 0021
Create Date: 2026-10-11
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0022"
down_revision: str | None = "0021"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "dishes", sa.Column("diet_tag", sa.String(length=10), server_default="none", nullable=False)
    )
    op.create_check_constraint("diet_tag", "dishes", "diet_tag IN ('none', 'vegetarian', 'vegan')")


def downgrade() -> None:
    op.drop_constraint("diet_tag", "dishes", type_="check")
    op.drop_column("dishes", "diet_tag")
