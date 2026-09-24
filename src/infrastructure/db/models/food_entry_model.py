"""ORM models for food entries and their ingredients."""

from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from sqlalchemy import Date, DateTime, Float, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.domain.entities.food_entry import FoodEntry
from src.domain.entities.ingredient import Ingredient
from src.domain.enums import AiFeedback, InputMethod, MealType
from src.infrastructure.db.base import Base
from src.infrastructure.db.mixins import UserOwned, UUIDPrimaryKey
from src.infrastructure.db.types import enum_column


class IngredientORM(UUIDPrimaryKey, Base):
    __tablename__ = "ingredients"

    food_entry_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("food_entries.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    quantity_g: Mapped[float] = mapped_column(Float, nullable=False)
    kcal: Mapped[int] = mapped_column(Integer, nullable=False)
    carbs_g: Mapped[float] = mapped_column(Float, nullable=False)
    protein_g: Mapped[float] = mapped_column(Float, nullable=False)
    fat_g: Mapped[float] = mapped_column(Float, nullable=False)
    fiber_g: Mapped[float | None] = mapped_column(Float, nullable=True)

    def to_domain(self) -> Ingredient:
        return Ingredient(
            id=self.id,
            food_entry_id=self.food_entry_id,
            name=self.name,
            quantity_g=self.quantity_g,
            kcal=self.kcal,
            carbs_g=self.carbs_g,
            protein_g=self.protein_g,
            fat_g=self.fat_g,
            fiber_g=self.fiber_g,
        )

    @staticmethod
    def from_domain(ingredient: Ingredient) -> IngredientORM:
        return IngredientORM(
            id=ingredient.id,
            food_entry_id=ingredient.food_entry_id,
            name=ingredient.name,
            quantity_g=ingredient.quantity_g,
            kcal=ingredient.kcal,
            carbs_g=ingredient.carbs_g,
            protein_g=ingredient.protein_g,
            fat_g=ingredient.fat_g,
            fiber_g=ingredient.fiber_g,
        )


class FoodEntryORM(UUIDPrimaryKey, UserOwned, Base):
    __tablename__ = "food_entries"
    __table_args__ = (
        Index("ix_food_entries_user_logged_at", "user_id", "logged_at"),
        Index("ix_food_entries_user_logged_on", "user_id", "logged_on"),
        UniqueConstraint("user_id", "client_id", name="uq_food_entries_client_id"),
    )

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    input_method: Mapped[InputMethod] = mapped_column(
        enum_column(InputMethod, "input_method"), nullable=False
    )
    meal_type: Mapped[MealType] = mapped_column(enum_column(MealType, "meal_type"), nullable=False)
    client_id: Mapped[str] = mapped_column(String(64), nullable=False)
    image_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    total_kcal: Mapped[int] = mapped_column(Integer, nullable=False)
    carbs_g: Mapped[float] = mapped_column(Float, nullable=False)
    protein_g: Mapped[float] = mapped_column(Float, nullable=False)
    fat_g: Mapped[float] = mapped_column(Float, nullable=False)
    # Premium-only. NULL means "not tracked", which is not the same as 0.0 g.
    fiber_g: Mapped[float | None] = mapped_column(Float, nullable=True)
    ai_feedback: Mapped[AiFeedback | None] = mapped_column(
        enum_column(AiFeedback, "ai_feedback"), nullable=True
    )
    logged_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    logged_on: Mapped[date] = mapped_column(Date, nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # selectin (not the lazy default) so to_domain() can read .ingredients without
    # tripping MissingGreenlet on the async engine.
    ingredients: Mapped[list[IngredientORM]] = relationship(
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    def to_domain(self) -> FoodEntry:
        return FoodEntry(
            id=self.id,
            user_id=self.user_id,
            name=self.name,
            input_method=self.input_method,
            meal_type=self.meal_type,
            client_id=self.client_id,
            total_kcal=self.total_kcal,
            carbs_g=self.carbs_g,
            protein_g=self.protein_g,
            fat_g=self.fat_g,
            image_url=self.image_url,
            fiber_g=self.fiber_g,
            ai_feedback=self.ai_feedback,
            logged_at=self.logged_at,
            logged_on=self.logged_on,
            ingredients=[row.to_domain() for row in self.ingredients],
        )

    @staticmethod
    def from_domain(entry: FoodEntry) -> FoodEntryORM:
        return FoodEntryORM(
            id=entry.id,
            user_id=entry.user_id,
            name=entry.name,
            input_method=entry.input_method,
            meal_type=entry.meal_type,
            client_id=entry.client_id,
            image_url=entry.image_url,
            total_kcal=entry.total_kcal,
            carbs_g=entry.carbs_g,
            protein_g=entry.protein_g,
            fat_g=entry.fat_g,
            fiber_g=entry.fiber_g,
            ai_feedback=entry.ai_feedback,
            logged_at=entry.logged_at,
            logged_on=entry.logged_on,
            ingredients=[IngredientORM.from_domain(i) for i in entry.ingredients],
        )
