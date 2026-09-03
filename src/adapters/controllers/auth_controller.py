"""Auth endpoints. HTTP <-> application DTO translation only.

`register` and `resend-verification` hand the verification email off to a FastAPI
background task: the response goes out first, delivery happens after, so a slow
or failing mail server never blocks or fails the request.
"""

from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Query, status

from src.adapters.controllers.auth_deps import (
    LoginUseCaseDep,
    LogoutUseCaseDep,
    RefreshUseCaseDep,
    RegisterUseCaseDep,
    ResendVerificationUseCaseDep,
    VerifyEmailUseCaseDep,
)
from src.adapters.schemas.auth_schemas import (
    LoginRequest,
    MessageResponse,
    RefreshRequest,
    RegisterRequest,
    ResendVerificationRequest,
    TokenResponse,
)
from src.adapters.schemas.user_schemas import UserResponse
from src.application.dtos.auth import (
    LoginInputDTO,
    RefreshInputDTO,
    RegisterInputDTO,
    ResendVerificationInputDTO,
)
from src.infrastructure.di import CurrentUserDep, EmailVerificationNotifierDep

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=MessageResponse, status_code=status.HTTP_201_CREATED)
async def register(
    body: RegisterRequest,
    use_case: RegisterUseCaseDep,
    notifier: EmailVerificationNotifierDep,
    background_tasks: BackgroundTasks,
) -> MessageResponse:
    dispatch = await use_case.execute(
        RegisterInputDTO(email=body.email, password=body.password, name=body.name)
    )
    background_tasks.add_task(
        notifier.send_verification, dispatch.email, dispatch.name, dispatch.token
    )
    return MessageResponse(detail="Account created. Check your email to confirm your address.")


@router.get("/verify-email", response_model=MessageResponse)
async def verify_email(
    use_case: VerifyEmailUseCaseDep,
    token: str = Query(min_length=1),
) -> MessageResponse:
    await use_case.execute(token)
    return MessageResponse(detail="Email confirmed. You can now log in.")


@router.post(
    "/resend-verification", response_model=MessageResponse, status_code=status.HTTP_202_ACCEPTED
)
async def resend_verification(
    body: ResendVerificationRequest,
    use_case: ResendVerificationUseCaseDep,
    notifier: EmailVerificationNotifierDep,
    background_tasks: BackgroundTasks,
) -> MessageResponse:
    dispatch = await use_case.execute(ResendVerificationInputDTO(email=body.email))
    if dispatch is not None:
        background_tasks.add_task(
            notifier.send_verification, dispatch.email, dispatch.name, dispatch.token
        )
    return MessageResponse(
        detail="If that address needs confirming, a new link is on its way."
    )


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
