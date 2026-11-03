"""HTTP wire models for the admin food catalog and the AI's unmatched names."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from src.adapters.schemas.base import CamelModel
from src.application.dtos.food_admin import (
    AdminFoodDTO,
    AdminFoodListDTO,
    FoodChangeDTO,
    FoodEditDTO,
    FoodMissDTO,
    FoodMissListDTO,
    FoodServingDTO,
)
from src.domain.enums import FoodCategory, FoodChangeAction, FoodMissStatus, FoodSourceKind


class FoodServing(CamelModel):
    label: str
    grams: int
    default: bool


class AdminFoodRowResponse(CamelModel):
    slug: str
    name: str
    name_en: str | None
    category: FoodCategory
    source_kind: FoodSourceKind
    source_ref: str | None
    verified: bool
    kcal: int
    carbs_g: float
    protein_g: float
    fat_g: float
    fiber_g: float | None
    archived: bool
    updated_at: datetime


class AdminFoodResponse(AdminFoodRowResponse):
    aliases: list[str]
    servings: list[FoodServing]
    created_at: datetime
    updated_by_email: str | None

    @classmethod
    def from_dto(cls, dto: AdminFoodDTO) -> AdminFoodResponse:
        return cls(**{**vars(dto), "servings": [FoodServing(**vars(s)) for s in dto.servings]})


class AdminFoodListResponse(CamelModel):
    foods: list[AdminFoodRowResponse]
    total: int
    next_cursor: str | None

    @classmethod
    def from_dto(cls, dto: AdminFoodListDTO) -> AdminFoodListResponse:
        # A row is the detail's leading fields; the rest of the DTO is ignored.
        return cls(
            foods=[AdminFoodRowResponse(**vars(f)) for f in dto.foods], total=dto.total, next_cursor=dto.next_cursor
        )


class CreateFoodRequest(CamelModel):
    """The entity enforces every limit (422); the wire only fixes types."""

    name: str
    name_en: str | None = None
    aliases: list[str] = []
    category: FoodCategory
    kcal: int
    carbs_g: float
    protein_g: float
    fat_g: float
    fiber_g: float | None = None  # null = not tracked
    servings: list[FoodServing]
    miss_id: UUID | None = None  # the unmatched name this food answers; unknown or not open is ignored


class UpdateFoodRequest(CamelModel):
    """Partial: an absent (or null) field is left as is. ``name_en`` and ``fiber_g`` are the exception: an
    explicit ``null`` clears them."""

    name: str | None = None
    name_en: str | None = None
    aliases: list[str] | None = None
    category: FoodCategory | None = None
    kcal: int | None = None
    carbs_g: float | None = None
    protein_g: float | None = None
    fat_g: float | None = None
    fiber_g: float | None = None
    servings: list[FoodServing] | None = None

    def to_dto(self) -> FoodEditDTO:
        sent = {
            k: getattr(self, k)
            for k in self.model_fields_set
            if getattr(self, k) is not None or k in ("name_en", "fiber_g")
        }
        if "servings" in sent:
            sent["servings"] = [FoodServingDTO(**vars(s)) for s in sent["servings"]]
        return FoodEditDTO(**sent)


class FoodSnapshot(CamelModel):
    name: str
    name_en: str | None
    aliases: list[str]
    category: FoodCategory
    kcal: int
    carbs_g: float
    protein_g: float
    fat_g: float
    fiber_g: float | None
    servings: list[FoodServing]
    source_kind: FoodSourceKind
    source_ref: str | None
    archived: bool


class FoodChangeResponse(CamelModel):
    id: UUID
    action: FoodChangeAction
    admin_email: str | None
    created_at: datetime
    before: FoodSnapshot | None  # null for a create
    after: FoodSnapshot

    @classmethod
    def from_dto(cls, dto: FoodChangeDTO) -> FoodChangeResponse:
        return cls(
            id=dto.id, action=dto.action, admin_email=dto.admin_email, created_at=dto.created_at,
            before=FoodSnapshot(**dto.before) if dto.before is not None else None, after=FoodSnapshot(**dto.after),
        )


class ExistingFood(CamelModel):
    slug: str
    name: str


class FoodMissResponse(CamelModel):
    id: UUID
    key: str
    name: str
    language: str
    count: int
    first_seen_at: datetime
    last_seen_at: datetime
    status: FoodMissStatus
    existing_food: ExistingFood | None

    @classmethod
    def from_dto(cls, dto: FoodMissDTO) -> FoodMissResponse:
        return cls(**{**vars(dto), "existing_food": ExistingFood(**vars(dto.existing_food)) if dto.existing_food else None})


class FoodMissListResponse(CamelModel):
    misses: list[FoodMissResponse]
    total: int
    next_cursor: str | None

    @classmethod
    def from_dto(cls, dto: FoodMissListDTO) -> FoodMissListResponse:
        return cls(misses=[FoodMissResponse.from_dto(m) for m in dto.misses], total=dto.total, next_cursor=dto.next_cursor)
