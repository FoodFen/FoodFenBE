"""Verify email + password and hand back a token pair."""

from __future__ import annotations

from dataclasses import dataclass

from src.application.dtos.auth import LoginInputDTO, TokenPairDTO
from src.application.ports.password_hasher import PasswordHasherProtocol
from src.application.ports.refresh_token_repository import RefreshTokenRepositoryProtocol
from src.application.ports.token_service import TokenServiceProtocol
from src.application.ports.user_repository import UserRepositoryProtocol
from src.application.use_cases.token_pair import issue_token_pair
from src.domain.exceptions import InvalidCredentialsException


@dataclass
class LoginUseCase:
    users: UserRepositoryProtocol
    refresh_tokens: RefreshTokenRepositoryProtocol
    hasher: PasswordHasherProtocol
    tokens: TokenServiceProtocol

    async def execute(self, data: LoginInputDTO) -> TokenPairDTO:
        user = await self.users.get_by_email(data.email.strip().lower())

        # One message for "no such user" and "wrong password" — no account enumeration.
        # ponytail: no dummy-hash timing equalisation; network jitter dwarfs the bcrypt
        # delta. Add a constant-time dummy verify if login timing ever becomes a concern.
        if (
            user is None
            or user.password_hash is None
            or not self.hasher.verify(data.password, user.password_hash)
        ):
            raise InvalidCredentialsException("invalid email or password")
        if not user.is_active:
            raise InvalidCredentialsException("account is disabled")

        return await issue_token_pair(user.id, self.tokens, self.refresh_tokens)
