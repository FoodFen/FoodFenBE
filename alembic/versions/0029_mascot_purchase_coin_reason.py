"""mascot_purchase coin reason: separate mascot buys from Premium redeems

Revision ID: 0029
Revises: 0028
Create Date: 2026-10-30
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0029"
down_revision: str | None = "0028"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_OLD_COIN_REASON = (
    "quest_completed", "streak_bonus", "purchase", "spend", "adjustment", "quiz_daily", "quiz_practice",
)
_NEW_COIN_REASON = (*_OLD_COIN_REASON, "mascot_purchase")


def _in_check(column: str, values: tuple[str, ...]) -> str:
    return f"{column} IN ({', '.join(repr(v) for v in values)})"


def upgrade() -> None:
    # "mascot_purchase" is as long as "quest_completed" (15), so the VARCHAR(15) stays.
    op.drop_constraint("coin_reason", "coin_transactions", type_="check")
    op.create_check_constraint(
        "coin_reason", "coin_transactions", _in_check("reason", _NEW_COIN_REASON)
    )
    # Old mascot buys were written as 'spend': the same user's mascot row, same price, same request.
    op.execute(
        """
        UPDATE coin_transactions ct SET reason = 'mascot_purchase'
        FROM user_mascots um JOIN mascots m ON m.id = um.mascot_id
        WHERE ct.reason = 'spend'
          AND um.user_id = ct.user_id
          AND ct.amount = -m.coin_cost
          AND abs(extract(epoch FROM ct.created_at - um.purchased_at)) < 5
        """
    )


def downgrade() -> None:
    op.drop_constraint("coin_reason", "coin_transactions", type_="check")
    op.execute("UPDATE coin_transactions SET reason = 'spend' WHERE reason = 'mascot_purchase'")
    op.create_check_constraint(
        "coin_reason", "coin_transactions", _in_check("reason", _OLD_COIN_REASON)
    )
