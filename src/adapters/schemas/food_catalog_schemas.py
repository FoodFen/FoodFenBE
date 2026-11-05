"""HTTP wire models for the public catalog sync endpoint (GET /foods)."""

from __future__ import annotations

from datetime import datetime

from pydantic import Field

from src.adapters.schemas.admin_food_schemas import FoodServing
from src.adapters.schemas.base import CamelModel
from src.application.dtos.food_admin import AdminFoodDTO
from src.application.dtos.food_catalog import CatalogSyncDTO
from src.domain.enums import FoodCategory, FoodSourceKind


class Per100g(CamelModel):
    kcal: int
    carbs_g: float
    protein_g: float
    fat_g: float
    fiber_g: float | None  # null = not tracked


class CatalogFoodResponse(CamelModel):
    slug: str
    name: str
    name_en: str | None
    aliases: list[str]
    category: FoodCategory
    source_kind: FoodSourceKind
    source_ref: str | None
    verified: bool
    per100g: Per100g = Field(alias="per100g")  # to_camel would give "per100G"
    servings: list[FoodServing]
    archived: bool
    updated_at: datetime

    @classmethod
    def from_dto(cls, f: AdminFoodDTO) -> CatalogFoodResponse:
        return cls(
            slug=f.slug, name=f.name, name_en=f.name_en, aliases=f.aliases, category=f.category,
            source_kind=f.source_kind, source_ref=f.source_ref, verified=f.verified,
            per100g=Per100g(kcal=f.kcal, carbs_g=f.carbs_g, protein_g=f.protein_g, fat_g=f.fat_g, fiber_g=f.fiber_g),
            servings=[FoodServing(**vars(s)) for s in f.servings], archived=f.archived, updated_at=f.updated_at,
        )


class CatalogFoodsResponse(CamelModel):
    foods: list[CatalogFoodResponse]
    server_time: datetime

    @classmethod
    def from_dto(cls, dto: CatalogSyncDTO) -> CatalogFoodsResponse:
        return cls(foods=[CatalogFoodResponse.from_dto(f) for f in dto.foods], server_time=dto.server_time)
