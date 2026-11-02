"""mascots.body_color: per-mascot colour of the body circle behind the art

Revision ID: 0031
Revises: 0030
Create Date: 2026-11-01
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0031"
down_revision: str | None = "0030"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # NULL = the app's theme default, so no backfill and no server default.
    op.add_column("mascots", sa.Column("body_color", sa.String(length=7), nullable=True))


def downgrade() -> None:
    op.drop_column("mascots", "body_color")
