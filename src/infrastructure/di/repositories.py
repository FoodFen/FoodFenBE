"""Repository providers — one factory + one ``Annotated`` alias per table.

Grows by ~4 lines per entity. Use cases receive these; slice-local ``*_deps``
modules compose them into use-case providers.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends

from src.application.ports.refresh_token_repository import RefreshTokenRepositoryProtocol
from src.application.ports.user_repository import UserRepositoryProtocol
from src.infrastructure.db.repositories.refresh_token_repository import (
    SQLAlchemyRefreshTokenRepository,
)
from src.infrastructure.db.repositories.user_repository import SQLAlchemyUserRepository
from src.infrastructure.di.database import SessionDep


def get_user_repository(session: SessionDep) -> UserRepositoryProtocol:
    return SQLAlchemyUserRepository(session)


UserRepositoryDep = Annotated[UserRepositoryProtocol, Depends(get_user_repository)]


def get_refresh_token_repository(session: SessionDep) -> RefreshTokenRepositoryProtocol:
    return SQLAlchemyRefreshTokenRepository(session)


RefreshTokenRepositoryDep = Annotated[
    RefreshTokenRepositoryProtocol, Depends(get_refresh_token_repository)
]
