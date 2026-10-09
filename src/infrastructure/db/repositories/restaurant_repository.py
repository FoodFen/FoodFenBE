"""Concrete ``RestaurantRepositoryProtocol`` backed by async SQLAlchemy."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import and_, case, delete, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.application.dtos.admin import AdminRestaurantRowDTO
from src.domain.entities.dish import Dish
from src.domain.entities.restaurant import Restaurant
from src.domain.enums import ModerationStatus
from src.domain.exceptions import RestaurantAlreadyExistsException
from src.infrastructure.db.models.dish_model import DishORM
from src.infrastructure.db.models.restaurant_model import RestaurantORM
from src.infrastructure.db.models.user_model import UserORM


class SQLAlchemyRestaurantRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, restaurant: Restaurant) -> None:
        try:
            # Savepoint, as in idempotency.py: keeps the request's transaction usable on failure.
            async with self._session.begin_nested():
                self._session.add(RestaurantORM.from_domain(restaurant))
                await self._session.flush()
        except IntegrityError as exc:  # uq_restaurants_user_id: a concurrent second create
            raise RestaurantAlreadyExistsException("you already have a restaurant") from exc

    async def get_by_id(self, restaurant_id: UUID) -> Restaurant | None:
        row = await self._session.get(RestaurantORM, restaurant_id)
        return row.to_domain() if row else None

    async def get_by_owner(self, user_id: int) -> Restaurant | None:
        row = (
            await self._session.execute(select(RestaurantORM).where(RestaurantORM.user_id == user_id))
        ).scalar_one_or_none()
        return row.to_domain() if row else None

    async def update(self, restaurant: Restaurant) -> None:
        await self._session.merge(RestaurantORM.from_domain(restaurant))
        await self._session.flush()

    async def list_for_admin(
        self, needs_review: bool, status: ModerationStatus | None
    ) -> list[AdminRestaurantRowDTO]:
        dish_count = func.count(DishORM.id)
        pending_count = func.coalesce(
            func.sum(case((DishORM.status == ModerationStatus.PENDING, 1), else_=0)), 0
        )
        stmt = (
            select(
                RestaurantORM,
                UserORM.name,
                UserORM.email,
                dish_count.label("dish_count"),
                pending_count.label("pending_dish_count"),
            )
            .join(UserORM, UserORM.id == RestaurantORM.user_id)
            .outerjoin(DishORM, DishORM.restaurant_id == RestaurantORM.id)
            .group_by(RestaurantORM.id, UserORM.id)
            .order_by(RestaurantORM.updated_at)
        )
        if status is not None:
            stmt = stmt.where(RestaurantORM.status == status)
        if needs_review:
            stmt = stmt.having(
                or_(
                    RestaurantORM.status == ModerationStatus.PENDING,
                    and_(RestaurantORM.status == ModerationStatus.APPROVED, pending_count > 0),
                )
            )
        rows = (await self._session.execute(stmt)).all()
        return [
            AdminRestaurantRowDTO(
                id=r.id, name=r.name, status=r.status, owner_name=owner_name,
                owner_email=owner_email, dish_count=int(dishes), pending_dish_count=int(pending),
                updated_at=r.updated_at, rejection_reason=r.rejection_reason,
            )
            for r, owner_name, owner_email, dishes, pending in rows
        ]

    async def add_dish(self, dish: Dish) -> None:
        self._session.add(DishORM.from_domain(dish))
        await self._session.flush()

    async def get_dish(self, dish_id: UUID) -> Dish | None:
        row = await self._session.get(DishORM, dish_id)
        return row.to_domain() if row else None

    async def update_dish(self, dish: Dish) -> None:
        await self._session.merge(DishORM.from_domain(dish))
        await self._session.flush()

    async def delete_dish(self, dish_id: UUID) -> None:
        await self._session.execute(delete(DishORM).where(DishORM.id == dish_id))

    async def list_dishes(self, restaurant_id: UUID) -> list[Dish]:
        rows = (
            await self._session.execute(
                select(DishORM)
                .where(DishORM.restaurant_id == restaurant_id)
                .order_by(DishORM.created_at, DishORM.id)
            )
        ).scalars().all()
        return [row.to_domain() for row in rows]

    async def list_public_dishes(self) -> list[tuple[Dish, Restaurant]]:
        rows = (
            await self._session.execute(
                select(DishORM, RestaurantORM)
                .join(RestaurantORM, RestaurantORM.id == DishORM.restaurant_id)
                .where(
                    DishORM.status == ModerationStatus.APPROVED,
                    RestaurantORM.status == ModerationStatus.APPROVED,
                )
            )
        ).all()
        return [(d.to_domain(), r.to_domain()) for d, r in rows]
