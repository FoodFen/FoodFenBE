"""Use case: the owner's ad payment history, newest first."""

from __future__ import annotations

from dataclasses import dataclass

from src.application.dtos.ad import MyAdPaymentDTO, MyAdPaymentListDTO
from src.application.ports.payment_repository import PaymentRepositoryProtocol
from src.application.ports.restaurant_repository import RestaurantRepositoryProtocol
from src.application.use_cases.restaurant_support import owned_restaurant


@dataclass
class ListMyPaymentsUseCase:
    restaurants: RestaurantRepositoryProtocol
    payments: PaymentRepositoryProtocol

    async def execute(self, user_id: int, offset: int = 0, limit: int = 20) -> MyAdPaymentListDTO:
        await owned_restaurant(self.restaurants, user_id)  # 404 without a restaurant
        rows = await self.payments.list_ad_payments(user_id, offset, limit + 1)  # +1: is there another page?
        return MyAdPaymentListDTO(
            payments=[
                MyAdPaymentDTO(
                    order_code=p.order_code or 0, amount=p.amount, status=p.status, provider=p.provider,
                    ad_days=p.ad_days or 0, created_at=p.created_at, paid_at=p.paid_at,
                )
                for p in rows[:limit]
            ],
            next_cursor=str(offset + limit) if len(rows) > limit else None,
        )
