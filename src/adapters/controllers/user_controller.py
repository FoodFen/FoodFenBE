"""HTTP <-> application DTO translation only. No business rules here.

Domain exceptions raised by the use cases are turned into HTTP status codes by
the handlers registered in ``src.main`` — the controller does not catch them.
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status

from src.adapters.schemas.user_schemas import CreateUserRequest, UserResponse
from src.application.dtos.user import CreateUserInputDTO
from src.application.use_cases.create_user import CreateUserUseCase
from src.application.use_cases.get_user import GetUserUseCase
from src.infrastructure.di import get_create_user_use_case, get_get_user_use_case

router = APIRouter(prefix="/users", tags=["users"])


@router.post("", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    body: CreateUserRequest,
    use_case: Annotated[CreateUserUseCase, Depends(get_create_user_use_case)],
) -> UserResponse:
    result = await use_case.execute(
        CreateUserInputDTO(email=body.email, name=body.name)
    )
    return UserResponse.model_validate(result)


@router.get("/{user_id}", response_model=UserResponse, status_code=status.HTTP_200_OK)
async def get_user(
    user_id: UUID,
    use_case: Annotated[GetUserUseCase, Depends(get_get_user_use_case)],
) -> UserResponse:
    result = await use_case.execute(user_id)
    return UserResponse.model_validate(result)
