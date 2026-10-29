"""``EmailVerificationNotifierProtocol`` implementations.

- ``LoggingEmailVerificationNotifier``: writes the link to the log (dev/test).
- ``BrevoEmailVerificationNotifier``: sends through Brevo's HTTP API (Render's free tier
  blocks the usual mail ports).

Both take their subject/body from ``_verification_message`` / ``_password_reset_message`` /
``_review_message``.
"""

from __future__ import annotations

import httpx

from src.infrastructure.logging import configure_logging

_log = configure_logging()
_BREVO_URL = "https://api.brevo.com/v3/smtp/email"


def _greeting(name: str | None) -> str:
    return name or "there"


def _verification_link(base_url: str, token: str) -> str:
    return f"{base_url.rstrip('/')}/auth/verify-email?token={token}"


def _password_reset_link(base_url: str, token: str) -> str:
    return f"{base_url.rstrip('/')}/auth/reset-password?token={token}"


def _verification_message(name: str | None, link: str) -> tuple[str, str]:
    return (
        "Confirm your FoodFen email",
        f"Hi {_greeting(name)},\n\n"
        f"Confirm your email address to activate your FoodFen account:\n\n"
        f"{link}\n\n"
        f"The link expires in 24 hours. If you didn't create an account, ignore this email.\n",
    )


def _password_reset_message(name: str | None, link: str) -> tuple[str, str]:
    return (
        "Reset your FoodFen password",
        f"Hi {_greeting(name)},\n\n"
        f"Reset your FoodFen password here:\n\n"
        f"{link}\n\n"
        f"The link expires soon. If you didn't request this, ignore this email — "
        f"your password will not change.\n",
    )


def _owner_portal_link(base_url: str) -> str:
    return f"{base_url.rstrip('/')}/restaurant"


def _review_message(
    name: str | None,
    restaurant_name: str,
    approved: bool,
    reason: str | None,
    dish_name: str | None,
    link: str,
) -> tuple[str, str]:
    if approved:
        return (
            f"{restaurant_name} is approved on FoodFen",
            f"Hi {_greeting(name)},\n\n"
            f"Good news: {restaurant_name} is approved and now visible to diners.\n\n"
            f"Manage your restaurant here:\n\n"
            f"{link}\n",
        )
    if dish_name:
        return (
            f"{dish_name} at {restaurant_name} was not approved",
            f"Hi {_greeting(name)},\n\n"
            f"Your dish {dish_name} at {restaurant_name} was not approved, so diners cannot see it.\n\n"
            f"Reason: {reason}\n\n"
            f"Edit the dish to send it back for review:\n\n"
            f"{link}\n",
        )
    return (
        f"{restaurant_name} was not approved on FoodFen",
        f"Hi {_greeting(name)},\n\n"
        f"{restaurant_name} was not approved, so diners cannot see it.\n\n"
        f"Reason: {reason}\n\n"
        f"Update your restaurant to send it back for review:\n\n"
        f"{link}\n",
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

    async def send_review_result(
        self,
        email: str,
        name: str | None,
        restaurant_name: str,
        approved: bool,
        reason: str | None,
        dish_name: str | None = None,
    ) -> None:
        link = _owner_portal_link(self._base_url)
        subject, _ = _review_message(name, restaurant_name, approved, reason, dish_name, link)
        _log.info("[email:console] review result for %s -> %s -> %s", email, subject, link)


class BrevoEmailVerificationNotifier:
    def __init__(self, *, base_url: str, sender: str, api_key: str, http: httpx.AsyncClient) -> None:
        self._base_url = base_url
        self._sender = sender
        self._api_key = api_key
        self._http = http

    async def send_verification(self, email: str, name: str | None, token: str) -> None:
        subject, body = _verification_message(name, _verification_link(self._base_url, token))
        await self._send(email, subject, body)

    async def send_password_reset(self, email: str, name: str | None, token: str) -> None:
        subject, body = _password_reset_message(name, _password_reset_link(self._base_url, token))
        await self._send(email, subject, body)

    async def send_review_result(
        self,
        email: str,
        name: str | None,
        restaurant_name: str,
        approved: bool,
        reason: str | None,
        dish_name: str | None = None,
    ) -> None:
        subject, body = _review_message(
            name, restaurant_name, approved, reason, dish_name, _owner_portal_link(self._base_url)
        )
        await self._send(email, subject, body)

    async def _send(self, email: str, subject: str, body: str) -> None:
        # Runs as a background task after the response: a failed email must be logged, not raised
        # (nobody awaits it, and it would only produce a noisy server error after a 200).
        try:
            response = await self._http.post(
                _BREVO_URL,
                headers={"api-key": self._api_key, "accept": "application/json"},
                json={
                    "sender": {"name": "FoodFen", "email": self._sender},
                    "to": [{"email": email}],
                    "subject": subject,
                    "textContent": body,
                },
                timeout=10,
            )
        except Exception:
            _log.exception("email delivery to %s failed", email)
            return
        if not response.is_success:
            _log.error(
                "email delivery to %s failed: %s %s", email, response.status_code, response.text
            )
