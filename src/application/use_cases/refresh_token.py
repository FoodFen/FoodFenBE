"""Exchange a valid refresh token for a new session, rotating the old token."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from src.application.dtos.auth import AuthSessionDTO, RefreshInputDTO
from src.application.ports.refresh_token_repository import RefreshTokenRepositoryProtocol
from src.application.ports.token_service import TokenServiceProtocol
from src.application.ports.user_repository import UserRepositoryProtocol
from src.application.use_cases.token_pair import issue_session
from src.domain.exceptions import InvalidTokenException, UserNotFoundException


@dataclass
class RefreshTokenUseCase:
    users: UserRepositoryProtocol
    refresh_tokens: RefreshTokenRepositoryProtocol
    tokens: TokenServiceProtocol

    async def execute(self, data: RefreshInputDTO) -> AuthSessionDTO:
        claims = self.tokens.read_refresh_token(data.refresh_token)

        stored = await self.refresh_tokens.get_by_jti(claims.jti)
        now = datetime.now(UTC)
        if stored is None or not stored.is_active(now):
            raise InvalidTokenException("refresh token is not valid")

        # Rotation: the presented token is single-use.
        stored.revoke(now)
        await self.refresh_tokens.revoke(stored)

        user = await self.users.get_by_id(claims.user_id)
        if user is None:
            raise UserNotFoundException(f"user {claims.user_id} not found")

        return await issue_session(user, self.tokens, self.refresh_tokens)
