"""User endpoints. HTTP <-> application DTO translation only. No business rules here.

Creation now lives in the auth slice (`POST /auth/sign-up`); what remains here
is lookup by id, and it requires a valid access token. Not part of the
front-end contract (which uses `GET /auth/me` for the caller's own profile) —
kept as an extra.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, status

from src.adapters.schemas.user_schemas import UserResponse
from src.infrastructure.di import GetUserUseCaseDep, get_current_user

router = APIRouter(
    prefix="/users",
    tags=["users"],
    dependencies=[Depends(get_current_user)],  # every route here needs auth
)


@router.get("/{user_id}", response_model=UserResponse, status_code=status.HTTP_200_OK)
async def get_user(user_id: int, use_case: GetUserUseCaseDep) -> UserResponse:
    result = await use_case.execute(user_id)
    return UserResponse.from_dto(result)
