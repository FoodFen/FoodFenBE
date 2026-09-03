"""End-to-end auth flow via httpx.AsyncClient against the real ASGI app + DB."""

from __future__ import annotations

_CREDS = {"email": "user@example.com", "password": "s3cret-pass"}


async def test_register_creates_pending_account_and_queues_email(client, notifier):
    resp = await client.post(
        "/auth/register",
        json={"email": "New@Example.com", "password": "s3cret-pass", "name": "  New  "},
    )
    assert resp.status_code == 201
    assert "access_token" not in resp.json()
    assert resp.json()["detail"].lower().startswith("account created")
    # background task ran before the response fully completed
    assert notifier.sent[-1]["email"] == "new@example.com"
    assert notifier.last_token


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
    assert resp.status_code == 422


async def test_login_before_verification_is_403(client, registered):
    resp = await client.post("/auth/login", json=_CREDS)
    assert resp.status_code == 403
    assert "confirm your email" in resp.json()["detail"].lower()


async def test_verify_then_login_succeeds(client, registered):
    v = await client.get(
        "/auth/verify-email", params={"token": registered["verification_token"]}
    )
    assert v.status_code == 200

    login = await client.post("/auth/login", json=_CREDS)
    assert login.status_code == 200
    assert login.json()["access_token"]


async def test_verify_is_idempotent(client, registered):
    params = {"token": registered["verification_token"]}
    assert (await client.get("/auth/verify-email", params=params)).status_code == 200
    assert (await client.get("/auth/verify-email", params=params)).status_code == 200


async def test_verify_with_garbage_token_is_401(client):
    resp = await client.get("/auth/verify-email", params={"token": "not-a-jwt"})
    assert resp.status_code == 401


async def test_resend_verification_always_202_and_reissues(client, registered, notifier):
    before = len(notifier.sent)

    r = await client.post("/auth/resend-verification", json={"email": "user@example.com"})
    assert r.status_code == 202
    assert len(notifier.sent) == before + 1

    # unknown address: still 202, nothing queued
    r = await client.post("/auth/resend-verification", json={"email": "ghost@example.com"})
    assert r.status_code == 202
    assert len(notifier.sent) == before + 1

    # the freshly resent token verifies
    v = await client.get("/auth/verify-email", params={"token": notifier.last_token})
    assert v.status_code == 200


async def test_resend_after_verified_queues_nothing(client, verified, notifier):
    before = len(notifier.sent)
    r = await client.post("/auth/resend-verification", json={"email": "user@example.com"})
    assert r.status_code == 202
    assert len(notifier.sent) == before


async def test_login_wrong_password_is_401(client, verified):
    resp = await client.post(
        "/auth/login", json={"email": "user@example.com", "password": "nope-nope"}
    )
    assert resp.status_code == 401
    assert resp.headers["www-authenticate"] == "Bearer"


async def test_login_unknown_user_is_401(client):
    resp = await client.post(
        "/auth/login", json={"email": "ghost@example.com", "password": "whatever1"}
    )
    assert resp.status_code == 401


async def test_me_requires_and_accepts_token(client, verified):
    assert (await client.get("/auth/me")).status_code == 401

    resp = await client.get(
        "/auth/me", headers={"Authorization": f"Bearer {verified['access_token']}"}
    )
    assert resp.status_code == 200
    assert resp.json()["email"] == "user@example.com"


async def test_me_rejects_refresh_token_as_access(client, verified):
    resp = await client.get(
        "/auth/me", headers={"Authorization": f"Bearer {verified['refresh_token']}"}
    )
    assert resp.status_code == 401


async def test_refresh_rotates_pair_and_revokes_old(client, verified):
    first = verified["refresh_token"]

    rotated = await client.post("/auth/refresh", json={"refresh_token": first})
    assert rotated.status_code == 200
    assert rotated.json()["refresh_token"] != first

    replay = await client.post("/auth/refresh", json={"refresh_token": first})
    assert replay.status_code == 401


async def test_logout_then_refresh_401(client, verified):
    rt = verified["refresh_token"]
    assert (await client.post("/auth/logout", json={"refresh_token": rt})).status_code == 204
    assert (await client.post("/auth/refresh", json={"refresh_token": rt})).status_code == 401
    assert (await client.post("/auth/logout", json={"refresh_token": rt})).status_code == 204
