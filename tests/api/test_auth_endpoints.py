"""End-to-end auth flow via httpx.AsyncClient against the real ASGI app + DB.

Endpoint names/shapes follow the front-end API contract: sign-up, sign-in,
refresh, sign-out, password-reset, all camelCase JSON. verify-email,
resend-verification, and reset-password are extras beyond that contract.
"""

from __future__ import annotations

_CREDS = {"email": "user@example.com", "password": "s3cret-pass"}


def _auth(session: dict) -> dict:
    return {"Authorization": f"Bearer {session['accessToken']}"}


async def test_sign_up_returns_live_session_immediately(client, notifier):
    resp = await client.post(
        "/auth/sign-up",
        json={"email": "New@Example.com", "password": "s3cret-pass", "displayName": "  New  "},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["accessToken"] and body["refreshToken"]
    assert isinstance(body["expiresAt"], int) and body["expiresAt"] > 0
    assert body["user"]["email"] == "new@example.com"
    assert body["user"]["displayName"] == "New"
    assert isinstance(body["user"]["id"], int)
    # a verification email still went out, just doesn't gate anything
    assert notifier.sent[-1]["email"] == "new@example.com"


async def test_sign_up_is_committed_before_the_background_email_runs(client, notifier):
    # In-memory SQLite shares one connection, so a second session would see uncommitted rows;
    # record the order of COMMIT vs. send instead.
    from sqlalchemy import event

    from src.infrastructure.db.session import engine

    order: list[str] = []
    record_commit = lambda _conn: order.append("commit")  # noqa: E731
    event.listen(engine.sync_engine, "commit", record_commit)
    original_send = notifier.send_verification

    async def send(email, name, token):
        order.append("send")
        await original_send(email, name, token)

    notifier.send_verification = send
    try:
        resp = await client.post("/auth/sign-up", json=_CREDS)
    finally:
        event.remove(engine.sync_engine, "commit", record_commit)

    assert resp.status_code == 200
    assert order == ["commit", "send"]


async def test_sign_up_without_display_name(client):
    resp = await client.post(
        "/auth/sign-up", json={"email": "noname@example.com", "password": "s3cret-pass"}
    )
    assert resp.status_code == 200
    assert resp.json()["user"]["displayName"] is None


async def test_sign_up_duplicate_email_is_validation_failure(client, signed_up):
    resp = await client.post(
        "/auth/sign-up",
        json={"email": "user@example.com", "password": "another-pass"},
    )
    assert resp.status_code == 400
    body = resp.json()
    assert "email" in body["errors"]
    assert body["message"]


async def test_sign_up_short_password_is_422_with_errors_shape(client):
    resp = await client.post(
        "/auth/sign-up", json={"email": "weak@example.com", "password": "1234567"}
    )
    assert resp.status_code == 422
    body = resp.json()
    assert "message" in body
    assert "errors" in body


async def test_sign_in_ok_and_wrong_password(client, signed_up):
    ok = await client.post("/auth/sign-in", json=_CREDS)
    assert ok.status_code == 200
    assert ok.json()["accessToken"]
    assert ok.json()["user"]["id"] == signed_up["user"]["id"]

    bad = await client.post(
        "/auth/sign-in", json={"email": "user@example.com", "password": "nope-nope"}
    )
    assert bad.status_code == 401
    assert bad.json()["message"]


async def test_sign_in_unknown_user_is_401(client):
    resp = await client.post(
        "/auth/sign-in", json={"email": "ghost@example.com", "password": "whatever1"}
    )
    assert resp.status_code == 401


async def test_me_requires_and_accepts_token(client, signed_up):
    assert (await client.get("/auth/me")).status_code == 401

    resp = await client.get("/auth/me", headers=_auth(signed_up))
    assert resp.status_code == 200
    assert resp.json()["email"] == "user@example.com"
    assert resp.json()["id"] == signed_up["user"]["id"]


async def test_swagger_token_endpoint_uses_oauth2_snake_case_shape(client, signed_up):
    """Regression: this response must NOT go through CamelModel — Swagger's
    Authorize dialog reads `access_token` (snake_case, OAuth2 spec) literally
    off the JSON body, and a camelCase `accessToken` leaves it as "undefined"."""
    resp = await client.post(
        "/auth/token",
        data={"username": "user@example.com", "password": "s3cret-pass"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["access_token"]
    assert "accessToken" not in body

    me = await client.get("/auth/me", headers={"Authorization": f"Bearer {body['access_token']}"})
    assert me.status_code == 200


async def test_me_rejects_refresh_token_as_access(client, signed_up):
    resp = await client.get(
        "/auth/me", headers={"Authorization": f"Bearer {signed_up['refreshToken']}"}
    )
    assert resp.status_code == 401


async def test_refresh_returns_full_session_and_rotates(client, signed_up):
    first = signed_up["refreshToken"]

    rotated = await client.post("/auth/refresh", json={"refreshToken": first})
    assert rotated.status_code == 200
    body = rotated.json()
    assert body["refreshToken"] != first
    assert body["user"]["id"] == signed_up["user"]["id"]  # AuthSession always carries the user

    # old refresh token no longer works
    replay = await client.post("/auth/refresh", json={"refreshToken": first})
    assert replay.status_code == 401


async def test_sign_out_requires_auth(client, signed_up):
    # not in the skipAuth list: a bearer token is required even though the
    # payload is just the refresh token.
    no_auth = await client.post(
        "/auth/sign-out", json={"refreshToken": signed_up["refreshToken"]}
    )
    assert no_auth.status_code == 401


async def test_sign_out_then_refresh_401(client, signed_up):
    rt = signed_up["refreshToken"]

    out = await client.post(
        "/auth/sign-out", json={"refreshToken": rt}, headers=_auth(signed_up)
    )
    assert out.status_code == 204

    resp = await client.post("/auth/refresh", json={"refreshToken": rt})
    assert resp.status_code == 401

    # idempotent
    again = await client.post(
        "/auth/sign-out", json={"refreshToken": rt}, headers=_auth(signed_up)
    )
    assert again.status_code == 204


async def test_password_reset_always_2xx_and_enumeration_safe(client, signed_up, notifier):
    known = await client.post("/auth/password-reset", json={"email": "user@example.com"})
    assert known.status_code == 202
    assert notifier.password_resets[-1]["email"] == "user@example.com"

    before = len(notifier.password_resets)
    unknown = await client.post("/auth/password-reset", json={"email": "ghost@example.com"})
    assert unknown.status_code == 202
    assert unknown.json() == known.json()  # identical body either way
    assert len(notifier.password_resets) == before  # nothing queued for the unknown address


async def test_reset_password_then_sign_in_with_new_password(client, signed_up, notifier):
    await client.post("/auth/password-reset", json={"email": "user@example.com"})
    token = notifier.last_reset_token

    resp = await client.post(
        "/auth/reset-password", json={"token": token, "newPassword": "newpassword1"}
    )
    assert resp.status_code == 200

    old = await client.post("/auth/sign-in", json=_CREDS)
    assert old.status_code == 401

    new = await client.post(
        "/auth/sign-in", json={"email": "user@example.com", "password": "newpassword1"}
    )
    assert new.status_code == 200


async def test_reset_token_is_single_use(client, signed_up, notifier):
    await client.post("/auth/password-reset", json={"email": "user@example.com"})
    token = notifier.last_reset_token

    first = await client.post(
        "/auth/reset-password", json={"token": token, "newPassword": "newpassword1"}
    )
    assert first.status_code == 200
    replay = await client.post(
        "/auth/reset-password", json={"token": token, "newPassword": "attacker-pass1"}
    )
    assert replay.status_code == 401

    still_new = await client.post(
        "/auth/sign-in", json={"email": "user@example.com", "password": "newpassword1"}
    )
    assert still_new.status_code == 200


async def test_reset_password_revokes_existing_sessions(client, signed_up, notifier):
    await client.post("/auth/password-reset", json={"email": "user@example.com"})
    await client.post(
        "/auth/reset-password",
        json={"token": notifier.last_reset_token, "newPassword": "newpassword1"},
    )

    resp = await client.post("/auth/refresh", json={"refreshToken": signed_up["refreshToken"]})
    assert resp.status_code == 401


# --- extras: not part of the front-end contract -----------------------------


async def test_verify_email_then_idempotent(client, signed_up):
    token = signed_up["verificationToken"]
    first = await client.get("/auth/verify-email", params={"token": token})
    assert first.status_code == 200
    second = await client.get("/auth/verify-email", params={"token": token})
    assert second.status_code == 200


async def test_verify_email_bad_token_is_401(client):
    resp = await client.get("/auth/verify-email", params={"token": "not-a-jwt"})
    assert resp.status_code == 401


async def test_resend_verification_always_202(client, signed_up, notifier):
    before = len(notifier.sent)
    resp = await client.post(
        "/auth/resend-verification", json={"email": "user@example.com"}
    )
    assert resp.status_code == 202
    assert len(notifier.sent) == before + 1

    unknown = await client.post(
        "/auth/resend-verification", json={"email": "ghost@example.com"}
    )
    assert unknown.status_code == 202
    assert len(notifier.sent) == before + 1


async def test_auth_endpoints_are_rate_limited_per_ip(client, monkeypatch):
    from src.infrastructure.di import security

    monkeypatch.setattr(security._auth_ip_limiter, "limit", 2)
    body = {"email": "nobody@example.com", "password": "wrong-pass-1"}

    assert (await client.post("/auth/sign-in", json=body)).status_code == 401
    assert (await client.post("/auth/sign-in", json=body)).status_code == 401
    resp = await client.post("/auth/sign-in", json=body)

    assert resp.status_code == 429
    assert resp.json()["message"] == "too many requests, try again later"


async def test_rate_limit_ignores_client_supplied_forwarded_for(client, monkeypatch):
    """Only the last hop (appended by our own proxy) is trusted; a client can't dodge the limit
    by prepending fake X-Forwarded-For entries."""
    from src.infrastructure.di import security

    monkeypatch.setattr(security._auth_ip_limiter, "limit", 2)
    body = {"email": "nobody@example.com", "password": "wrong-pass-1"}

    chains = ["6.6.6.1, 10.0.0.1", "6.6.6.2, 10.0.0.1", "6.6.6.3, 10.0.0.1", "6.6.6.4, 10.0.0.2"]
    statuses = [
        (await client.post("/auth/sign-in", json=body, headers={"X-Forwarded-For": chain})).status_code
        for chain in chains
    ]

    # Spoofed leading entries don't help the same real client (3rd -> 429); a different real
    # client (10.0.0.2) still has its own budget.
    assert statuses == [401, 401, 429, 401]


async def test_failing_email_delivery_does_not_undo_sign_up(client, monkeypatch):
    """The mail runs as a background task *inside* the request's DB-session scope; if delivery
    raises, the sign-up transaction must still commit."""
    from src.infrastructure.di import get_email_verification_notifier
    from src.infrastructure.notifications.email_verification_notifier import (
        SmtpEmailVerificationNotifier,
    )
    from src.main import app

    def _unreachable(self, message):
        raise OSError("Network is unreachable")

    monkeypatch.setattr(SmtpEmailVerificationNotifier, "_deliver", _unreachable)
    smtp = SmtpEmailVerificationNotifier(
        base_url="http://x", sender="a@b.c", host="h", port=25, username="", password="",
        starttls=False,
    )
    app.dependency_overrides[get_email_verification_notifier] = lambda: smtp
    creds = {"email": "mail@example.com", "password": "s3cret-pass"}

    assert (await client.post("/auth/sign-up", json=creds)).status_code == 200
    assert (await client.post("/auth/sign-in", json=creds)).status_code == 200
