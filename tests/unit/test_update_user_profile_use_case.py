"""UpdateUserProfileUseCase unit tests. No I/O."""

from __future__ import annotations

import pytest

from src.application.dtos.update_user_profile import UpdateUserProfileInputDTO
from src.application.use_cases.update_user_profile import UpdateUserProfileUseCase
from src.domain.entities.user import User
from src.domain.enums import Gender
from src.domain.exceptions import InvalidUserAttributeException, UserAlreadyExistsException, UserNotFoundException


class FakeUserRepo:
    def __init__(self, users: list[User]) -> None:
        self._by_id = {u.id: u for u in users}

    async def get_by_id(self, user_id):
        return self._by_id.get(user_id)

    async def get_by_email(self, email):
        return next((u for u in self._by_id.values() if u.email == email), None)

    async def create(self, user):
        raise NotImplementedError

    async def update(self, user):
        if user.id not in self._by_id:
            raise UserNotFoundException(f"user {user.id} not found")
        self._by_id[user.id] = user
        return user


def _user(user_id=1, **overrides) -> User:
    user = User.create(email="a@example.com", name="Original")
    user.id = user_id
    for field, value in overrides.items():
        setattr(user, field, value)
    return user


async def test_only_the_sent_fields_change():
    repo = FakeUserRepo([_user(height=170.0, weight_current=70.0)])
    use_case = UpdateUserProfileUseCase(users=repo)

    result = await use_case.execute(
        UpdateUserProfileInputDTO(user_id=1, updates={"height": 180.0})
    )

    assert result.height == 180.0
    assert result.weight_current == 70.0  # untouched: not in `updates`


async def test_empty_updates_leaves_the_user_unchanged():
    repo = FakeUserRepo([_user(name="Original")])
    use_case = UpdateUserProfileUseCase(users=repo)

    result = await use_case.execute(UpdateUserProfileInputDTO(user_id=1, updates={}))

    assert result.name == "Original"


async def test_display_name_maps_to_the_domains_name_field():
    repo = FakeUserRepo([_user(name="Original")])
    use_case = UpdateUserProfileUseCase(users=repo)

    result = await use_case.execute(
        UpdateUserProfileInputDTO(user_id=1, updates={"display_name": "New Name"})
    )

    assert result.name == "New Name"


async def test_gender_updates():
    repo = FakeUserRepo([_user()])
    use_case = UpdateUserProfileUseCase(users=repo)

    result = await use_case.execute(
        UpdateUserProfileInputDTO(user_id=1, updates={"gender": Gender.FEMALE})
    )

    assert result.gender is Gender.FEMALE


async def test_invalid_value_raises_domain_exception():
    repo = FakeUserRepo([_user()])
    use_case = UpdateUserProfileUseCase(users=repo)

    with pytest.raises(InvalidUserAttributeException):
        await use_case.execute(UpdateUserProfileInputDTO(user_id=1, updates={"height": -5.0}))


async def test_changing_email_to_one_already_taken_raises():
    repo = FakeUserRepo([_user(user_id=1), _user(user_id=2, name="Taken")])
    repo._by_id[2].email = "taken@example.com"
    use_case = UpdateUserProfileUseCase(users=repo)

    with pytest.raises(UserAlreadyExistsException):
        await use_case.execute(
            UpdateUserProfileInputDTO(user_id=1, updates={"email": "taken@example.com"})
        )


async def test_changing_email_to_a_taken_one_with_different_case_still_raises():
    """Every other path (login, reset, social) normalizes email with
    .strip().lower() before comparing — this endpoint must too, or a
    mixed-case duplicate reaches the DB's unique constraint as a raw 500
    instead of the clean 400 UserAlreadyExistsException gives."""
    repo = FakeUserRepo([_user(user_id=1), _user(user_id=2, name="Taken")])
    repo._by_id[2].email = "taken@example.com"
    use_case = UpdateUserProfileUseCase(users=repo)

    with pytest.raises(UserAlreadyExistsException):
        await use_case.execute(
            UpdateUserProfileInputDTO(user_id=1, updates={"email": "Taken@Example.com"})
        )


async def test_null_unit_system_raises_instead_of_hitting_the_db_not_null_constraint():
    repo = FakeUserRepo([_user()])
    use_case = UpdateUserProfileUseCase(users=repo)

    with pytest.raises(InvalidUserAttributeException):
        await use_case.execute(UpdateUserProfileInputDTO(user_id=1, updates={"unit_system": None}))


async def test_null_calorie_calc_mode_raises_instead_of_hitting_the_db_not_null_constraint():
    repo = FakeUserRepo([_user()])
    use_case = UpdateUserProfileUseCase(users=repo)

    with pytest.raises(InvalidUserAttributeException):
        await use_case.execute(
            UpdateUserProfileInputDTO(user_id=1, updates={"calorie_calc_mode": None})
        )


async def test_changing_email_clears_verified_status():
    from datetime import UTC, datetime

    user = _user()
    user.verify_email(datetime(2026, 1, 1, tzinfo=UTC))
    repo = FakeUserRepo([user])
    use_case = UpdateUserProfileUseCase(users=repo)

    result = await use_case.execute(
        UpdateUserProfileInputDTO(user_id=1, updates={"email": "new@example.com"})
    )

    assert result.id == 1
    assert repo._by_id[1].email_verified_at is None
