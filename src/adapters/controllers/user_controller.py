"""User endpoints. HTTP <-> application DTO translation only. No business rules here.

Creation lives in the auth slice (`POST /auth/sign-up`), the caller's own
profile is `GET /auth/me`; what's here is `PATCH /me` for offline profile-edit
sync (contract: docs/backend-contracts/sync.md in the FoodFenFE repo).
There is deliberately no lookup-by-id: ids are sequential, so it would leak
every user's profile.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from src.adapters.schemas.user_schemas import UpdateUserProfileRequest, UserResponse
from src.application.dtos.update_user_profile import UpdateUserProfileInputDTO
from src.infrastructure.di import (
    CurrentUserDep,
    UpdateUserProfileUseCaseDep,
    get_current_user,
)

router = APIRouter(
    prefix="/users",
    tags=["users"],
    dependencies=[Depends(get_current_user)],  # every route here needs auth
)


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
