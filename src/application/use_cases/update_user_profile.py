"""Use case: partial update of the caller's own profile (PATCH /users/me).

True partial-patch semantics — only keys present in ``updates`` are applied;
everything else on the user is left exactly as it was. ``display_name`` is
the one field whose wire/DTO name doesn't match the domain attribute
(``User.name``), same mapping ``user_schemas.py`` already does for reads.
"""

from __future__ import annotations

from dataclasses import dataclass

from src.application.dtos.update_user_profile import UpdateUserProfileInputDTO
from src.application.dtos.user import UserOutputDTO
from src.application.ports.user_repository import UserRepositoryProtocol
from src.domain.exceptions import (
    InvalidUserAttributeException,
    UserAlreadyExistsException,
    UserNotFoundException,
)

# Fields the domain never allows None for, even though the wire schema types
# them Optional purely so a PATCH can omit them. An explicit null for one of
# these would otherwise reach the DB's NOT NULL constraint as a raw 500.
_NON_NULLABLE_FIELDS = ("unit_system", "calorie_calc_mode")


@dataclass
class UpdateUserProfileUseCase:
    users: UserRepositoryProtocol

    async def execute(self, input_dto: UpdateUserProfileInputDTO) -> UserOutputDTO:
        user = await self.users.get_by_id(input_dto.user_id)
        if user is None:
            raise UserNotFoundException(f"user {input_dto.user_id} not found")

        updates = dict(input_dto.updates)
        if "display_name" in updates:
            updates["name"] = updates.pop("display_name")

        for field in _NON_NULLABLE_FIELDS:
            if field in updates and updates[field] is None:
                raise InvalidUserAttributeException(f"{field} must not be null")

        new_email = updates.get("email")
        if new_email is not None:
            new_email = new_email.strip().lower()
            updates["email"] = new_email
            if new_email != user.email:
                existing = await self.users.get_by_email(new_email)
                if existing is not None and existing.id != user.id:
                    raise UserAlreadyExistsException(
                        f"user with email {new_email!r} already exists"
                    )
                user.email_verified_at = None  # a changed, unproven address is no longer verified

        for field, value in updates.items():
            setattr(user, field, value)
        user.__post_init__()

        updated = await self.users.update(user)
        return UserOutputDTO.from_entity(updated)
