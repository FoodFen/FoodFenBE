"""Concrete ``UserRepositoryProtocol`` implementation backed by async SQLAlchemy."""

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.entities.user import User
from src.domain.exceptions import UserAlreadyExistsException, UserNotFoundException
from src.infrastructure.db.models.user_model import UserORM


class SQLAlchemyUserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, user_id: int) -> User | None:
        row = await self._session.get(UserORM, user_id)
        return row.to_domain() if row is not None else None

    async def get_by_email(self, email: str) -> User | None:
        row = (
            await self._session.execute(select(UserORM).where(UserORM.email == email))
        ).scalar_one_or_none()
        return row.to_domain() if row is not None else None

    async def create(self, user: User) -> User:
        row = UserORM.from_domain(user)
        try:
            # Savepoint, as in the restaurant repo: keeps the request's transaction usable on failure.
            async with self._session.begin_nested():
                self._session.add(row)
                await self._session.flush()
        except IntegrityError as exc:  # uq on users.email: a concurrent sign-up with the same email
            raise UserAlreadyExistsException(
                f"user with email {user.email!r} already exists"
            ) from exc
        await self._session.refresh(row)
        return row.to_domain()

    async def update(self, user: User) -> User:
        row = await self._session.get(UserORM, user.id)
        if row is None:
            raise UserNotFoundException(f"user {user.id} not found")
        fresh = UserORM.from_domain(user)
        for column in UserORM.__table__.columns.keys():
            if column != "equipped_mascot_id":  # not on the entity; the mascot repository owns it
                setattr(row, column, getattr(fresh, column))
        await self._session.flush()
        return row.to_domain()

    async def lock(self, user_id: int) -> None:
        await self._session.execute(select(UserORM.id).where(UserORM.id == user_id).with_for_update())
