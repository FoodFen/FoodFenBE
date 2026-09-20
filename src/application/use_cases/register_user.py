"""Register a new user, log them in immediately, and (best-effort) start email
verification.

Verification no longer gates login — the client this API serves has no
"please verify your email" screen, so a session is handed back right away.
The verification email is still sent; it's just not required to use the app.
"""

from __future__ import annotations

from dataclasses import dataclass

from src.application.dtos.auth import RegisterInputDTO, RegisterResultDTO
from src.application.ports.password_hasher import PasswordHasherProtocol
from src.application.ports.refresh_token_repository import RefreshTokenRepositoryProtocol
from src.application.ports.token_service import TokenServiceProtocol
from src.application.ports.user_repository import UserRepositoryProtocol
from src.application.use_cases.token_pair import issue_session
from src.domain.entities.user import User
from src.domain.exceptions import UserAlreadyExistsException


@dataclass
class RegisterUserUseCase:
    users: UserRepositoryProtocol
    refresh_tokens: RefreshTokenRepositoryProtocol
    hasher: PasswordHasherProtocol
    tokens: TokenServiceProtocol

    async def execute(self, data: RegisterInputDTO) -> RegisterResultDTO:
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
        session = await issue_session(created, self.tokens, self.refresh_tokens)
        verification = self.tokens.issue_verification_token(created.id)
        return RegisterResultDTO(session=session, verification_token=verification.token)
