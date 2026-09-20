"""Issue a fresh verification token for an unverified account.

Returns ``None`` when there is nothing to send (unknown email, or already
verified) so the controller can answer identically in every case and not leak
whether an address is registered.
"""

from __future__ import annotations

from dataclasses import dataclass

from src.application.dtos.auth import ResendVerificationInputDTO, VerificationDispatchDTO
from src.application.ports.token_service import TokenServiceProtocol
from src.application.ports.user_repository import UserRepositoryProtocol


@dataclass
class ResendVerificationUseCase:
    users: UserRepositoryProtocol
    tokens: TokenServiceProtocol

    async def execute(self, data: ResendVerificationInputDTO) -> VerificationDispatchDTO | None:
        user = await self.users.get_by_email(data.email.strip().lower())
        if user is None or user.is_email_verified:
            return None
        token = self.tokens.issue_verification_token(user.id)
        return VerificationDispatchDTO(email=user.email, name=user.name, token=token.token)
