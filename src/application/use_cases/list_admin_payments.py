"""Use case: the admin transaction history. Filter (Vietnam-day range on ``created_at``), then page."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta

from src.application.dtos.admin import AdminPaymentFilterDTO, AdminPaymentListDTO
from src.application.ports.payment_repository import PaymentRepositoryProtocol
from src.application.use_cases.get_admin_dashboard import VIETNAM
from src.domain.enums import PaymentProvider, PaymentStatus, PlanType
from src.domain.exceptions import InvalidAttributeException


def _vn_midnight_utc(day: date) -> datetime:
    return datetime.combine(day, time(), VIETNAM).astimezone(UTC)


@dataclass
class ListAdminPaymentsUseCase:
    payments: PaymentRepositoryProtocol

    async def execute(
        self,
        q: str | None,
        status: PaymentStatus | None,
        plan_type: PlanType | None,
        provider: PaymentProvider | None,
        from_date: date | None,
        to_date: date | None,
        offset: int = 0,
        limit: int = 20,
    ) -> AdminPaymentListDTO:
        if from_date and to_date and from_date > to_date:
            raise InvalidAttributeException("'from' must not be after 'to'")
        try:
            start = _vn_midnight_utc(from_date) if from_date else None
            end = _vn_midnight_utc(to_date + timedelta(days=1)) if to_date else None
        except OverflowError as exc:
            raise InvalidAttributeException("date out of range") from exc
        rows, total = await self.payments.list_for_admin(
            AdminPaymentFilterDTO(q, status, plan_type, provider, start, end), offset, limit
        )
        page_end = offset + limit
        return AdminPaymentListDTO(
            payments=rows, total=total, next_cursor=str(page_end) if page_end < total else None
        )
