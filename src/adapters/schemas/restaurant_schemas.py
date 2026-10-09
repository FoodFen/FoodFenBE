"""HTTP wire models for owner restaurant / dish endpoints (camelCase)."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Annotated
from urllib.parse import urlparse
from uuid import UUID

from pydantic import AfterValidator, ConfigDict, Field, field_validator

from src.adapters.schemas.base import CamelModel, MoneyField
from src.application.dtos.restaurant import (
    DishOutputDTO,
    PublicDishDTO,
    PublicDishListDTO,
    PublicRestaurantDTO,
    PublicRestaurantSummaryDTO,
    RestaurantOutputDTO,
)
from src.domain.enums import ModerationStatus
from src.infrastructure.config import settings  # a leaf module: just the cloud name, no wiring


def _cloudinary_only(url: str) -> str:
    """Only images uploaded through this app: ``POST /restaurants/mine/images`` hands out these URLs.
    Fails closed: no ``CLOUDINARY_URL`` configured means no ``imageUrl`` is accepted (``null`` still is)."""
    cloud = urlparse(settings.cloudinary_url).hostname  # same parse as CloudinaryImageStorage
    if not cloud or not url.startswith(f"https://res.cloudinary.com/{cloud}/image/upload/"):
        raise ValueError("must be an image uploaded through POST /restaurants/mine/images")
    return url


CloudinaryImageUrl = Annotated[str, AfterValidator(_cloudinary_only)]


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


class PublicDishResponse(CamelModel):
    id: UUID
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

    @classmethod
    def from_dto(cls, dto: PublicDishDTO) -> PublicDishResponse:
        return cls(**vars(dto))


class PublicRestaurantSummaryResponse(CamelModel):
    id: UUID
    name: str
    address: str
    latitude: float
    longitude: float

    @classmethod
    def from_dto(cls, dto: PublicRestaurantSummaryDTO) -> PublicRestaurantSummaryResponse:
        return cls(**vars(dto))


class PublicFitDishResponse(PublicDishResponse):
    fits: bool
    restaurant: PublicRestaurantSummaryResponse


class PublicDishListResponse(CamelModel):
    remaining_kcal: int | None
    dishes: list[PublicFitDishResponse]

    @classmethod
    def from_dto(cls, dto: PublicDishListDTO) -> PublicDishListResponse:
        return cls(
            remaining_kcal=dto.remaining_kcal,
            dishes=[
                PublicFitDishResponse(
                    **vars(d.dish), fits=d.fits, restaurant=PublicRestaurantSummaryResponse.from_dto(d.restaurant)
                )
                for d in dto.dishes
            ],
        )


class PublicRestaurantResponse(CamelModel):
    id: UUID
    name: str
    description: str | None
    address: str
    phone: str
    opening_hours: str
    latitude: float
    longitude: float
    image_url: str | None
    dishes: list[PublicDishResponse]

    @classmethod
    def from_dto(cls, dto: PublicRestaurantDTO) -> PublicRestaurantResponse:
        return cls(
            **{k: v for k, v in vars(dto).items() if k != "dishes"},
            dishes=[PublicDishResponse.from_dto(d) for d in dto.dishes],
        )


class CreateRestaurantRequest(CamelModel):
    model_config = ConfigDict(str_strip_whitespace=True)  # merges with CamelModel's

    name: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=2000)
    address: str = Field(min_length=1, max_length=500)
    phone: str = Field(min_length=1, max_length=32)
    opening_hours: str = Field(min_length=1, max_length=255)
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    image_url: CloudinaryImageUrl | None = Field(default=None, max_length=2048)


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
    image_url: CloudinaryImageUrl | None = Field(default=None, max_length=2048)

    @field_validator("name", "address", "phone", "opening_hours", "latitude", "longitude")
    @classmethod
    def reject_null_required(cls, value):
        return _not_null(value)


class CreateDishRequest(CamelModel):
    model_config = ConfigDict(str_strip_whitespace=True)  # merges with CamelModel's

    name: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=2000)
    image_url: CloudinaryImageUrl | None = Field(default=None, max_length=2048)
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
    image_url: CloudinaryImageUrl | None = Field(default=None, max_length=2048)
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
