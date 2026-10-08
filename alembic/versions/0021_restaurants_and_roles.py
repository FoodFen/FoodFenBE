"""users.role, restaurants, dishes

Revision ID: 0021
Revises: 0020
Create Date: 2026-10-08
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0021"
down_revision: str | None = "0020"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_MODERATION = "status IN ('pending', 'approved', 'rejected')"


def _moderation_columns() -> list[sa.Column]:
    return [
        sa.Column("status", sa.String(length=8), nullable=False),
        sa.Column("rejection_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
    ]


def upgrade() -> None:
    op.add_column(
        "users", sa.Column("role", sa.String(length=5), server_default="user", nullable=False)
    )
    op.create_check_constraint("user_role", "users", "role IN ('user', 'admin')")

    op.create_table(
        "restaurants",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("address", sa.String(length=500), nullable=False),
        sa.Column("phone", sa.String(length=32), nullable=False),
        sa.Column("opening_hours", sa.String(length=255), nullable=False),
        sa.Column("latitude", sa.Float(), nullable=False),
        sa.Column("longitude", sa.Float(), nullable=False),
        sa.Column("image_url", sa.String(length=2048), nullable=True),
        *_moderation_columns(),
        sa.PrimaryKeyConstraint("id", name="pk_restaurants"),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_restaurants_user_id_users", ondelete="CASCADE"
        ),
        sa.UniqueConstraint("user_id", name="uq_restaurants_user_id"),
        sa.CheckConstraint(_MODERATION, name="moderation_status"),
    )
    op.create_index("ix_restaurants_status", "restaurants", ["status"])

    op.create_table(
        "dishes",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("restaurant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("image_url", sa.String(length=2048), nullable=True),
        sa.Column("price", sa.Numeric(precision=12, scale=0), nullable=False),
        sa.Column("serving_g", sa.Integer(), nullable=False),
        sa.Column("kcal", sa.Integer(), nullable=False),
        sa.Column("protein_g", sa.Float(), nullable=False),
        sa.Column("carbs_g", sa.Float(), nullable=False),
        sa.Column("fat_g", sa.Float(), nullable=False),
        sa.Column("fiber_g", sa.Float(), nullable=True),
        *_moderation_columns(),
        sa.PrimaryKeyConstraint("id", name="pk_dishes"),
        sa.ForeignKeyConstraint(
            ["restaurant_id"],
            ["restaurants.id"],
            name="fk_dishes_restaurant_id_restaurants",
            ondelete="CASCADE",
        ),
        sa.CheckConstraint(_MODERATION, name="moderation_status"),
    )
    op.create_index("ix_dishes_restaurant_id", "dishes", ["restaurant_id"])
    op.create_index("ix_dishes_status", "dishes", ["status"])


def downgrade() -> None:
    op.drop_index("ix_dishes_status", table_name="dishes")
    op.drop_index("ix_dishes_restaurant_id", table_name="dishes")
    op.drop_table("dishes")
    op.drop_index("ix_restaurants_status", table_name="restaurants")
    op.drop_table("restaurants")
    op.drop_constraint("user_role", "users", type_="check")
    op.drop_column("users", "role")
