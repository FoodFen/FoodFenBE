"""POST /auth/social — end-to-end against the real app + DB.

The identity-token verifier is faked (see conftest.py) since a real Google/Apple
JWKS round-trip isn't something a test suite should depend on; the signature/
issuer/audience logic itself is covered for real in
tests/unit/test_social_identity_verifier.py.
"""

from __future__ import annotations

from src.application.dtos.auth import VerifiedIdentity


async def test_new_google_sign_in_creates_verified_passwordless_account(client, social_verifier):
    social_verifier.stub(
        "good-google-token",
        VerifiedIdentity(subject="g-1", email="new@example.com", email_verified=True),
    )

    resp = await client.post(
        "/auth/social", json={"provider": "google", "idToken": "good-google-token"}
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["accessToken"] and body["refreshToken"]
    assert body["user"]["email"] == "new@example.com"


async def test_apple_first_sign_in_uses_full_name_and_email_from_body(client, social_verifier):
    social_verifier.stub(
        "apple-token", VerifiedIdentity(subject="a-1", email=None, email_verified=False)
    )

    resp = await client.post(
        "/auth/social",
        json={
            "provider": "apple",
            "idToken": "apple-token",
            "fullName": "Ada Lovelace",
            "email": "ada@example.com",
        },
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["user"]["email"] == "ada@example.com"
    assert body["user"]["displayName"] == "Ada Lovelace"


async def test_returning_social_user_signs_into_same_account(client, social_verifier):
    social_verifier.stub(
        "good-google-token",
        VerifiedIdentity(subject="g-2", email="repeat@example.com", email_verified=True),
    )
    first = await client.post(
        "/auth/social", json={"provider": "google", "idToken": "good-google-token"}
    )
    again = await client.post(
        "/auth/social", json={"provider": "google", "idToken": "good-google-token"}
    )

    assert first.json()["user"]["id"] == again.json()["user"]["id"]


async def test_auto_links_to_existing_password_account(client, social_verifier, signed_up):
    # `signed_up` already created a password account at user@example.com.
    social_verifier.stub(
        "google-link-token",
        VerifiedIdentity(subject="g-3", email="user@example.com", email_verified=True),
    )

    resp = await client.post(
        "/auth/social", json={"provider": "google", "idToken": "google-link-token"}
    )

    assert resp.status_code == 200
    assert resp.json()["user"]["id"] == signed_up["user"]["id"]


async def test_auto_link_to_unverified_account_invalidates_its_password(
    client, social_verifier, signed_up
):
    """signed_up's account is unverified (verification is non-gating at
    sign-up) — a real Google sign-in for that same email must invalidate
    whatever password credential was on it, closing the squatted-email
    takeover vector."""
    social_verifier.stub(
        "google-link-token",
        VerifiedIdentity(subject="g-4", email="user@example.com", email_verified=True),
    )
    await client.post("/auth/social", json={"provider": "google", "idToken": "google-link-token"})

    resp = await client.post(
        "/auth/sign-in", json={"email": "user@example.com", "password": "s3cret-pass"}
    )

    assert resp.status_code == 401


async def test_bad_identity_token_is_401(client):
    resp = await client.post(
        "/auth/social", json={"provider": "google", "idToken": "not-a-real-token"}
    )
    assert resp.status_code == 401
    assert resp.json()["message"]


async def test_unsupported_provider_is_422(client):
    resp = await client.post(
        "/auth/social", json={"provider": "facebook", "idToken": "whatever"}
    )
    assert resp.status_code == 422


async def test_missing_email_everywhere_is_400(client, social_verifier):
    social_verifier.stub("no-email-token", VerifiedIdentity(subject="a-9", email=None, email_verified=False))
    resp = await client.post(
        "/auth/social", json={"provider": "apple", "idToken": "no-email-token"}
    )
    assert resp.status_code == 400


async def test_social_session_works_on_protected_endpoint(client, social_verifier):
    social_verifier.stub(
        "good-token", VerifiedIdentity(subject="g-5", email="me@example.com", email_verified=True)
    )
    session = await client.post(
        "/auth/social", json={"provider": "google", "idToken": "good-token"}
    )
    access = session.json()["accessToken"]

    me = await client.get("/auth/me", headers={"Authorization": f"Bearer {access}"})
    assert me.status_code == 200
    assert me.json()["email"] == "me@example.com"
