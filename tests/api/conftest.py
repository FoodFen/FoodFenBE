"""Shared fixtures for API tests: schema reset, HTTP client, a recording notifier."""

from __future__ import annotations

import pytest_asyncio
from httpx import ASGITransport, AsyncClient

import src.infrastructure.db.models  # noqa: F401 — register every table on Base.metadata
from src.application.dtos.auth import VerifiedIdentity
from src.domain.exceptions import InvalidTokenException
from src.infrastructure.db.base import Base
from src.infrastructure.db.session import engine
from src.infrastructure.di import (
    get_ai_chat_provider,
    get_email_verification_notifier,
    get_social_identity_verifier,
)
from src.main import app

_CREDENTIALS = {"email": "user@example.com", "password": "s3cret-pass", "displayName": "User"}


class RecordingNotifier:
    """Captures tokens instead of sending an email."""

    def __init__(self) -> None:
        self.sent: list[dict[str, str]] = []
        self.password_resets: list[dict[str, str]] = []

    async def send_verification(self, email: str, name: str | None, token: str) -> None:
        self.sent.append({"email": email, "name": name, "token": token})

    async def send_password_reset(self, email: str, name: str | None, token: str) -> None:
        self.password_resets.append({"email": email, "name": name, "token": token})

    @property
    def last_token(self) -> str:
        return self.sent[-1]["token"]

    @property
    def last_reset_token(self) -> str:
        return self.password_resets[-1]["token"]


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


class FakeSocialVerifier:
    """Maps a raw token string to a canned identity — no real Google/Apple call."""

    def __init__(self) -> None:
        self._identities: dict[str, VerifiedIdentity] = {}

    def stub(self, token: str, identity: VerifiedIdentity) -> None:
        self._identities[token] = identity

    def verify(self, provider, id_token):
        if id_token not in self._identities:
            raise InvalidTokenException("invalid identity token")
        return self._identities[id_token]


@pytest_asyncio.fixture
def social_verifier():
    fake = FakeSocialVerifier()
    app.dependency_overrides[get_social_identity_verifier] = lambda: fake
    yield fake
    app.dependency_overrides.pop(get_social_identity_verifier, None)


class FakeAiChatProvider:
    """Yields a scripted reply instead of calling a real LLM."""

    def __init__(self) -> None:
        self.deltas = ["Hello", ", world!"]

    async def stream_reply(self, history, user_message):
        for delta in self.deltas:
            yield delta


@pytest_asyncio.fixture
def ai_chat_provider():
    fake = FakeAiChatProvider()
    app.dependency_overrides[get_ai_chat_provider] = lambda: fake
    yield fake
    app.dependency_overrides.pop(get_ai_chat_provider, None)


@pytest_asyncio.fixture
async def client(notifier, social_verifier, ai_chat_provider):  # overrides before requests
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest_asyncio.fixture
async def signed_up(client, notifier):
    """A freshly signed-up user: sign-up returns a live session immediately —
    no verification step required to use the app."""
    resp = await client.post("/auth/sign-up", json=_CREDENTIALS)
    assert resp.status_code == 200
    body = resp.json()
    return {**_CREDENTIALS, **body, "verificationToken": notifier.last_token}
