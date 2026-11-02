"""ORM model for the server-side food catalog (nutrition per 100 g)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, Boolean, CheckConstraint, DateTime, Float, ForeignKey, Integer, String, text
from sqlalchemy.orm import Mapped, mapped_column

from src.domain.entities.catalog_food import CatalogFood, CatalogServing
from src.domain.enums import FoodCategory, FoodSourceKind
from src.infrastructure.db.base import Base
from src.infrastructure.db.mixins import UUIDPrimaryKey
from src.infrastructure.db.types import enum_column


class FoodORM(UUIDPrimaryKey, Base):
    __tablename__ = "foods"
    __table_args__ = (CheckConstraint("(source_kind = 'legacy') = (source_ref IS NULL)", name="source_ref"),)

    slug: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    aliases: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    category: Mapped[FoodCategory] = mapped_column(enum_column(FoodCategory, "food_category"), nullable=False)
    source_kind: Mapped[FoodSourceKind] = mapped_column(enum_column(FoodSourceKind, "food_source_kind"), nullable=False)
    source_ref: Mapped[str | None] = mapped_column(String(64), nullable=True)
    kcal: Mapped[int] = mapped_column(Integer, nullable=False)
    carbs_g: Mapped[float] = mapped_column(Float, nullable=False)
    protein_g: Mapped[float] = mapped_column(Float, nullable=False)
    fat_g: Mapped[float] = mapped_column(Float, nullable=False)
    fiber_g: Mapped[float | None] = mapped_column(Float, nullable=True)  # NULL = not tracked, not 0 g
    servings: Mapped[list[dict]] = mapped_column(JSON, nullable=False)  # [{"label", "grams", "default"}]
    archived: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_by_admin_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    def to_domain(self) -> CatalogFood:
        return CatalogFood(
            id=self.id,
            slug=self.slug,
            name=self.name,
            aliases=list(self.aliases),
            category=self.category,
            source_kind=self.source_kind,
            source_ref=self.source_ref,
            kcal=self.kcal,
            carbs_g=self.carbs_g,
            protein_g=self.protein_g,
            fat_g=self.fat_g,
            fiber_g=self.fiber_g,
            servings=[CatalogServing(s["label"], s["grams"], s["default"]) for s in self.servings],
            archived=self.archived,
            created_at=self.created_at,
            updated_at=self.updated_at,
            updated_by_admin_id=self.updated_by_admin_id,
        )
