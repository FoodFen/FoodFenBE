"""chat_messages.dish_ids

Revision ID: 0023
Revises: 0022
Create Date: 2026-10-11
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0023"
down_revision: str | None = "0022"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "chat_messages", sa.Column("dish_ids", sa.JSON(), server_default=sa.text("'[]'"), nullable=False)
    )


def downgrade() -> None:
    op.drop_column("chat_messages", "dish_ids")
