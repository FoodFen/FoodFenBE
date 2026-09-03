"""Confirm a user's email from the token in the link they clicked."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from src.application.ports.token_service import TokenServiceProtocol
from src.application.ports.user_repository import UserRepositoryProtocol
from src.domain.exceptions import UserNotFoundException


@dataclass
class VerifyEmailUseCase:
    users: UserRepositoryProtocol
    tokens: TokenServiceProtocol

    async def execute(self, token: str) -> None:
        user_id = self.tokens.read_verification_token(token)  # InvalidTokenException -> 401
        user = await self.users.get_by_id(user_id)
        if user is None:
            raise UserNotFoundException(f"user {user_id} not found")

        if user.is_email_verified:
            return  # idempotent: clicking the link twice is fine

        user.verify_email(datetime.now(UTC))
        await self.users.update(user)
