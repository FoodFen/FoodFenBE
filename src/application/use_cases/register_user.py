"""Register a new (unverified) user and produce the data for a verification email."""

from __future__ import annotations

from dataclasses import dataclass

from src.application.dtos.auth import RegisterInputDTO, VerificationDispatchDTO
from src.application.ports.password_hasher import PasswordHasherProtocol
from src.application.ports.token_service import TokenServiceProtocol
from src.application.ports.user_repository import UserRepositoryProtocol
from src.domain.entities.user import User
from src.domain.exceptions import UserAlreadyExistsException


@dataclass
class RegisterUserUseCase:
    users: UserRepositoryProtocol
    hasher: PasswordHasherProtocol
    tokens: TokenServiceProtocol

    async def execute(self, data: RegisterInputDTO) -> VerificationDispatchDTO:
        User.validate_password_strength(data.password)
        user = User.create(
            email=data.email,
            name=data.name,
            password_hash=self.hasher.hash(data.password),
        )  # email_verified_at is None -> login is blocked until confirmed

        if await self.users.get_by_email(user.email) is not None:
            raise UserAlreadyExistsException(
                f"user with email {user.email!r} already exists"
            )

        created = await self.users.create(user)
        token = self.tokens.issue_verification_token(created.id)
        return VerificationDispatchDTO(email=created.email, name=created.name, token=token.token)
