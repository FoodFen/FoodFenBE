"""HTTP wire models for owner restaurant / dish endpoints (camelCase)."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import ConfigDict, Field, field_validator

from src.adapters.schemas.base import CamelModel, MoneyField
from src.application.dtos.restaurant import DishOutputDTO, RestaurantOutputDTO
from src.domain.enums import ModerationStatus

_HTTPS = r"^https://"


def _not_null(value):
    """PATCH fields are optional but a *sent* ``null`` on a required one is a field error (422),
    never a 500 from the entity. Field validators only run for fields the client sent."""
    if value is None:
        raise ValueError("cannot be null")
    return value


class RestaurantResponse(CamelModel):
    id: UUID
    name: str
    description: str | None
    address: str
    phone: str
    opening_hours: str
    latitude: float
    longitude: float
    image_url: str | None
    status: ModerationStatus
    rejection_reason: str | None
    created_at: datetime
    updated_at: datetime
    reviewed_at: datetime | None

    @classmethod
    def from_dto(cls, dto: RestaurantOutputDTO) -> RestaurantResponse:
        return cls(**vars(dto))


class DishResponse(CamelModel):
    id: UUID
    restaurant_id: UUID
    name: str
    description: str | None
    image_url: str | None
    price: MoneyField
    serving_g: int
    kcal: int
    protein_g: float
    carbs_g: float
    fat_g: float
    fiber_g: float | None
    status: ModerationStatus
    rejection_reason: str | None
    created_at: datetime
    updated_at: datetime
    reviewed_at: datetime | None

    @classmethod
    def from_dto(cls, dto: DishOutputDTO) -> DishResponse:
        return cls(**vars(dto))


class CreateRestaurantRequest(CamelModel):
    model_config = ConfigDict(str_strip_whitespace=True)  # merges with CamelModel's

    name: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=2000)
    address: str = Field(min_length=1, max_length=500)
    phone: str = Field(min_length=1, max_length=32)
    opening_hours: str = Field(min_length=1, max_length=255)
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    image_url: str | None = Field(default=None, max_length=2048, pattern=_HTTPS)


class UpdateRestaurantRequest(CamelModel):
    """Partial: only sent fields apply (controller uses ``exclude_unset``). ``description`` and
    ``imageUrl`` may be cleared with ``null``; the rest may not."""

    model_config = ConfigDict(str_strip_whitespace=True)  # merges with CamelModel's

    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=2000)
    address: str | None = Field(default=None, min_length=1, max_length=500)
    phone: str | None = Field(default=None, min_length=1, max_length=32)
    opening_hours: str | None = Field(default=None, min_length=1, max_length=255)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    image_url: str | None = Field(default=None, max_length=2048, pattern=_HTTPS)

    @field_validator("name", "address", "phone", "opening_hours", "latitude", "longitude")
    @classmethod
    def reject_null_required(cls, value):
        return _not_null(value)


class CreateDishRequest(CamelModel):
    model_config = ConfigDict(str_strip_whitespace=True)  # merges with CamelModel's

    name: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=2000)
    image_url: str | None = Field(default=None, max_length=2048, pattern=_HTTPS)
    price: Decimal = Field(ge=0, max_digits=12, decimal_places=0)
    serving_g: int = Field(gt=0, le=10_000)
    kcal: int = Field(ge=0, le=20_000)
    protein_g: float = Field(ge=0, le=2_000)
    carbs_g: float = Field(ge=0, le=2_000)
    fat_g: float = Field(ge=0, le=2_000)
    fiber_g: float | None = Field(default=None, ge=0, le=2_000)


class UpdateDishRequest(CamelModel):
    model_config = ConfigDict(str_strip_whitespace=True)  # merges with CamelModel's

    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=2000)
    image_url: str | None = Field(default=None, max_length=2048, pattern=_HTTPS)
    price: Decimal | None = Field(default=None, ge=0, max_digits=12, decimal_places=0)
    serving_g: int | None = Field(default=None, gt=0, le=10_000)
    kcal: int | None = Field(default=None, ge=0, le=20_000)
    protein_g: float | None = Field(default=None, ge=0, le=2_000)
    carbs_g: float | None = Field(default=None, ge=0, le=2_000)
    fat_g: float | None = Field(default=None, ge=0, le=2_000)
    fiber_g: float | None = Field(default=None, ge=0, le=2_000)  # null clears it (not tracked)

    @field_validator("name", "price", "serving_g", "kcal", "protein_g", "carbs_g", "fat_g")
    @classmethod
    def reject_null_required(cls, value):
        return _not_null(value)


class ImageUploadResponse(CamelModel):
    url: str  # absolute (Cloudinary secure_url)
