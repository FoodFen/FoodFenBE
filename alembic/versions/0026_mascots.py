"""mascots catalogue, user_mascots, users.equipped_mascot_id

Revision ID: 0026
Revises: 0025
Create Date: 2026-10-19
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0026"
down_revision: str | None = "0025"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# (id, name, coin_cost). Bundles are 600 coins / 10 Premium days. Change with SQL; deactivate, never delete.
_MASCOTS = [("default", "Fen", 0), ("sprout", "Sprout", 300), ("berry", "Berry", 600), ("chili", "Chili", 1000)]

_mascots = sa.table(
    "mascots", sa.column("id", sa.String), sa.column("name", sa.String), sa.column("coin_cost", sa.Integer)
)


def upgrade() -> None:
    op.create_table(
        "mascots",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=40), nullable=False),
        sa.Column("coin_cost", sa.Integer(), nullable=False),
        sa.Column("active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_mascots"),
        sa.CheckConstraint("coin_cost >= 0", name="coin_cost"),
    )
    op.bulk_insert(_mascots, [{"id": i, "name": n, "coin_cost": c} for i, n, c in _MASCOTS])

    op.create_table(
        "user_mascots",
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("mascot_id", sa.String(length=32), nullable=False),
        sa.Column("purchased_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("user_id", "mascot_id", name="pk_user_mascots"),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_user_mascots_user_id_users", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["mascot_id"], ["mascots.id"], name="fk_user_mascots_mascot_id_mascots"),
    )

    op.add_column(
        "users",
        sa.Column("equipped_mascot_id", sa.String(length=32), server_default="default", nullable=False),
    )
    op.create_foreign_key(
        "fk_users_equipped_mascot_id_mascots", "users", "mascots", ["equipped_mascot_id"], ["id"]
    )


def downgrade() -> None:
    op.drop_constraint("fk_users_equipped_mascot_id_mascots", "users", type_="foreignkey")
    op.drop_column("users", "equipped_mascot_id")
    op.drop_table("user_mascots")
    op.drop_table("mascots")
