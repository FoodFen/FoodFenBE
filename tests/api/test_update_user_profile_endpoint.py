"""PATCH /users/me — end-to-end against the real app."""

from __future__ import annotations


async def test_patch_updates_only_the_sent_field(client, signed_up):
    headers = {"Authorization": f"Bearer {signed_up['accessToken']}"}

    resp = await client.patch("/users/me", json={"height": 180.0}, headers=headers)

    assert resp.status_code == 200
    body = resp.json()
    assert body["height"] == 180.0
    assert body["displayName"] == signed_up["displayName"]  # untouched


async def test_patch_requires_auth(client):
    resp = await client.patch("/users/me", json={"height": 180.0})
    assert resp.status_code == 401


async def test_patch_rejects_subscription_tier(client, signed_up):
    headers = {"Authorization": f"Bearer {signed_up['accessToken']}"}

    resp = await client.patch(
        "/users/me", json={"subscriptionTier": "premium"}, headers=headers
    )

    assert resp.status_code == 422


async def test_patch_display_name_updates_the_domain_name_field(client, signed_up):
    headers = {"Authorization": f"Bearer {signed_up['accessToken']}"}

    resp = await client.patch("/users/me", json={"displayName": "New Name"}, headers=headers)

    assert resp.status_code == 200
    assert resp.json()["displayName"] == "New Name"


async def test_patch_email_collision_returns_400_with_field_error(client, signed_up):
    headers = {"Authorization": f"Bearer {signed_up['accessToken']}"}
    await client.post(
        "/auth/sign-up",
        json={"email": "taken@example.com", "password": "s3cret-pass", "displayName": "Taken"},
    )

    resp = await client.patch("/users/me", json={"email": "taken@example.com"}, headers=headers)

    assert resp.status_code == 400
    assert "email" in resp.json()["errors"]
