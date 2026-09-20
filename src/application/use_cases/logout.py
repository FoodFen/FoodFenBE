"""Revoke a refresh token. Idempotent — an already-dead token is a no-op success."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from src.application.dtos.auth import RefreshInputDTO
from src.application.ports.refresh_token_repository import RefreshTokenRepositoryProtocol
from src.application.ports.token_service import TokenServiceProtocol
from src.domain.exceptions import InvalidTokenException


@dataclass
class LogoutUseCase:
    refresh_tokens: RefreshTokenRepositoryProtocol
    tokens: TokenServiceProtocol

    async def execute(self, data: RefreshInputDTO) -> None:
        try:
            claims = self.tokens.read_refresh_token(data.refresh_token)
        except InvalidTokenException:
            return  # malformed/expired: nothing to revoke

        stored = await self.refresh_tokens.get_by_jti(claims.jti)
        if stored is not None and stored.revoked_at is None:
            stored.revoke(datetime.now(UTC))
            await self.refresh_tokens.revoke(stored)
