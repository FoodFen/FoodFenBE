"""Composition root: every FastAPI provider and ``Annotated`` dependency alias.

One package, one place to look: ``database.py`` (session), ``repositories.py``
(one factory + alias per table), ``security.py`` (hasher, token service,
``get_current_user``), ``notifications.py`` (outbound email), ``use_cases.py``
(every ``get_*_use_case`` provider). This module re-exports all of it so
callers just do ``from src.infrastructure.di import XyzDep``.
"""

from src.infrastructure.di.database import SessionDep
from src.infrastructure.di.notifications import (
    EmailVerificationNotifierDep,
    get_email_verification_notifier,
)
from src.infrastructure.di.repositories import (
    RefreshTokenRepositoryDep,
    SocialIdentityRepositoryDep,
    UserRepositoryDep,
    get_refresh_token_repository,
    get_social_identity_repository,
    get_user_repository,
)
from src.infrastructure.di.security import (
    CurrentUserDep,
    PasswordHasherDep,
    SocialIdentityVerifierDep,
    TokenServiceDep,
    get_current_user,
    get_password_hasher,
    get_social_identity_verifier,
    get_token_service,
)
from src.infrastructure.di.use_cases import (
    GetUserUseCaseDep,
    LoginUseCaseDep,
    LogoutUseCaseDep,
    RefreshUseCaseDep,
    RegisterUseCaseDep,
    RequestPasswordResetUseCaseDep,
    ResendVerificationUseCaseDep,
    ResetPasswordUseCaseDep,
    SocialSignInUseCaseDep,
    VerifyEmailUseCaseDep,
    get_get_user_use_case,
    get_login_use_case,
    get_logout_use_case,
    get_refresh_use_case,
    get_register_use_case,
    get_request_password_reset_use_case,
    get_resend_verification_use_case,
    get_reset_password_use_case,
    get_social_sign_in_use_case,
    get_verify_email_use_case,
)

__all__ = [
    "CurrentUserDep",
    "EmailVerificationNotifierDep",
    "GetUserUseCaseDep",
    "LoginUseCaseDep",
    "LogoutUseCaseDep",
    "PasswordHasherDep",
    "RefreshTokenRepositoryDep",
    "RefreshUseCaseDep",
    "RegisterUseCaseDep",
    "RequestPasswordResetUseCaseDep",
    "ResendVerificationUseCaseDep",
    "ResetPasswordUseCaseDep",
    "SessionDep",
    "SocialIdentityRepositoryDep",
    "SocialIdentityVerifierDep",
    "SocialSignInUseCaseDep",
    "TokenServiceDep",
    "UserRepositoryDep",
    "VerifyEmailUseCaseDep",
    "get_current_user",
    "get_email_verification_notifier",
    "get_get_user_use_case",
    "get_login_use_case",
    "get_logout_use_case",
    "get_password_hasher",
    "get_refresh_token_repository",
    "get_refresh_use_case",
    "get_register_use_case",
    "get_request_password_reset_use_case",
    "get_resend_verification_use_case",
    "get_reset_password_use_case",
    "get_social_identity_repository",
    "get_social_identity_verifier",
    "get_social_sign_in_use_case",
    "get_token_service",
    "get_user_repository",
    "get_verify_email_use_case",
]
