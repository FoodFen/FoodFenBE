"""Use-case providers for the auth slice — composed from the shared di primitives.

Kept next to ``auth_controller`` because that is their only caller.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends

from src.application.use_cases.login import LoginUseCase
from src.application.use_cases.logout import LogoutUseCase
from src.application.use_cases.refresh_token import RefreshTokenUseCase
from src.application.use_cases.register_user import RegisterUserUseCase
from src.application.use_cases.resend_verification import ResendVerificationUseCase
from src.application.use_cases.verify_email import VerifyEmailUseCase
from src.infrastructure.di import (
    PasswordHasherDep,
    RefreshTokenRepositoryDep,
    TokenServiceDep,
    UserRepositoryDep,
)


def get_register_use_case(
    users: UserRepositoryDep, hasher: PasswordHasherDep, tokens: TokenServiceDep
) -> RegisterUserUseCase:
    return RegisterUserUseCase(users=users, hasher=hasher, tokens=tokens)


def get_login_use_case(
    users: UserRepositoryDep,
    refresh_tokens: RefreshTokenRepositoryDep,
    hasher: PasswordHasherDep,
    tokens: TokenServiceDep,
) -> LoginUseCase:
    return LoginUseCase(
        users=users, refresh_tokens=refresh_tokens, hasher=hasher, tokens=tokens
    )


def get_refresh_use_case(
    refresh_tokens: RefreshTokenRepositoryDep, tokens: TokenServiceDep
) -> RefreshTokenUseCase:
    return RefreshTokenUseCase(refresh_tokens=refresh_tokens, tokens=tokens)


def get_logout_use_case(
    refresh_tokens: RefreshTokenRepositoryDep, tokens: TokenServiceDep
) -> LogoutUseCase:
    return LogoutUseCase(refresh_tokens=refresh_tokens, tokens=tokens)


def get_verify_email_use_case(
    users: UserRepositoryDep, tokens: TokenServiceDep
) -> VerifyEmailUseCase:
    return VerifyEmailUseCase(users=users, tokens=tokens)


def get_resend_verification_use_case(
    users: UserRepositoryDep, tokens: TokenServiceDep
) -> ResendVerificationUseCase:
    return ResendVerificationUseCase(users=users, tokens=tokens)


RegisterUseCaseDep = Annotated[RegisterUserUseCase, Depends(get_register_use_case)]
LoginUseCaseDep = Annotated[LoginUseCase, Depends(get_login_use_case)]
RefreshUseCaseDep = Annotated[RefreshTokenUseCase, Depends(get_refresh_use_case)]
LogoutUseCaseDep = Annotated[LogoutUseCase, Depends(get_logout_use_case)]
VerifyEmailUseCaseDep = Annotated[VerifyEmailUseCase, Depends(get_verify_email_use_case)]
ResendVerificationUseCaseDep = Annotated[
    ResendVerificationUseCase, Depends(get_resend_verification_use_case)
]
