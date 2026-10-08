"""Owner endpoints under /restaurants. HTTP <-> application DTO translation only.

"/mine" carries no id: one user owns at most one restaurant, so ownership is implied by the token.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, File, UploadFile, status

from src.adapters.schemas.restaurant_schemas import (
    CreateRestaurantRequest,
    ImageUploadResponse,
    RestaurantResponse,
    UpdateRestaurantRequest,
)
from src.application.dtos.restaurant import CreateRestaurantInputDTO, UpdateRestaurantInputDTO
from src.domain.exceptions import UnreadableImageException
from src.infrastructure.di import (
    CreateRestaurantUseCaseDep,
    CurrentUserDep,
    GetMyRestaurantUseCaseDep,
    UpdateMyRestaurantUseCaseDep,
    UploadRestaurantImageUseCaseDep,
    limit_upload_by_user,
)

router = APIRouter(prefix="/restaurants", tags=["restaurants"])

# Browser-renderable only (no HEIC): these images are shown on the web and in the app.
_ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}
_MAX_IMAGE_BYTES = 5 * 1024 * 1024


@router.post("", response_model=RestaurantResponse, status_code=status.HTTP_201_CREATED)
async def create_restaurant(
    body: CreateRestaurantRequest, user: CurrentUserDep, use_case: CreateRestaurantUseCaseDep
) -> RestaurantResponse:
    result = await use_case.execute(CreateRestaurantInputDTO(user_id=user.id, **body.model_dump()))
    return RestaurantResponse.from_dto(result)


@router.get("/mine", response_model=RestaurantResponse)
async def get_my_restaurant(
    user: CurrentUserDep, use_case: GetMyRestaurantUseCaseDep
) -> RestaurantResponse:
    return RestaurantResponse.from_dto(await use_case.execute(user.id))


@router.patch("/mine", response_model=RestaurantResponse)
async def update_my_restaurant(
    body: UpdateRestaurantRequest, user: CurrentUserDep, use_case: UpdateMyRestaurantUseCaseDep
) -> RestaurantResponse:
    result = await use_case.execute(
        UpdateRestaurantInputDTO(user_id=user.id, updates=body.model_dump(exclude_unset=True))
    )
    return RestaurantResponse.from_dto(result)


@router.post(
    "/mine/images",
    response_model=ImageUploadResponse,
    dependencies=[Depends(limit_upload_by_user)],
)
async def upload_image(
    user: CurrentUserDep,
    use_case: UploadRestaurantImageUseCaseDep,
    image: Annotated[UploadFile, File()],
) -> ImageUploadResponse:
    """Any signed-in user, so the create form can attach a photo before the restaurant exists."""
    if image.content_type not in _ALLOWED_IMAGE_TYPES:
        raise UnreadableImageException(f"unsupported image type: {image.content_type!r}")
    data = await image.read(_MAX_IMAGE_BYTES + 1)
    if len(data) > _MAX_IMAGE_BYTES:
        raise UnreadableImageException("image is larger than 5 MB")
    return ImageUploadResponse(url=await use_case.execute(data, image.content_type))
