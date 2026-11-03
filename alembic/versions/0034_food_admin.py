"""foods.name_en (backfilled from the seed), food_changes audit log, food_misses

`name_en` = the first ASCII alias of the seed food that adds a word the Vietnamese name lacks
(`bun cha` is skipped for "Bún chả", `grilled pork with noodles` is taken); the alias stays in `aliases`.
The seed file is the source (prod data == seed today), so `--sql` renders offline. Foods the rule leaves
null (16 of 670) are for an admin to fill in.

Revision ID: 0034
Revises: 0033
Create Date: 2026-11-03
"""
from __future__ import annotations

import json
import re
import unicodedata
from collections.abc import Sequence
from pathlib import Path

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0034"
down_revision: str | None = "0033"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_ACTIONS = ("create", "update", "archive", "unarchive")
_MISS_STATUSES = ("open", "ignored", "resolved")

_foods = sa.table("foods", sa.column("slug", sa.String), sa.column("name_en", sa.String))


def _fold(text: str) -> str:
    """Copy of `src.application.dish_fit.fold`: a migration must not import `src`."""
    nfd = unicodedata.normalize("NFD", text.casefold())
    return "".join(c for c in nfd if not unicodedata.combining(c)).replace("đ", "d")


def _words(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", _fold(text)))


def _backfill() -> list[tuple[str, str]]:
    """(slug, name_en) for every seed food that has one."""
    path = Path(__file__).resolve().parents[1] / "data" / "foods.json"
    pairs = []
    for f in json.loads(path.read_text(encoding="utf-8")):
        name_words = _words(f["name"])
        en = next((a for a in f["aliases"] if a.isascii() and not _words(a) <= name_words), None)
        if en is not None:
            pairs.append((f["id"], en))
    return pairs


def _in_check(column: str, values: tuple[str, ...]) -> str:
    return f"{column} IN ({', '.join(repr(v) for v in values)})"


def upgrade() -> None:
    op.add_column("foods", sa.Column("name_en", sa.String(length=120), nullable=True))
    for slug, en in _backfill():
        op.execute(
            sa.update(_foods).where(_foods.c.slug == slug, _foods.c.name_en.is_(None)).values(name_en=en)
        )

    op.create_table(
        "food_changes",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("food_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("admin_id", sa.Integer(), nullable=True),
        sa.Column("action", sa.String(length=9), nullable=False),
        sa.Column("before", sa.JSON(), nullable=True),
        sa.Column("after", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_food_changes"),
        sa.ForeignKeyConstraint(["food_id"], ["foods.id"], name="fk_food_changes_food_id_foods"),
        sa.ForeignKeyConstraint(
            ["admin_id"], ["users.id"], name="fk_food_changes_admin_id_users", ondelete="SET NULL"
        ),
        # Bare names: the naming convention prefixes ck_<table>_.
        sa.CheckConstraint(_in_check("action", _ACTIONS), name="food_change_action"),
    )
    op.create_index("ix_food_changes_food_id", "food_changes", ["food_id"])

    op.create_table(
        "food_misses",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("key", sa.String(length=120), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("language", sa.String(length=8), nullable=False),
        sa.Column("count", sa.Integer(), nullable=False),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(length=8), nullable=False),
        sa.Column("resolved_food_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_food_misses"),
        sa.UniqueConstraint("key", name="uq_food_misses_key"),
        sa.ForeignKeyConstraint(["resolved_food_id"], ["foods.id"], name="fk_food_misses_resolved_food_id_foods"),
        sa.CheckConstraint(_in_check("status", _MISS_STATUSES), name="food_miss_status"),
        sa.CheckConstraint("(status = 'resolved') = (resolved_food_id IS NOT NULL)", name="resolved_food"),
    )


def downgrade() -> None:
    op.drop_table("food_misses")
    op.drop_index("ix_food_changes_food_id", table_name="food_changes")
    op.drop_table("food_changes")
    op.drop_column("foods", "name_en")
