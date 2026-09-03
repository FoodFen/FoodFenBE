"""Register a new user and hand back a token pair."""

from __future__ import annotations

from dataclasses import dataclass

from src.application.dtos.auth import RegisterInputDTO, TokenPairDTO
from src.application.ports.password_hasher import PasswordHasherProtocol
from src.application.ports.refresh_token_repository import (
    RefreshTokenRepositoryProtocol,
)
from src.application.ports.token_service import TokenServiceProtocol
from src.application.ports.user_repository import UserRepositoryProtocol
from src.application.use_cases.token_pair import issue_token_pair
from src.domain.entities.user import User
from src.domain.exceptions import UserAlreadyExistsException


@dataclass
class RegisterUserUseCase:
    users: UserRepositoryProtocol
    refresh_tokens: RefreshTokenRepositoryProtocol
    hasher: PasswordHasherProtocol
    tokens: TokenServiceProtocol

    async def execute(self, data: RegisterInputDTO) -> TokenPairDTO:
        User.validate_password_strength(data.password)
        user = User.create(
            email=data.email,
            name=data.name,
            password_hash=self.hasher.hash(data.password),
        )

        if await self.users.get_by_email(user.email) is not None:
            raise UserAlreadyExistsException(
                f"user with email {user.email!r} already exists"
            )

        created = await self.users.create(user)
        return await issue_token_pair(created.id, self.tokens, self.refresh_tokens)
