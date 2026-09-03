"""Exchange a valid refresh token for a new token pair, rotating the old one."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from src.application.dtos.auth import RefreshInputDTO, TokenPairDTO
from src.application.ports.refresh_token_repository import RefreshTokenRepositoryProtocol
from src.application.ports.token_service import TokenServiceProtocol
from src.application.use_cases.token_pair import issue_token_pair
from src.domain.exceptions import InvalidTokenException


@dataclass
class RefreshTokenUseCase:
    refresh_tokens: RefreshTokenRepositoryProtocol
    tokens: TokenServiceProtocol

    async def execute(self, data: RefreshInputDTO) -> TokenPairDTO:
        claims = self.tokens.read_refresh_token(data.refresh_token)

        stored = await self.refresh_tokens.get_by_jti(claims.jti)
        now = datetime.now(UTC)
        if stored is None or not stored.is_active(now):
            raise InvalidTokenException("refresh token is not valid")

        # Rotation: the presented token is single-use.
        stored.revoke(now)
        await self.refresh_tokens.revoke(stored)

        return await issue_token_pair(claims.user_id, self.tokens, self.refresh_tokens)
