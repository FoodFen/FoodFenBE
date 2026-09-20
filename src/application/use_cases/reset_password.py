"""Confirm a password reset: verify the token, set the new password.

Not part of the front-end contract (it only documents *requesting* a reset)
but necessary for the feature to do anything — this is what a reset-password
web page would call with the token from the emailed link.
"""

from __future__ import annotations

from dataclasses import dataclass

from src.application.dtos.auth import ResetPasswordInputDTO
from src.application.ports.password_hasher import PasswordHasherProtocol
from src.application.ports.token_service import TokenServiceProtocol
from src.application.ports.user_repository import UserRepositoryProtocol
from src.domain.entities.user import User
from src.domain.exceptions import UserNotFoundException


@dataclass
class ResetPasswordUseCase:
    users: UserRepositoryProtocol
    hasher: PasswordHasherProtocol
    tokens: TokenServiceProtocol

    async def execute(self, data: ResetPasswordInputDTO) -> None:
        user_id = self.tokens.read_password_reset_token(data.token)  # InvalidTokenException -> 401
        User.validate_password_strength(data.new_password)

        user = await self.users.get_by_id(user_id)
        if user is None:
            raise UserNotFoundException(f"user {user_id} not found")

        user.password_hash = self.hasher.hash(data.new_password)
        await self.users.update(user)
