"""index quizzes by user

Revision ID: 0018
Revises: 0017
Create Date: 2026-10-03
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0018"
down_revision: str | None = "0017"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index("ix_quizzes_user_id_created_at", "quizzes", ["user_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_quizzes_user_id_created_at", table_name="quizzes")
