"""Get-user-by-id use case. Standard library + domain only."""

from __future__ import annotations

from dataclasses import dataclass

from src.application.dtos.user import UserOutputDTO
from src.application.ports.user_repository import UserRepositoryProtocol
from src.domain.exceptions import UserNotFoundException


@dataclass
class GetUserUseCase:
    users: UserRepositoryProtocol

    async def execute(self, user_id: int) -> UserOutputDTO:
        user = await self.users.get_by_id(user_id)
        if user is None:
            raise UserNotFoundException(f"user {user_id} not found")
        return UserOutputDTO.from_entity(user)
