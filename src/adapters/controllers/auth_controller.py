"""Auth endpoints. HTTP <-> application DTO translation only."""

from __future__ import annotations

from fastapi import APIRouter, status

from src.adapters.controllers.auth_deps import (
    LoginUseCaseDep,
    LogoutUseCaseDep,
    RefreshUseCaseDep,
    RegisterUseCaseDep,
)
from src.adapters.schemas.auth_schemas import (
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    TokenResponse,
)
from src.adapters.schemas.user_schemas import UserResponse
from src.application.dtos.auth import LoginInputDTO, RefreshInputDTO, RegisterInputDTO
from src.infrastructure.di import CurrentUserDep

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(body: RegisterRequest, use_case: RegisterUseCaseDep) -> TokenResponse:
    result = await use_case.execute(
        RegisterInputDTO(email=body.email, password=body.password, name=body.name)
    )
    return TokenResponse.model_validate(result)


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, use_case: LoginUseCaseDep) -> TokenResponse:
    result = await use_case.execute(LoginInputDTO(email=body.email, password=body.password))
    return TokenResponse.model_validate(result)


@router.post("/refresh", response_model=TokenResponse)
async def refresh(body: RefreshRequest, use_case: RefreshUseCaseDep) -> TokenResponse:
    result = await use_case.execute(RefreshInputDTO(refresh_token=body.refresh_token))
    return TokenResponse.model_validate(result)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(body: RefreshRequest, use_case: LogoutUseCaseDep) -> None:
    await use_case.execute(RefreshInputDTO(refresh_token=body.refresh_token))


@router.get("/me", response_model=UserResponse)
async def me(current_user: CurrentUserDep) -> UserResponse:
    return UserResponse.model_validate(current_user)
