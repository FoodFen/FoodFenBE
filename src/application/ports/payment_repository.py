"""Persistence port for payments. Structural typing via Protocol."""

from __future__ import annotations

from typing import Protocol

from src.application.dtos.admin import AdminPaymentFilterDTO, AdminPaymentRowDTO
from src.domain.entities.payment import Payment
from src.domain.enums import PaymentStatus


class PaymentRepositoryProtocol(Protocol):
    async def create(self, payment: Payment) -> Payment:
        """Insert. Assigns ``order_code`` (a DB identity column) and returns it set."""
        ...

    async def get_by_order_code(self, order_code: int) -> Payment | None: ...

    async def update(self, payment: Payment) -> Payment:
        """Raise ``PaymentNotFoundException`` if the row is gone."""
        ...

    async def update_if_status(self, payment: Payment, allowed: tuple[PaymentStatus, ...]) -> bool:
        """Persist ``status``/``paid_at`` only if the stored status is still in ``allowed``.

        True only for the one request whose write flipped it (like ``QuestRepository.record``).
        """
        ...

    async def list_for_admin(
        self, filters: AdminPaymentFilterDTO, offset: int, limit: int
    ) -> tuple[list[AdminPaymentRowDTO], int]:
        """Newest first (id breaks ties): the page ``[offset, offset + limit)`` and the total match count."""
        ...

    async def list_ad_payments(self, user_id: int, offset: int, limit: int) -> list[Payment]:
        """The user's ``ad_package`` payments, newest first (id breaks ties)."""
        ...
