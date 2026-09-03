"""Shared helper: mint an access+refresh pair and record the refresh token.

Used by register, login, and refresh — the one place that knows a token pair is
"an access JWT plus a tracked refresh JWT".
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from src.application.dtos.auth import TokenPairDTO
from src.application.ports.refresh_token_repository import RefreshTokenRepositoryProtocol
from src.application.ports.token_service import TokenServiceProtocol
from src.domain.entities.refresh_token import RefreshToken


async def issue_token_pair(
    user_id: UUID,
    tokens: TokenServiceProtocol,
    refresh_tokens: RefreshTokenRepositoryProtocol,
) -> TokenPairDTO:
    access = tokens.issue_access_token(user_id)
    jti = uuid4()
    refresh = tokens.issue_refresh_token(user_id, jti)
    await refresh_tokens.add(RefreshToken.issue(user_id, jti, refresh.expires_at))

    expires_in = int((access.expires_at - datetime.now(UTC)).total_seconds())
    return TokenPairDTO(
        access_token=access.token,
        refresh_token=refresh.token,
        expires_in=max(expires_in, 0),
    )
