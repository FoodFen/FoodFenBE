"""users.protein_g_per_kg, users.fat_share: nullable macro overrides (None = auto)

Revision ID: 0025
Revises: 0024
Create Date: 2026-10-18
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "0025"
down_revision: str | None = "0024"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("protein_g_per_kg", sa.Float(), nullable=True))
    op.add_column("users", sa.Column("fat_share", sa.Float(), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "fat_share")
    op.drop_column("users", "protein_g_per_kg")
