"""Daily sweep: flip lapsed ACTIVE subscriptions to EXPIRED and their users to FREE.

Complements the lazy check in ``di/security.py::get_premium_status`` (which still
guards access); this keeps the stored tier honest for ``/auth/me``, analytics, etc.
"""

from __future__ import annotations

import asyncio
from datetime import date

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.enums import SubscriptionStatus, SubscriptionTier
from src.infrastructure.db.models.subscription_model import SubscriptionORM
from src.infrastructure.db.models.user_model import UserORM
from src.infrastructure.db.session import SessionLocal
from src.infrastructure.logging import configure_logging

_log = configure_logging()
_INTERVAL_SECONDS = 24 * 60 * 60


async def expire_lapsed_subscriptions(session: AsyncSession, today: date) -> int:
    """Idempotent, so running it on several instances at once is harmless."""
    user_ids = (
        (
            await session.execute(
                update(SubscriptionORM)
                .where(
                    SubscriptionORM.status == SubscriptionStatus.ACTIVE,
                    SubscriptionORM.end_date < today,
                )
                .values(status=SubscriptionStatus.EXPIRED)
                .returning(SubscriptionORM.user_id)
            )
        )
        .scalars()
        .all()
    )
    if user_ids:
        await session.execute(
            update(UserORM)
            .where(UserORM.id.in_(user_ids))
            .values(subscription_tier=SubscriptionTier.FREE)
        )
    return len(user_ids)


async def run_expiry_loop() -> None:
    """Sweep at startup, then daily. ponytail: in-process loop, no scheduler — move to
    a cron/worker if the API ever scales past a few instances."""
    while True:
        try:
            async with SessionLocal() as session:
                expired = await expire_lapsed_subscriptions(session, date.today())
                await session.commit()
            if expired:
                _log.info("expired %d lapsed subscriptions", expired)
        except Exception:
            _log.exception("subscription expiry sweep failed")
        await asyncio.sleep(_INTERVAL_SECONDS)
