"""Issue a password-reset token for an account, if one exists.

Returns ``None`` when there is nothing to send (unknown email) so the
controller can answer identically either way and not leak whether an address
is registered — same pattern as ``ResendVerificationUseCase``.
"""

from __future__ import annotations

from dataclasses import dataclass

from src.application.dtos.auth import RequestPasswordResetInputDTO, VerificationDispatchDTO
from src.application.ports.token_service import TokenServiceProtocol
from src.application.ports.user_repository import UserRepositoryProtocol


@dataclass
class RequestPasswordResetUseCase:
    users: UserRepositoryProtocol
    tokens: TokenServiceProtocol

    async def execute(self, data: RequestPasswordResetInputDTO) -> VerificationDispatchDTO | None:
        user = await self.users.get_by_email(data.email.strip().lower())
        if user is None:
            return None
        token = self.tokens.issue_password_reset_token(user.id, user.password_stamp)
        return VerificationDispatchDTO(email=user.email, name=user.name, token=token.token)
