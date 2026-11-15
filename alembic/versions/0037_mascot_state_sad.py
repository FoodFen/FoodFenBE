"""mascot_images: allow the `sad` state

Revision ID: 0037
Revises: 0036
Create Date: 2026-11-15
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0037"
down_revision: str | None = "0036"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_OLD_STATES = (
    "idle", "hungry", "thirsty", "eating", "drinking", "exercising", "thinking", "happy", "confused",
)
_NEW_STATES = (*_OLD_STATES, "sad")


def _in_check(values: tuple[str, ...]) -> str:
    return f"state IN ({', '.join(repr(v) for v in values)})"


def upgrade() -> None:
    op.drop_constraint("mascot_state", "mascot_images", type_="check")
    op.create_check_constraint("mascot_state", "mascot_images", _in_check(_NEW_STATES))


def downgrade() -> None:
    op.drop_constraint("mascot_state", "mascot_images", type_="check")
    op.execute("DELETE FROM mascot_images WHERE state = 'sad'")
    op.create_check_constraint("mascot_state", "mascot_images", _in_check(_OLD_STATES))
