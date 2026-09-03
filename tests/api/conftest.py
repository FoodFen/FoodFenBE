"""Shared fixtures for API tests: schema reset, HTTP client, a recording notifier."""

from __future__ import annotations

import pytest_asyncio
from httpx import ASGITransport, AsyncClient

import src.infrastructure.db.models  # noqa: F401 — register every table on Base.metadata
from src.infrastructure.db.base import Base
from src.infrastructure.db.session import engine
from src.infrastructure.di import get_email_verification_notifier
from src.main import app

_CREDENTIALS = {"email": "user@example.com", "password": "s3cret-pass", "name": "User"}


class RecordingNotifier:
    """Captures the verification token instead of sending an email."""

    def __init__(self) -> None:
        self.sent: list[dict[str, str]] = []

    async def send_verification(self, email: str, name: str, token: str) -> None:
        self.sent.append({"email": email, "name": name, "token": token})

    @property
    def last_token(self) -> str:
        return self.sent[-1]["token"]


@pytest_asyncio.fixture(autouse=True)
async def _reset_schema():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
def notifier():
    recorder = RecordingNotifier()
    app.dependency_overrides[get_email_verification_notifier] = lambda: recorder
    yield recorder
    app.dependency_overrides.pop(get_email_verification_notifier, None)


@pytest_asyncio.fixture
async def client(notifier):  # notifier override must be installed before requests
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest_asyncio.fixture
async def registered(client, notifier):
    """A registered but NOT-yet-verified user."""
    resp = await client.post("/auth/register", json=_CREDENTIALS)
    assert resp.status_code == 201
    return {**_CREDENTIALS, "verification_token": notifier.last_token}


@pytest_asyncio.fixture
async def verified(client, registered):
    """A verified user plus a live access + refresh token pair."""
    v = await client.get("/auth/verify-email", params={"token": registered["verification_token"]})
    assert v.status_code == 200
    login = await client.post(
        "/auth/login", json={"email": _CREDENTIALS["email"], "password": _CREDENTIALS["password"]}
    )
    assert login.status_code == 200
    return {**_CREDENTIALS, **login.json()}
