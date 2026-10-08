"""Admin guard, moderation and dashboard. End-to-end against the real app + SQLite."""

from __future__ import annotations

from src.domain.enums import UserRole


async def test_me_carries_role_and_null_restaurant(client, make_user):
    headers, _ = await make_user("plain@example.com")
    me = (await client.get("/auth/me", headers=headers)).json()
    assert me["role"] == "user"
    assert me["restaurantId"] is None


async def test_sign_in_session_carries_role(client, make_user):
    await make_user("boss@example.com", admin=True)
    resp = await client.post("/auth/sign-in", json={"email": "boss@example.com", "password": "s3cret-pass"})
    assert resp.json()["user"]["role"] == "admin"


async def test_non_admin_is_forbidden(client, make_user):
    headers, _ = await make_user("plain@example.com")
    resp = await client.get("/admin/restaurants", headers=headers)
    assert resp.status_code == 403
    assert "message" in resp.json()


async def test_admin_routes_need_a_token(client):
    assert (await client.get("/admin/restaurants")).status_code == 401


async def test_demoted_admin_is_forbidden_immediately(client, make_user, set_role):
    headers, user_id = await make_user("boss@example.com", admin=True)
    assert (await client.get("/admin/restaurants", headers=headers)).status_code == 200
    await set_role(user_id, UserRole.USER)
    assert (await client.get("/admin/restaurants", headers=headers)).status_code == 403
