"""Outbound-notification providers. Backend chosen by ``settings.email_backend``."""

from __future__ import annotations

from functools import lru_cache
from typing import Annotated

import httpx
from fastapi import Depends

from src.application.ports.email_verification_notifier import (
    EmailVerificationNotifierProtocol,
)
from src.infrastructure.config import settings
from src.infrastructure.notifications.email_verification_notifier import (
    LoggingEmailVerificationNotifier,
    BrevoEmailVerificationNotifier,
)


@lru_cache
def _email_verification_notifier() -> EmailVerificationNotifierProtocol:
    if settings.email_backend == "brevo":
        return BrevoEmailVerificationNotifier(
            base_url=settings.app_base_url,
            sender=settings.email_from,
            api_key=settings.brevo_api_key,
            http=httpx.AsyncClient(),
        )
    return LoggingEmailVerificationNotifier(base_url=settings.app_base_url)


def get_email_verification_notifier() -> EmailVerificationNotifierProtocol:
    return _email_verification_notifier()


EmailVerificationNotifierDep = Annotated[
    EmailVerificationNotifierProtocol, Depends(get_email_verification_notifier)
]
