"""Shared helper: mint an access+refresh pair, record the refresh token, and
package the result as the ``AuthSessionDTO`` every session-establishing
endpoint (sign-up, sign-in, refresh) returns.
"""

from __future__ import annotations

from uuid import uuid4

from src.application.dtos.auth import AuthSessionDTO
from src.application.dtos.user import UserOutputDTO
from src.application.ports.refresh_token_repository import RefreshTokenRepositoryProtocol
from src.application.ports.token_service import TokenServiceProtocol
from src.domain.entities.refresh_token import RefreshToken
from src.domain.entities.user import User


async def issue_session(
    user: User,
    tokens: TokenServiceProtocol,
    refresh_tokens: RefreshTokenRepositoryProtocol,
) -> AuthSessionDTO:
    assert user.id is not None, "cannot issue a session for an unpersisted user"

    access = tokens.issue_access_token(user.id)
    jti = uuid4()
    refresh = tokens.issue_refresh_token(user.id, jti)
    await refresh_tokens.add(RefreshToken.issue(user.id, jti, refresh.expires_at))

    return AuthSessionDTO(
        access_token=access.token,
        refresh_token=refresh.token,
        access_expires_at=access.expires_at,
        user=UserOutputDTO.from_entity(user),
    )
