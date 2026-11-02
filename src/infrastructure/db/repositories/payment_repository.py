"""Concrete ``PaymentRepositoryProtocol`` implementation backed by async SQLAlchemy."""

from __future__ import annotations

from sqlalchemy import and_, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.entities.payment import Payment
from src.application.dtos.admin import AdminPaymentFilterDTO, AdminPaymentRowDTO
from src.domain.enums import PaymentStatus, PlanType
from src.domain.exceptions import PaymentNotFoundException
from src.infrastructure.db.models.payment_model import PaymentORM
from src.infrastructure.db.models.restaurant_model import RestaurantORM
from src.infrastructure.db.models.user_model import UserORM


class SQLAlchemyPaymentRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, payment: Payment) -> Payment:
        row = PaymentORM.from_domain(payment)
        self._session.add(row)
        await self._session.flush()
        await self._session.refresh(row)
        return row.to_domain()

    async def get_by_order_code(self, order_code: int) -> Payment | None:
        row = (
            await self._session.execute(
                select(PaymentORM)
                .where(PaymentORM.order_code == order_code)
                .execution_options(populate_existing=True)  # see a concurrent request's committed flip
            )
        ).scalar_one_or_none()
        return row.to_domain() if row is not None else None

    async def update(self, payment: Payment) -> Payment:
        row = await self._session.get(PaymentORM, payment.id)
        if row is None:
            raise PaymentNotFoundException(f"payment {payment.id} not found")
        fresh = PaymentORM.from_domain(payment)
        for column in PaymentORM.__table__.columns.keys():
            if column == "order_code":
                continue  # identity column: never overwritten after insert
            setattr(row, column, getattr(fresh, column))
        await self._session.flush()
        return row.to_domain()

    async def update_if_status(self, payment: Payment, allowed: tuple[PaymentStatus, ...]) -> bool:
        flipped = await self._session.scalar(
            update(PaymentORM)
            .where(PaymentORM.id == payment.id, PaymentORM.status.in_(allowed))
            .values(status=payment.status, paid_at=payment.paid_at)
            .returning(PaymentORM.id)
        )
        return flipped is not None

    async def list_for_admin(
        self, filters: AdminPaymentFilterDTO, offset: int, limit: int
    ) -> tuple[list[AdminPaymentRowDTO], int]:
        f = filters
        where = []
        if f.q and f.q.strip():
            q = f.q.strip()
            match = UserORM.email.icontains(q, autoescape=True)
            if q.isascii() and q.isdigit() and len(q) <= 18:  # fits BIGINT
                match = or_(match, PaymentORM.order_code == int(q))
            where.append(match)
        if f.status is not None:
            where.append(PaymentORM.status == f.status)
        if f.plan_type is not None:
            where.append(PaymentORM.plan_type == f.plan_type)
        if f.provider is not None:
            where.append(PaymentORM.provider == f.provider)
        if f.start is not None:
            where.append(PaymentORM.created_at >= f.start)
        if f.end is not None:
            where.append(PaymentORM.created_at < f.end)
        base = (
            select(PaymentORM, UserORM.email, UserORM.name, RestaurantORM.id, RestaurantORM.name)
            .join(UserORM, UserORM.id == PaymentORM.user_id)
            # restaurants.user_id is unique, so this join adds no rows
            .outerjoin(
                RestaurantORM,
                and_(RestaurantORM.user_id == PaymentORM.user_id, PaymentORM.plan_type == PlanType.AD_PACKAGE),
            )
            .where(*where)
        )
        total = await self._session.scalar(select(func.count()).select_from(base.subquery()))
        rows = (
            await self._session.execute(
                base.order_by(PaymentORM.created_at.desc(), PaymentORM.id.desc()).offset(offset).limit(limit)
            )
        ).all()
        return [
            AdminPaymentRowDTO(
                id=p.id, order_code=p.order_code, user_id=p.user_id, user_email=email, user_name=name,
                restaurant_id=restaurant_id, restaurant_name=restaurant_name, plan_type=p.plan_type,
                provider=p.provider, amount=p.amount, status=p.status, ad_days=p.ad_days,
                created_at=p.created_at, paid_at=p.paid_at,
            )
            for p, email, name, restaurant_id, restaurant_name in rows
        ], int(total or 0)

    async def list_ad_payments(self, user_id: int, offset: int, limit: int) -> list[Payment]:
        rows = await self._session.execute(
            select(PaymentORM)
            .where(PaymentORM.user_id == user_id, PaymentORM.plan_type == PlanType.AD_PACKAGE)
            .order_by(PaymentORM.created_at.desc(), PaymentORM.id.desc())
            .offset(offset)
            .limit(limit)
        )
        return [row.to_domain() for row in rows.scalars()]
