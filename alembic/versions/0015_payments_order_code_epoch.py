"""start payments.order_code at epoch seconds

PayOS remembers every order_code it has ever seen, so a sequence that restarts
at 1 (reset/new DB, or another env on the same PayOS keys) collides with
"Đơn thanh toán đã tồn tại". Jump past anything used before; never go backwards.

Revision ID: 0015
Revises: 0014
Create Date: 2026-10-03
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0015"
down_revision: str | None = "0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        "SELECT setval(pg_get_serial_sequence('payments', 'order_code'), "
        "GREATEST(extract(epoch FROM now())::bigint, (SELECT COALESCE(MAX(order_code), 0) FROM payments)))"
    )


def downgrade() -> None:
    pass  # a sequence can't safely rewind; codes already sent to PayOS stay used
