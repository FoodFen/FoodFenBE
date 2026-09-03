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
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from src.application.ports.password_hasher import PasswordHasherProtocol
from src.application.ports.token_service import TokenServiceProtocol
from src.domain.entities.user import User
from src.domain.exceptions import InvalidTokenException
from src.infrastructure.config import settings
from src.infrastructure.di.repositories import UserRepositoryDep
from src.infrastructure.security.jwt_service import JwtTokenService
from src.infrastructure.security.password_hasher import BcryptPasswordHasher


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
    )


def get_token_service() -> TokenServiceProtocol:
    return _token_service()


TokenServiceDep = Annotated[TokenServiceProtocol, Depends(get_token_service)]

_bearer = HTTPBearer(auto_error=False, description="Access token from POST /auth/login")


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
    tokens: TokenServiceDep,
    users: UserRepositoryDep,
) -> User:
    if credentials is None:
        raise InvalidTokenException("missing bearer token")
    user_id = tokens.read_access_token(credentials.credentials)
    user = await users.get_by_id(user_id)
    if user is None or not user.is_active:
        raise InvalidTokenException("user no longer exists or is inactive")
    return user


CurrentUserDep = Annotated[User, Depends(get_current_user)]
