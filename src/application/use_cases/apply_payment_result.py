"""Shared helper: apply a payment provider's outcome to Payment/Subscription/User.

Used by both the webhook handler and the status-reconciliation fallback (the
same role as ``token_pair.py::issue_session`` for the auth slice) so the
"success -> extend premium" branch exists exactly once.
"""

from __future__ import annotations

from datetime import date

from src.application.ports.payment_repository import PaymentRepositoryProtocol
from src.application.ports.subscription_repository import SubscriptionRepositoryProtocol
from src.application.ports.user_repository import UserRepositoryProtocol
from src.domain.entities.payment import Payment
from src.domain.entities.subscription import Subscription
from src.domain.enums import PaymentStatus, SubscriptionTier


async def apply_payment_result(
    payment: Payment,
    succeeded: bool,
    payments: PaymentRepositoryProtocol,
    subscriptions: SubscriptionRepositoryProtocol,
    users: UserRepositoryProtocol,
) -> Payment:
    if payment.status is not PaymentStatus.PENDING:
        return payment  # already processed — webhook retry or double reconciliation

    if succeeded:
        payment.mark_paid()
        existing = await subscriptions.get_by_user_id(payment.user_id)
        renewed = Subscription.renew(
            existing, payment.user_id, payment.plan_type, payment.amount, date.today()
        )
        await subscriptions.save(renewed)

        user = await users.get_by_id(payment.user_id)
        if user is not None:
            user.subscription_tier = SubscriptionTier.PREMIUM
            await users.update(user)
    else:
        payment.mark_failed()

    return await payments.update(payment)
