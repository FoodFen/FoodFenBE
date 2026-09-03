"""User endpoints. HTTP <-> application DTO translation only. No business rules here.

Creation now lives in the auth slice (`POST /auth/register`); what remains here is
lookup, and it requires a valid access token.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, status

from src.adapters.controllers.user_deps import GetUserUseCaseDep
from src.adapters.schemas.user_schemas import UserResponse
from src.infrastructure.di import get_current_user

router = APIRouter(
    prefix="/users",
    tags=["users"],
    dependencies=[Depends(get_current_user)],  # every route here needs auth
)


@router.get("/{user_id}", response_model=UserResponse, status_code=status.HTTP_200_OK)
async def get_user(user_id: UUID, use_case: GetUserUseCaseDep) -> UserResponse:
    result = await use_case.execute(user_id)
    return UserResponse.model_validate(result)
