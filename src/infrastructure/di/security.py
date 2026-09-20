"""Auth primitives: password hasher, token service, and the current-user guard.

The hasher and token service are process-wide singletons — they only hold config
(bcrypt cost, JWT secret/TTLs) and are otherwise stateless, so there is no reason
to rebuild them per request.
"""

from __future__ import annotations

from datetime import timedelta
from functools import lru_cache
from typing import Annotated

from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer

from src.application.ports.password_hasher import PasswordHasherProtocol
from src.application.ports.social_identity_verifier import SocialIdentityVerifierProtocol
from src.application.ports.token_service import TokenServiceProtocol
from src.domain.entities.user import User
from src.domain.exceptions import InvalidTokenException
from src.infrastructure.config import settings
from src.infrastructure.di.repositories import UserRepositoryDep
from src.infrastructure.security.jwt_service import JwtTokenService
from src.infrastructure.security.password_hasher import BcryptPasswordHasher
from src.infrastructure.security.social_identity_verifier import JwtSocialIdentityVerifier


def _split_ids(raw: str) -> frozenset[str]:
    return frozenset(part.strip() for part in raw.split(",") if part.strip())


@lru_cache
def _password_hasher() -> BcryptPasswordHasher:
    return BcryptPasswordHasher()


def get_password_hasher() -> PasswordHasherProtocol:
    return _password_hasher()


PasswordHasherDep = Annotated[PasswordHasherProtocol, Depends(get_password_hasher)]


@lru_cache
def _token_service() -> JwtTokenService:
    return JwtTokenService(
        secret=settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
        access_ttl=timedelta(minutes=settings.access_token_expire_minutes),
        refresh_ttl=timedelta(days=settings.refresh_token_expire_days),
        verification_ttl=timedelta(hours=settings.verification_token_expire_hours),
        password_reset_ttl=timedelta(minutes=settings.password_reset_token_expire_minutes),
    )


def get_token_service() -> TokenServiceProtocol:
    return _token_service()


TokenServiceDep = Annotated[TokenServiceProtocol, Depends(get_token_service)]


@lru_cache
def _social_identity_verifier() -> JwtSocialIdentityVerifier:
    return JwtSocialIdentityVerifier(
        google_client_ids=_split_ids(settings.google_oauth_client_ids),
        apple_client_ids=_split_ids(settings.apple_client_ids),
    )


def get_social_identity_verifier() -> SocialIdentityVerifierProtocol:
    return _social_identity_verifier()


SocialIdentityVerifierDep = Annotated[
    SocialIdentityVerifierProtocol, Depends(get_social_identity_verifier)
]

# Over plain HTTPBearer so Swagger's Authorize button gets a login form
# (POSTs to tokenUrl) instead of a bare token field. auto_error=False: we
# raise our own exception below rather than FastAPI's default HTTPException.
_oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/token", auto_error=False)


async def get_current_user(
    token: Annotated[str | None, Depends(_oauth2_scheme)],
    tokens: TokenServiceDep,
    users: UserRepositoryDep,
) -> User:
    if token is None:
        raise InvalidTokenException("missing bearer token")
    user_id = tokens.read_access_token(token)
    user = await users.get_by_id(user_id)
    if user is None or not user.is_active:
        raise InvalidTokenException("user no longer exists or is inactive")
    return user


CurrentUserDep = Annotated[User, Depends(get_current_user)]
