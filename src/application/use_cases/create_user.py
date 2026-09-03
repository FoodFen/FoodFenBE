"""Create-user use case. Standard library + domain only."""

from __future__ import annotations

from dataclasses import dataclass

from src.application.dtos.user import CreateUserInputDTO, UserOutputDTO
from src.application.ports.user_repository import UserRepositoryProtocol
from src.domain.entities.user import User
from src.domain.exceptions import UserAlreadyExistsException


@dataclass
class CreateUserUseCase:
    users: UserRepositoryProtocol

    async def execute(self, data: CreateUserInputDTO) -> UserOutputDTO:
        # Build first so domain invariants (email/name) are validated before the uniqueness check.
        user = User.create(email=data.email, name=data.name)

        if await self.users.get_by_email(user.email) is not None:
            raise UserAlreadyExistsException(
                f"user with email {user.email!r} already exists"
            )

        created = await self.users.create(user)
        return UserOutputDTO.from_entity(created)
