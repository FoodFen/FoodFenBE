"""Shared fixtures for API tests: schema reset + HTTP client against the ASGI app."""

from __future__ import annotations

import pytest_asyncio
from httpx import ASGITransport, AsyncClient

import src.infrastructure.db.models  # noqa: F401 — register every table on Base.metadata
from src.infrastructure.db.base import Base
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


@pytest_asyncio.fixture
async def registered(client):
    """A registered user plus their fresh token pair."""
    resp = await client.post(
        "/auth/register",
        json={"email": "user@example.com", "password": "s3cret-pass", "name": "User"},
    )
    assert resp.status_code == 201
    return resp.json()
