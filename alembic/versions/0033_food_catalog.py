"""foods: server-side food catalog, seeded with the Mobile app's built catalog

Seeded from the Mobile app's built `src/data/catalog/foods.json` (670 foods: NIN 2007, USDA, recipes,
labels), copied to `alembic/data/foods.json`. From now on this table is the source of truth for new
foods and edits; that file is a frozen seed and later changes go in new migrations or the admin API.

`verified` is not stored (derived: every source_kind but `legacy`). Name/alias fold strings and serving
ids from the JSON are not stored either.

Revision ID: 0033
Revises: 0032
Create Date: 2026-11-02
"""
from __future__ import annotations

import json
import uuid
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0033"
down_revision: str | None = "0032"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_CATEGORIES = (
    "an-vat", "banh-mi", "bun-tron", "che-trang-mieng", "chien-nuong", "com",
    "do-uong", "mon-man", "mon-nuoc", "nguyen-lieu", "rau-chay", "trai-cay",
)
_SOURCE_KINDS = ("nin", "usda", "recipe", "label", "team", "legacy")


def _in_check(column: str, values: tuple[str, ...]) -> str:
    return f"{column} IN ({', '.join(repr(v) for v in values)})"


class _Json(sa.types.TypeDecorator):
    """sa.JSON has no literal renderer, so `--sql` (offline) could not render the seed rows."""

    impl = sa.JSON
    cache_ok = True

    def process_literal_param(self, value, dialect):
        return "'" + json.dumps(value, ensure_ascii=False).replace("'", "''") + "'"


_foods = sa.table(
    "foods",
    sa.column("id", postgresql.UUID(as_uuid=True)),
    sa.column("slug", sa.String),
    sa.column("name", sa.String),
    sa.column("aliases", _Json),
    sa.column("category", sa.String),
    sa.column("source_kind", sa.String),
    sa.column("source_ref", sa.String),
    sa.column("kcal", sa.Integer),
    sa.column("carbs_g", sa.Float),
    sa.column("protein_g", sa.Float),
    sa.column("fat_g", sa.Float),
    sa.column("fiber_g", sa.Float),
    sa.column("servings", _Json),
    sa.column("archived", sa.Boolean),
    sa.column("created_at", sa.DateTime(timezone=True)),
    sa.column("updated_at", sa.DateTime(timezone=True)),
    sa.column("updated_by_admin_id", sa.Integer),
)


def _load() -> list[dict]:
    path = Path(__file__).resolve().parents[1] / "data" / "foods.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _rows(foods: list[dict]) -> list[dict]:
    now = datetime.now(UTC)
    rows = []
    for f in foods:
        per = f["per100g"]
        kind = f["source"] if f.get("verified") else "legacy"
        rows.append(
            {
                "id": uuid.uuid5(uuid.NAMESPACE_URL, f"foodfen:food:{f['id']}"),
                "slug": f["id"],
                "name": f["name"],
                "aliases": f["aliases"],
                "category": f["category"],
                "source_kind": kind,
                "source_ref": f.get("sourceRef") or ("recipe" if kind == "recipe" else None),
                "kcal": per["kcal"],
                "carbs_g": per["carbsG"],
                "protein_g": per["proteinG"],
                "fat_g": per["fatG"],
                "fiber_g": per.get("fiberG"),  # absent stays NULL (not tracked), never 0
                "servings": [
                    {"label": s["label"], "grams": s["grams"], "default": s.get("default", False)}
                    for s in f["servings"]
                ],
                "archived": False,
                "created_at": now,
                "updated_at": now,
                "updated_by_admin_id": None,
            }
        )
    return rows


def upgrade() -> None:
    op.create_table(
        "foods",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("slug", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("aliases", sa.JSON(), nullable=False),
        sa.Column("category", sa.String(length=15), nullable=False),
        sa.Column("source_kind", sa.String(length=6), nullable=False),
        sa.Column("source_ref", sa.String(length=64), nullable=True),
        sa.Column("kcal", sa.Integer(), nullable=False),
        sa.Column("carbs_g", sa.Float(), nullable=False),
        sa.Column("protein_g", sa.Float(), nullable=False),
        sa.Column("fat_g", sa.Float(), nullable=False),
        sa.Column("fiber_g", sa.Float(), nullable=True),
        sa.Column("servings", sa.JSON(), nullable=False),
        sa.Column("archived", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_by_admin_id", sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_foods"),
        sa.UniqueConstraint("slug", name="uq_foods_slug"),
        sa.ForeignKeyConstraint(
            ["updated_by_admin_id"], ["users.id"], name="fk_foods_updated_by_admin_id_users", ondelete="SET NULL"
        ),
        # Bare names: the naming convention prefixes ck_foods_.
        sa.CheckConstraint(_in_check("category", _CATEGORIES), name="food_category"),
        sa.CheckConstraint(_in_check("source_kind", _SOURCE_KINDS), name="food_source_kind"),
        sa.CheckConstraint("(source_kind = 'legacy') = (source_ref IS NULL)", name="source_ref"),
    )
    op.bulk_insert(_foods, _rows(_load()))


def downgrade() -> None:
    op.drop_table("foods")
