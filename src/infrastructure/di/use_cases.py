"""Use-case providers for every slice, in one place.

One file to open when wiring or reviewing a use case, at the cost of it
growing with the app. Split it again (e.g. by slice) if it gets unwieldy.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends

from src.application.use_cases.get_user import GetUserUseCase
from src.application.use_cases.login import LoginUseCase
from src.application.use_cases.logout import LogoutUseCase
from src.application.use_cases.refresh_token import RefreshTokenUseCase
from src.application.use_cases.register_user import RegisterUserUseCase
from src.application.use_cases.request_password_reset import RequestPasswordResetUseCase
from src.application.use_cases.resend_verification import ResendVerificationUseCase
from src.application.use_cases.reset_password import ResetPasswordUseCase
from src.application.use_cases.social_sign_in import SocialSignInUseCase
from src.application.use_cases.verify_email import VerifyEmailUseCase
from src.infrastructure.di.repositories import (
    RefreshTokenRepositoryDep,
    SocialIdentityRepositoryDep,
    UserRepositoryDep,
)
from src.infrastructure.di.security import (
    PasswordHasherDep,
    SocialIdentityVerifierDep,
    TokenServiceDep,
)


def get_get_user_use_case(repo: UserRepositoryDep) -> GetUserUseCase:
    return GetUserUseCase(users=repo)


GetUserUseCaseDep = Annotated[GetUserUseCase, Depends(get_get_user_use_case)]


def get_register_use_case(
    users: UserRepositoryDep,
    refresh_tokens: RefreshTokenRepositoryDep,
    hasher: PasswordHasherDep,
    tokens: TokenServiceDep,
) -> RegisterUserUseCase:
    return RegisterUserUseCase(
        users=users, refresh_tokens=refresh_tokens, hasher=hasher, tokens=tokens
    )


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
    users: UserRepositoryDep,
    refresh_tokens: RefreshTokenRepositoryDep,
    tokens: TokenServiceDep,
) -> RefreshTokenUseCase:
    return RefreshTokenUseCase(users=users, refresh_tokens=refresh_tokens, tokens=tokens)


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


def get_request_password_reset_use_case(
    users: UserRepositoryDep, tokens: TokenServiceDep
) -> RequestPasswordResetUseCase:
    return RequestPasswordResetUseCase(users=users, tokens=tokens)


def get_reset_password_use_case(
    users: UserRepositoryDep, hasher: PasswordHasherDep, tokens: TokenServiceDep
) -> ResetPasswordUseCase:
    return ResetPasswordUseCase(users=users, hasher=hasher, tokens=tokens)


def get_social_sign_in_use_case(
    users: UserRepositoryDep,
    social_identities: SocialIdentityRepositoryDep,
    refresh_tokens: RefreshTokenRepositoryDep,
    verifier: SocialIdentityVerifierDep,
    tokens: TokenServiceDep,
) -> SocialSignInUseCase:
    return SocialSignInUseCase(
        users=users,
        social_identities=social_identities,
        refresh_tokens=refresh_tokens,
        verifier=verifier,
        tokens=tokens,
    )


RegisterUseCaseDep = Annotated[RegisterUserUseCase, Depends(get_register_use_case)]
LoginUseCaseDep = Annotated[LoginUseCase, Depends(get_login_use_case)]
RefreshUseCaseDep = Annotated[RefreshTokenUseCase, Depends(get_refresh_use_case)]
LogoutUseCaseDep = Annotated[LogoutUseCase, Depends(get_logout_use_case)]
VerifyEmailUseCaseDep = Annotated[VerifyEmailUseCase, Depends(get_verify_email_use_case)]
ResendVerificationUseCaseDep = Annotated[
    ResendVerificationUseCase, Depends(get_resend_verification_use_case)
]
RequestPasswordResetUseCaseDep = Annotated[
    RequestPasswordResetUseCase, Depends(get_request_password_reset_use_case)
]
ResetPasswordUseCaseDep = Annotated[ResetPasswordUseCase, Depends(get_reset_password_use_case)]
SocialSignInUseCaseDep = Annotated[SocialSignInUseCase, Depends(get_social_sign_in_use_case)]
