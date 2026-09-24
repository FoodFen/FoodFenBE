"""User endpoints. HTTP <-> application DTO translation only. No business rules here.

Creation now lives in the auth slice (`POST /auth/sign-up`); what remains here
is lookup by id, and `PATCH /me` for offline profile-edit sync (contract:
docs/backend-contracts/sync.md in the FoodFenFE repo). Not part of the
front-end contract for lookup-by-id (which uses `GET /auth/me` for the
caller's own profile) — kept as an extra.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, status

from src.adapters.schemas.user_schemas import UpdateUserProfileRequest, UserResponse
from src.application.dtos.update_user_profile import UpdateUserProfileInputDTO
from src.infrastructure.di import (
    CurrentUserDep,
    GetUserUseCaseDep,
    UpdateUserProfileUseCaseDep,
    get_current_user,
)

router = APIRouter(
    prefix="/users",
    tags=["users"],
    dependencies=[Depends(get_current_user)],  # every route here needs auth
)


@router.get("/{user_id}", response_model=UserResponse, status_code=status.HTTP_200_OK)
async def get_user(user_id: int, use_case: GetUserUseCaseDep) -> UserResponse:
    result = await use_case.execute(user_id)
    return UserResponse.from_dto(result)


@router.patch("/me", response_model=UserResponse)
async def update_my_profile(
    body: UpdateUserProfileRequest,
    user: CurrentUserDep,
    use_case: UpdateUserProfileUseCaseDep,
) -> UserResponse:
    input_dto = UpdateUserProfileInputDTO(
        user_id=user.id, updates=body.model_dump(exclude_unset=True)
    )
    result = await use_case.execute(input_dto)
    return UserResponse.from_dto(result)
