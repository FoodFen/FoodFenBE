"""Composition root: wire concrete adapters into use cases for FastAPI ``Depends``."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.application.ports.user_repository import UserRepositoryProtocol
from src.application.use_cases.create_user import CreateUserUseCase
from src.application.use_cases.get_user import GetUserUseCase
from src.infrastructure.db.repositories.user_repository import SQLAlchemyUserRepository
from src.infrastructure.db.session import get_db_session

SessionDep = Annotated[AsyncSession, Depends(get_db_session)]


def get_user_repository(session: SessionDep) -> UserRepositoryProtocol:
    return SQLAlchemyUserRepository(session)


UserRepositoryDep = Annotated[UserRepositoryProtocol, Depends(get_user_repository)]


def get_create_user_use_case(repo: UserRepositoryDep) -> CreateUserUseCase:
    return CreateUserUseCase(users=repo)


def get_get_user_use_case(repo: UserRepositoryDep) -> GetUserUseCase:
    return GetUserUseCase(users=repo)
