"""Port: deliver an "please confirm your email" message. Standard library only.

Consumed by the auth controller (which schedules it as a FastAPI background task
after the response), not by the use cases — a use case cannot reach
``BackgroundTasks``. The use cases return a ``VerificationDispatchDTO``; the
controller hands it here.
"""

from __future__ import annotations

from typing import Protocol


class EmailVerificationNotifierProtocol(Protocol):
    async def send_verification(self, email: str, name: str, token: str) -> None: ...
