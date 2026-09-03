"""``EmailVerificationNotifierProtocol`` implementations.

- ``LoggingEmailVerificationNotifier``: writes the link to the log (dev/test).
- ``SmtpEmailVerificationNotifier``: sends via SMTP using the stdlib client,
  off the event loop with ``asyncio.to_thread``.

Both build the same message via ``_build_message`` so the wording lives in one place.
"""

from __future__ import annotations

import asyncio
import smtplib
from email.message import EmailMessage

from src.infrastructure.logging import configure_logging

_log = configure_logging()


def _verification_link(base_url: str, token: str) -> str:
    return f"{base_url.rstrip('/')}/auth/verify-email?token={token}"


def _build_message(sender: str, to: str, name: str, link: str) -> EmailMessage:
    message = EmailMessage()
    message["Subject"] = "Confirm your FoodFen email"
    message["From"] = sender
    message["To"] = to
    message.set_content(
        f"Hi {name},\n\n"
        f"Confirm your email address to activate your FoodFen account:\n\n"
        f"{link}\n\n"
        f"The link expires in 24 hours. If you didn't create an account, ignore this email.\n"
    )
    return message


class LoggingEmailVerificationNotifier:
    def __init__(self, *, base_url: str) -> None:
        self._base_url = base_url

    async def send_verification(self, email: str, name: str, token: str) -> None:
        _log.info(
            "[email:console] verification link for %s -> %s",
            email,
            _verification_link(self._base_url, token),
        )


class SmtpEmailVerificationNotifier:
    def __init__(
        self,
        *,
        base_url: str,
        sender: str,
        host: str,
        port: int,
        username: str,
        password: str,
        starttls: bool,
    ) -> None:
        self._base_url = base_url
        self._sender = sender
        self._host = host
        self._port = port
        self._username = username
        self._password = password
        self._starttls = starttls

    async def send_verification(self, email: str, name: str, token: str) -> None:
        message = _build_message(
            self._sender, email, name, _verification_link(self._base_url, token)
        )
        await asyncio.to_thread(self._deliver, message)

    def _deliver(self, message: EmailMessage) -> None:
        with smtplib.SMTP(self._host, self._port, timeout=10) as smtp:
            if self._starttls:
                smtp.starttls()
            if self._username:
                smtp.login(self._username, self._password)
            smtp.send_message(message)
