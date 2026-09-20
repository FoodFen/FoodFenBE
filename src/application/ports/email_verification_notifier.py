"""Port: deliver the account-lifecycle emails (verify address, reset password).

Consumed by the auth controller, not the use cases — a use case cannot reach
``BackgroundTasks``, which is how the send is scheduled after the response.

Password reset lives on this port rather than a second one: both are "mint a
token, email a link" over the same transport.
"""

from __future__ import annotations

from typing import Protocol


class EmailVerificationNotifierProtocol(Protocol):
    async def send_verification(self, email: str, name: str, token: str) -> None: ...

    async def send_password_reset(self, email: str, name: str, token: str) -> None: ...
