"""add social_identities table

Revision ID: 0006
Revises: 0005
Create Date: 2026-09-19
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_PROVIDER = ("google", "apple")


def upgrade() -> None:
    op.create_table(
        "social_identities",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("provider", sa.String(length=6), nullable=False),
        sa.Column("provider_user_id", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_social_identities"),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_social_identities_user_id_users",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "provider", "provider_user_id", name="uq_social_identities_provider_sub"
        ),
        sa.CheckConstraint(f"provider IN {_PROVIDER}", name="auth_provider"),
    )


def downgrade() -> None:
    op.drop_table("social_identities")
