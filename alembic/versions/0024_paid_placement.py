"""paid placement: ad_packages, restaurants.featured_until, payments.ad_days, ad_impressions

Revision ID: 0024
Revises: 0023
Create Date: 2026-10-12
"""
from __future__ import annotations

import uuid
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0024"
down_revision: str | None = "0023"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_OLD_PLAN_TYPE = ("monthly", "annual", "coin_redeem")
_NEW_PLAN_TYPE = (*_OLD_PLAN_TYPE, "ad_package")


def _in_check(column: str, values: tuple[str, ...]) -> str:
    return f"{column} IN ({', '.join(repr(v) for v in values)})"


def _retype_plan_type(values: tuple[str, ...]) -> None:
    # Same as 0012: the enum CHECK lives on both tables that store a plan_type.
    for table in ("subscriptions", "payments"):
        op.drop_constraint("plan_type", table, type_="check")
        op.alter_column(
            table,
            "plan_type",
            type_=sa.String(length=max(len(v) for v in values)),
            existing_nullable=False,
        )
        op.create_check_constraint("plan_type", table, _in_check("plan_type", values))


def upgrade() -> None:
    packages = op.create_table(
        "ad_packages",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("days", sa.Integer(), nullable=False),
        sa.Column("price_vnd", sa.Numeric(12, 0), nullable=False),
        sa.Column("active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_ad_packages"),
    )
    op.bulk_insert(packages, [{"id": uuid.uuid4(), "days": 7, "price_vnd": 99000}])  # edit with the admin API

    op.add_column("restaurants", sa.Column("featured_until", sa.DateTime(timezone=True), nullable=True))

    _retype_plan_type(_NEW_PLAN_TYPE)
    op.add_column("payments", sa.Column("ad_days", sa.Integer(), nullable=True))
    op.create_check_constraint(
        "ad_days",
        "payments",
        "(plan_type = 'ad_package') = (ad_days IS NOT NULL) AND (ad_days IS NULL OR ad_days > 0)",
    )

    op.create_table(
        "ad_impressions",
        sa.Column("restaurant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column("count", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["restaurant_id"], ["restaurants.id"],
            name="fk_ad_impressions_restaurant_id_restaurants", ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("restaurant_id", "day", name="pk_ad_impressions"),
    )


def downgrade() -> None:
    op.drop_table("ad_impressions")
    op.drop_constraint("ad_days", "payments", type_="check")
    op.drop_column("payments", "ad_days")
    # Ad payments have no place under the old plan_type constraint.
    op.execute("DELETE FROM payments WHERE plan_type = 'ad_package'")
    _retype_plan_type(_OLD_PLAN_TYPE)
    op.drop_column("restaurants", "featured_until")
    op.drop_table("ad_packages")
