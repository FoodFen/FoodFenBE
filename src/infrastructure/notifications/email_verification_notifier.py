"""``EmailVerificationNotifierProtocol`` implementations.

- ``LoggingEmailVerificationNotifier``: writes the link to the log (dev/test).
- ``SmtpEmailVerificationNotifier``: sends via SMTP using the stdlib client,
  off the event loop with ``asyncio.to_thread``.

Both build their messages via ``_build_message`` so the wording lives in one place.
"""

from __future__ import annotations

import asyncio
import smtplib
from email.message import EmailMessage

from src.infrastructure.logging import configure_logging

_log = configure_logging()


def _greeting(name: str | None) -> str:
    return name or "there"


def _verification_link(base_url: str, token: str) -> str:
    return f"{base_url.rstrip('/')}/auth/verify-email?token={token}"


def _password_reset_link(base_url: str, token: str) -> str:
    return f"{base_url.rstrip('/')}/auth/reset-password?token={token}"


def _build_message(sender: str, to: str, subject: str, body: str) -> EmailMessage:
    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = sender
    message["To"] = to
    message.set_content(body)
    return message


def _verification_message(sender: str, email: str, name: str | None, link: str) -> EmailMessage:
    return _build_message(
        sender,
        email,
        "Confirm your FoodFen email",
        f"Hi {_greeting(name)},\n\n"
        f"Confirm your email address to activate your FoodFen account:\n\n"
        f"{link}\n\n"
        f"The link expires in 24 hours. If you didn't create an account, ignore this email.\n",
    )


def _password_reset_message(sender: str, email: str, name: str | None, link: str) -> EmailMessage:
    return _build_message(
        sender,
        email,
        "Reset your FoodFen password",
        f"Hi {_greeting(name)},\n\n"
        f"Reset your FoodFen password here:\n\n"
        f"{link}\n\n"
        f"The link expires soon. If you didn't request this, ignore this email — "
        f"your password will not change.\n",
    )


class LoggingEmailVerificationNotifier:
    def __init__(self, *, base_url: str) -> None:
        self._base_url = base_url

    async def send_verification(self, email: str, name: str | None, token: str) -> None:
        _log.info(
            "[email:console] verification link for %s -> %s",
            email,
            _verification_link(self._base_url, token),
        )

    async def send_password_reset(self, email: str, name: str | None, token: str) -> None:
        _log.info(
            "[email:console] password reset link for %s -> %s",
            email,
            _password_reset_link(self._base_url, token),
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

    async def send_verification(self, email: str, name: str | None, token: str) -> None:
        message = _verification_message(
            self._sender, email, name, _verification_link(self._base_url, token)
        )
        await asyncio.to_thread(self._deliver, message)

    async def send_password_reset(self, email: str, name: str | None, token: str) -> None:
        message = _password_reset_message(
            self._sender, email, name, _password_reset_link(self._base_url, token)
        )
        await asyncio.to_thread(self._deliver, message)

    def _deliver(self, message: EmailMessage) -> None:
        with smtplib.SMTP(self._host, self._port, timeout=10) as smtp:
            if self._starttls:
                smtp.starttls()
            if self._username:
                smtp.login(self._username, self._password)
            smtp.send_message(message)
