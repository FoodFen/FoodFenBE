"""Confirm a password reset: verify the token, set the new password.

Not part of the front-end contract (it only documents *requesting* a reset)
but necessary for the feature to do anything — this is what a reset-password
web page would call with the token from the emailed link.

The token embeds the password stamp it was issued against, so it works once: after the
password changes the stamp no longer matches. Every existing session is revoked too, so
whoever held the old password (or a stolen refresh token) is locked out.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from src.application.dtos.auth import ResetPasswordInputDTO
from src.application.ports.password_hasher import PasswordHasherProtocol
from src.application.ports.refresh_token_repository import RefreshTokenRepositoryProtocol
from src.application.ports.token_service import TokenServiceProtocol
from src.application.ports.user_repository import UserRepositoryProtocol
from src.domain.exceptions import InvalidTokenException, UserNotFoundException


@dataclass
class ResetPasswordUseCase:
    users: UserRepositoryProtocol
    hasher: PasswordHasherProtocol
    tokens: TokenServiceProtocol
    refresh_tokens: RefreshTokenRepositoryProtocol

    async def execute(self, data: ResetPasswordInputDTO) -> None:
        user_id, stamp = self.tokens.read_password_reset_token(data.token)  # bad token -> 401

        user = await self.users.get_by_id(user_id)
        if user is None:
            raise UserNotFoundException(f"user {user_id} not found")
        if stamp != user.password_stamp:
            raise InvalidTokenException("password reset link was already used")
        user.validate_password_strength(data.new_password)

        user.password_hash = self.hasher.hash(data.new_password)
        await self.users.update(user)
        await self.refresh_tokens.revoke_all_for_user(user.id, datetime.now(UTC))
