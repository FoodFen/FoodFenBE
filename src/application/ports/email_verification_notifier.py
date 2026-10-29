"""Port: deliver the account-lifecycle emails (verify address, reset password) and the
moderation result sent to a restaurant owner.

Consumed by the auth and admin controllers, not the use cases — a use case cannot reach
``BackgroundTasks``, which is how the send is scheduled after the response.

Password reset lives on this port rather than a second one: both are "mint a
token, email a link" over the same transport; the review result is one more email over it.
"""

from __future__ import annotations

from typing import Protocol


class EmailVerificationNotifierProtocol(Protocol):
    async def send_verification(self, email: str, name: str, token: str) -> None: ...

    async def send_password_reset(self, email: str, name: str, token: str) -> None: ...

    async def send_review_result(
        self,
        email: str,
        name: str | None,
        restaurant_name: str,
        approved: bool,
        reason: str | None,
        dish_name: str | None = None,
    ) -> None:
        """Tell an owner their restaurant (or, with ``dish_name``, a dish) was approved or rejected."""
        ...
