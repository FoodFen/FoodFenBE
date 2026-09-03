"""End-to-end API tests via httpx.AsyncClient against the ASGI app.

Uses the app's own engine (DATABASE_URL / .env); schema is reset per test.
"""

from __future__ import annotations

import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from src.infrastructure.db.base import Base
from src.infrastructure.db.models.user_model import UserORM  # noqa: F401 — registers the table
from src.infrastructure.db.session import engine
from src.main import app


@pytest_asyncio.fixture(autouse=True)
async def _reset_schema():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def test_create_then_get_user(client):
    resp = await client.post("/users", json={"email": "api@example.com", "name": "Api User"})
    assert resp.status_code == 201
    body = resp.json()
    assert body["email"] == "api@example.com"
    assert body["is_active"] is True

    got = await client.get(f"/users/{body['id']}")
    assert got.status_code == 200
    assert got.json()["id"] == body["id"]


async def test_get_missing_user_returns_404(client):
    resp = await client.get("/users/00000000-0000-0000-0000-000000000000")
    assert resp.status_code == 404


async def test_duplicate_email_returns_409(client):
    await client.post("/users", json={"email": "dupe@example.com", "name": "A"})
    resp = await client.post("/users", json={"email": "dupe@example.com", "name": "B"})
    assert resp.status_code == 409


async def test_invalid_email_returns_400(client):
    resp = await client.post("/users", json={"email": "bad", "name": "A"})
    assert resp.status_code == 400
