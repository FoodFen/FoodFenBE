"""Shared helper: apply a payment provider's outcome to Payment and what it bought (Premium, or restaurant placement).

Used by both the webhook handler and the status-reconciliation fallback (the
same role as ``token_pair.py::issue_session`` for the auth slice) so the
"success -> grant what was bought" branch exists exactly once.
"""

from __future__ import annotations

from datetime import date

from src.application.ports.payment_repository import PaymentRepositoryProtocol
from src.application.ports.restaurant_repository import RestaurantRepositoryProtocol
from src.application.ports.subscription_repository import SubscriptionRepositoryProtocol
from src.application.ports.user_repository import UserRepositoryProtocol
from src.domain.entities.payment import Payment
from src.domain.entities.subscription import Subscription
from src.domain.enums import PaymentStatus, PlanType, SubscriptionTier


async def apply_payment_result(
    payment: Payment,
    succeeded: bool,
    payments: PaymentRepositoryProtocol,
    subscriptions: SubscriptionRepositoryProtocol,
    users: UserRepositoryProtocol,
    restaurants: RestaurantRepositoryProtocol,
) -> Payment:
    # Already processed (webhook retry / double reconciliation) — except a locally CANCELLED
    # payment the provider confirms as paid: that money must still grant Premium.
    if payment.status is not PaymentStatus.PENDING and not (
        payment.status is PaymentStatus.CANCELLED and succeeded
    ):
        return payment

    # Conditional write first: only the request that flips the status may renew Premium.
    # ponytail: two DIFFERENT payments of one user paid concurrently can still race on the
    # Subscription row; lock the user row (FOR UPDATE) if that ever matters.
    # ponytail: two ad payments of one owner paid concurrently can race on featured_until; lock the
    # restaurant row if that ever matters (same ceiling as the Subscription note above).
    if succeeded:
        payment.mark_paid()
        if not await payments.update_if_status(payment, (PaymentStatus.PENDING, PaymentStatus.CANCELLED)):
            return await _stored(payment, payments)
        if payment.plan_type is PlanType.AD_PACKAGE:
            restaurant = await restaurants.get_by_owner(payment.user_id)  # one restaurant per owner
            if restaurant is not None:
                restaurant.extend_featured(payment.ad_days, payment.paid_at)
                await restaurants.update(restaurant)
            return payment
        existing = await subscriptions.get_by_user_id(payment.user_id)
        renewed = Subscription.renew(
            existing, payment.user_id, payment.plan_type, payment.amount, date.today()
        )
        await subscriptions.save(renewed)

        user = await users.get_by_id(payment.user_id)
        if user is not None:
            user.subscription_tier = SubscriptionTier.PREMIUM
            await users.update(user)
        return payment

    payment.mark_failed()
    if not await payments.update_if_status(payment, (PaymentStatus.PENDING,)):
        return await _stored(payment, payments)
    return payment


async def _stored(payment: Payment, payments: PaymentRepositoryProtocol) -> Payment:
    """Another request already processed this payment: report what it stored, no side effects."""
    return await payments.get_by_order_code(payment.order_code) or payment
