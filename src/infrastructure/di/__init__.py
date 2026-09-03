"""Shared composition-root dependencies.

Slice-specific use-case providers live next to their controller
(`src/adapters/controllers/<slice>_deps.py`); only cross-slice primitives are
re-exported here.
"""

from src.infrastructure.di.database import SessionDep
from src.infrastructure.di.repositories import (
    RefreshTokenRepositoryDep,
    UserRepositoryDep,
    get_refresh_token_repository,
    get_user_repository,
)
from src.infrastructure.di.security import (
    CurrentUserDep,
    PasswordHasherDep,
    TokenServiceDep,
    get_current_user,
    get_password_hasher,
    get_token_service,
)

__all__ = [
    "CurrentUserDep",
    "PasswordHasherDep",
    "RefreshTokenRepositoryDep",
    "SessionDep",
    "TokenServiceDep",
    "UserRepositoryDep",
    "get_current_user",
    "get_password_hasher",
    "get_refresh_token_repository",
    "get_token_service",
    "get_user_repository",
]
