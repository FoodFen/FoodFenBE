"""End-to-end auth flow via httpx.AsyncClient against the real ASGI app + DB."""

from __future__ import annotations


async def test_register_returns_token_pair(client):
    resp = await client.post(
        "/auth/register",
        json={"email": "New@Example.com", "password": "s3cret-pass", "name": "  New  "},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"] and body["refresh_token"]
    assert body["expires_in"] > 0


async def test_register_duplicate_is_409(client, registered):
    resp = await client.post(
        "/auth/register",
        json={"email": "user@example.com", "password": "another-pass", "name": "Dup"},
    )
    assert resp.status_code == 409


async def test_register_short_password_is_422(client):
    resp = await client.post(
        "/auth/register",
        json={"email": "weak@example.com", "password": "1234567", "name": "W"},
    )
    # Pydantic min_length rejects a 7-char password before it reaches the domain policy.
    assert resp.status_code == 422


async def test_login_ok_and_wrong_password_401(client, registered):
    ok = await client.post(
        "/auth/login", json={"email": "user@example.com", "password": "s3cret-pass"}
    )
    assert ok.status_code == 200
    assert ok.json()["access_token"]

    bad = await client.post(
        "/auth/login", json={"email": "user@example.com", "password": "nope-nope"}
    )
    assert bad.status_code == 401
    assert bad.headers["www-authenticate"] == "Bearer"


async def test_login_unknown_user_is_401(client):
    resp = await client.post(
        "/auth/login", json={"email": "ghost@example.com", "password": "whatever1"}
    )
    assert resp.status_code == 401


async def test_me_requires_and_accepts_token(client, registered):
    assert (await client.get("/auth/me")).status_code == 401

    resp = await client.get(
        "/auth/me", headers={"Authorization": f"Bearer {registered['access_token']}"}
    )
    assert resp.status_code == 200
    assert resp.json()["email"] == "user@example.com"


async def test_me_rejects_refresh_token_as_access(client, registered):
    resp = await client.get(
        "/auth/me", headers={"Authorization": f"Bearer {registered['refresh_token']}"}
    )
    assert resp.status_code == 401


async def test_refresh_rotates_pair_and_revokes_old(client, registered):
    first = registered["refresh_token"]

    rotated = await client.post("/auth/refresh", json={"refresh_token": first})
    assert rotated.status_code == 200
    assert rotated.json()["refresh_token"] != first

    # old refresh token no longer works
    replay = await client.post("/auth/refresh", json={"refresh_token": first})
    assert replay.status_code == 401


async def test_logout_then_refresh_401(client, registered):
    rt = registered["refresh_token"]

    out = await client.post("/auth/logout", json={"refresh_token": rt})
    assert out.status_code == 204

    resp = await client.post("/auth/refresh", json={"refresh_token": rt})
    assert resp.status_code == 401

    # logout is idempotent
    assert (await client.post("/auth/logout", json={"refresh_token": rt})).status_code == 204
