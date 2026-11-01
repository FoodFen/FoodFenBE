"""mascot_images: per-state artwork for each mascot

Revision ID: 0030
Revises: 0029
Create Date: 2026-10-30
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0030"
down_revision: str | None = "0029"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_STATES = ("idle", "hungry", "thirsty", "eating", "drinking", "exercising", "thinking", "happy", "confused")


def upgrade() -> None:
    op.create_table(
        "mascot_images",
        sa.Column("mascot_id", sa.String(length=32), nullable=False),
        sa.Column("state", sa.String(length=10), nullable=False),
        sa.Column("url", sa.String(length=2048), nullable=False),
        sa.PrimaryKeyConstraint("mascot_id", "state", name="pk_mascot_images"),
        sa.ForeignKeyConstraint(
            ["mascot_id"], ["mascots.id"], name="fk_mascot_images_mascot_id_mascots", ondelete="CASCADE"
        ),
        # Bare name: the naming convention prefixes ck_mascot_images_.
        sa.CheckConstraint(f"state IN ({', '.join(repr(s) for s in _STATES)})", name="mascot_state"),
    )


def downgrade() -> None:
    op.drop_table("mascot_images")
