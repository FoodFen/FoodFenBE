"""Auth endpoints. HTTP <-> application DTO translation only.

Endpoint names and shapes follow the front-end API contract (see
docs/authentication.md): sign-up / sign-in / refresh / sign-out /
password-reset / social, camelCase JSON, ``AuthSession``/``User`` response
shapes. ``verify-email``, ``resend-verification``, and ``reset-password`` are
extra — not required by that contract, kept as optional/bonus functionality.

Email-sending endpoints hand the message off to a FastAPI background task: the
response goes out first, delivery happens after, so a slow or failing mail
server never blocks or fails the request.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, Query, status
from fastapi.security import OAuth2PasswordRequestForm

from src.adapters.schemas.auth_schemas import (
    AuthSessionResponse,
    MessageResponse,
    PasswordResetRequest,
    RefreshRequest,
    ResendVerificationRequest,
    ResetPasswordRequest,
    SignInRequest,
    SignOutRequest,
    SignUpRequest,
    SocialSignInRequest,
    SwaggerTokenResponse,
)
from src.adapters.schemas.user_schemas import UserResponse
from src.application.dtos.auth import (
    LoginInputDTO,
    RefreshInputDTO,
    RegisterInputDTO,
    RequestPasswordResetInputDTO,
    ResendVerificationInputDTO,
    ResetPasswordInputDTO,
    SocialSignInInputDTO,
)
from src.application.dtos.user import UserOutputDTO
from src.infrastructure.di import (
    CurrentUserDep,
    EmailVerificationNotifierDep,
    LoginUseCaseDep,
    LogoutUseCaseDep,
    RefreshUseCaseDep,
    RegisterUseCaseDep,
    RequestPasswordResetUseCaseDep,
    ResendVerificationUseCaseDep,
    ResetPasswordUseCaseDep,
    SocialSignInUseCaseDep,
    VerifyEmailUseCaseDep,
    get_current_user,
)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/sign-up", response_model=AuthSessionResponse)
async def sign_up(
    body: SignUpRequest,
    use_case: RegisterUseCaseDep,
    notifier: EmailVerificationNotifierDep,
    background_tasks: BackgroundTasks,
) -> AuthSessionResponse:
    result = await use_case.execute(
        RegisterInputDTO(email=body.email, password=body.password, name=body.display_name)
    )
    background_tasks.add_task(
        notifier.send_verification,
        result.session.user.email,
        result.session.user.name,
        result.verification_token,
    )
    return AuthSessionResponse.from_dto(result.session)


@router.post("/sign-in", response_model=AuthSessionResponse)
async def sign_in(body: SignInRequest, use_case: LoginUseCaseDep) -> AuthSessionResponse:
    session = await use_case.execute(LoginInputDTO(email=body.email, password=body.password))
    return AuthSessionResponse.from_dto(session)


@router.post("/refresh", response_model=AuthSessionResponse)
async def refresh(body: RefreshRequest, use_case: RefreshUseCaseDep) -> AuthSessionResponse:
    session = await use_case.execute(RefreshInputDTO(refresh_token=body.refresh_token))
    return AuthSessionResponse.from_dto(session)


@router.post("/social", response_model=AuthSessionResponse)
async def social_sign_in(
    body: SocialSignInRequest, use_case: SocialSignInUseCaseDep
) -> AuthSessionResponse:
    session = await use_case.execute(
        SocialSignInInputDTO(
            provider=body.provider,
            id_token=body.id_token,
            full_name=body.full_name,
            email=body.email,
        )
    )
    return AuthSessionResponse.from_dto(session)


@router.post(
    "/sign-out", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(get_current_user)]
)
async def sign_out(body: SignOutRequest, use_case: LogoutUseCaseDep) -> None:
    await use_case.execute(RefreshInputDTO(refresh_token=body.refresh_token))


@router.post(
    "/password-reset", response_model=MessageResponse, status_code=status.HTTP_202_ACCEPTED
)
async def password_reset(
    body: PasswordResetRequest,
    use_case: RequestPasswordResetUseCaseDep,
    notifier: EmailVerificationNotifierDep,
    background_tasks: BackgroundTasks,
) -> MessageResponse:
    dispatch = await use_case.execute(RequestPasswordResetInputDTO(email=body.email))
    if dispatch is not None:
        background_tasks.add_task(
            notifier.send_password_reset, dispatch.email, dispatch.name, dispatch.token
        )
    # Always the same response: this endpoint must not reveal whether the email is registered.
    return MessageResponse(message="If that address has an account, a reset link is on its way.")


@router.get("/me", response_model=UserResponse)
async def me(current_user: CurrentUserDep) -> UserResponse:
    return UserResponse.from_dto(UserOutputDTO.from_entity(current_user))


@router.get("/verify-email", response_model=MessageResponse)
async def verify_email(
    use_case: VerifyEmailUseCaseDep,
    token: str = Query(min_length=1),
) -> MessageResponse:
    await use_case.execute(token)
    return MessageResponse(message="Email confirmed.")


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
        message="If that address needs confirming, a new link is on its way."
    )


@router.post("/reset-password", response_model=MessageResponse)
async def reset_password(
    body: ResetPasswordRequest, use_case: ResetPasswordUseCaseDep
) -> MessageResponse:
    await use_case.execute(
        ResetPasswordInputDTO(token=body.token, new_password=body.new_password)
    )
    return MessageResponse(message="Password updated. You can now sign in.")


@router.post("/token", response_model=SwaggerTokenResponse, include_in_schema=False)
async def sign_in_for_swagger(
    form: Annotated[OAuth2PasswordRequestForm, Depends()],
    use_case: LoginUseCaseDep,
) -> SwaggerTokenResponse:
    """Same sign-in, OAuth2-form-shaped. Exists only as the target of Swagger's
    "Authorize" dialog (`tokenUrl="auth/token"` in `di/security.py`) — real
    clients use the JSON `/auth/sign-in` above. Hidden from the schema so it
    doesn't show up as a second, redundant login endpoint.
    """
    session = await use_case.execute(LoginInputDTO(email=form.username, password=form.password))
    return SwaggerTokenResponse(access_token=session.access_token)
