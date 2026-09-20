"""Repository providers — one factory + one ``Annotated`` alias per table.

Grows by ~4 lines per entity. Use-case providers in ``use_cases.py`` compose
these; nothing outside the ``di/`` package builds a repository directly.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends

from src.application.ports.chat_message_repository import ChatMessageRepositoryProtocol
from src.application.ports.refresh_token_repository import RefreshTokenRepositoryProtocol
from src.application.ports.social_identity_repository import SocialIdentityRepositoryProtocol
from src.application.ports.user_repository import UserRepositoryProtocol
from src.infrastructure.db.repositories.chat_message_repository import (
    SQLAlchemyChatMessageRepository,
)
from src.infrastructure.db.repositories.refresh_token_repository import (
    SQLAlchemyRefreshTokenRepository,
)
from src.infrastructure.db.repositories.social_identity_repository import (
    SQLAlchemySocialIdentityRepository,
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


def get_social_identity_repository(session: SessionDep) -> SocialIdentityRepositoryProtocol:
    return SQLAlchemySocialIdentityRepository(session)


SocialIdentityRepositoryDep = Annotated[
    SocialIdentityRepositoryProtocol, Depends(get_social_identity_repository)
]


def get_chat_message_repository(session: SessionDep) -> ChatMessageRepositoryProtocol:
    return SQLAlchemyChatMessageRepository(session)


ChatMessageRepositoryDep = Annotated[
    ChatMessageRepositoryProtocol, Depends(get_chat_message_repository)
]
