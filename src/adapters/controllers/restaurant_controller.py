"""Owner endpoints under /restaurants. HTTP <-> application DTO translation only.

"/mine" carries no id: one user owns at most one restaurant, so ownership is implied by the token.
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, UploadFile, status

from src.adapters.schemas.restaurant_schemas import (
    CreateDishRequest,
    CreateRestaurantRequest,
    DishResponse,
    ImageUploadResponse,
    RestaurantResponse,
    UpdateDishRequest,
    UpdateRestaurantRequest,
)
from src.application.dtos.restaurant import (
    CreateDishInputDTO,
    CreateRestaurantInputDTO,
    UpdateDishInputDTO,
    UpdateRestaurantInputDTO,
)
from src.domain.exceptions import UnreadableImageException
from src.infrastructure.di import (
    CreateDishUseCaseDep,
    CreateRestaurantUseCaseDep,
    CurrentUserDep,
    DeleteDishUseCaseDep,
    GetMyRestaurantUseCaseDep,
    ListMyDishesUseCaseDep,
    UpdateDishUseCaseDep,
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
    if not (
        data.startswith((b"\xff\xd8\xff", b"\x89PNG"))
        or (data[:4] == b"RIFF" and data[8:12] == b"WEBP")
    ):
        raise UnreadableImageException("file is not a JPEG, PNG or WebP image")
    return ImageUploadResponse(url=await use_case.execute(data, image.content_type))


@router.get("/mine/dishes", response_model=list[DishResponse])
async def list_my_dishes(user: CurrentUserDep, use_case: ListMyDishesUseCaseDep) -> list[DishResponse]:
    return [DishResponse.from_dto(d) for d in await use_case.execute(user.id)]


@router.post("/mine/dishes", response_model=DishResponse, status_code=status.HTTP_201_CREATED)
async def create_dish(
    body: CreateDishRequest, user: CurrentUserDep, use_case: CreateDishUseCaseDep
) -> DishResponse:
    return DishResponse.from_dto(
        await use_case.execute(CreateDishInputDTO(user_id=user.id, **body.model_dump()))
    )


@router.patch("/mine/dishes/{dish_id}", response_model=DishResponse)
async def update_dish(
    dish_id: UUID, body: UpdateDishRequest, user: CurrentUserDep, use_case: UpdateDishUseCaseDep
) -> DishResponse:
    result = await use_case.execute(
        UpdateDishInputDTO(user_id=user.id, dish_id=dish_id, updates=body.model_dump(exclude_unset=True))
    )
    return DishResponse.from_dto(result)


@router.delete("/mine/dishes/{dish_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_dish(dish_id: UUID, user: CurrentUserDep, use_case: DeleteDishUseCaseDep) -> None:
    await use_case.execute(user.id, dish_id)
