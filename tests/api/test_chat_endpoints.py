"""GET/POST /chat/messages — end-to-end against the real app + DB.

The LLM call is faked (see `ai_chat_provider` in conftest.py) — a real Gemini
round-trip isn't something a test suite should depend on.
"""

from __future__ import annotations


def _parse_sse(body: str) -> list[tuple[str, dict]]:
    import json

    frames = []
    for chunk in body.strip().split("\n\n"):
        lines = chunk.splitlines()
        event = lines[0].removeprefix("event: ")
        data = json.loads(lines[1].removeprefix("data: "))
        frames.append((event, data))
    return frames


async def test_send_message_streams_tokens_then_done(client, signed_up):
    headers = {"Authorization": f"Bearer {signed_up['accessToken']}"}

    resp = await client.post("/chat/messages", json={"message": "hi"}, headers=headers)

    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/event-stream")
    frames = _parse_sse(resp.text)
    assert [f[0] for f in frames] == ["token", "token", "done"]
    assert frames[0][1] == {"delta": "Hello"}
    assert frames[2][1]["message"]["role"] == "assistant"
    assert frames[2][1]["message"]["content"] == "Hello, world!"


async def test_send_message_requires_auth(client):
    resp = await client.post("/chat/messages", json={"message": "hi"})
    assert resp.status_code == 401


async def test_sent_messages_appear_in_history(client, signed_up):
    headers = {"Authorization": f"Bearer {signed_up['accessToken']}"}
    await client.post("/chat/messages", json={"message": "hi"}, headers=headers)

    resp = await client.get("/chat/messages", headers=headers)

    assert resp.status_code == 200
    body = resp.json()
    roles = [m["role"] for m in body["messages"]]
    assert roles == ["assistant", "user"]  # newest-first
    assert body["messages"][1]["content"] == "hi"
    assert body["nextCursor"] is None


async def test_history_paginates_with_cursor(client, signed_up):
    headers = {"Authorization": f"Bearer {signed_up['accessToken']}"}
    for i in range(3):
        await client.post("/chat/messages", json={"message": f"msg-{i}"}, headers=headers)

    first = await client.get("/chat/messages?limit=2", headers=headers)
    assert first.status_code == 200
    first_body = first.json()
    assert len(first_body["messages"]) == 2
    assert first_body["nextCursor"] is not None

    second = await client.get(
        "/chat/messages",
        params={"limit": 2, "before": first_body["nextCursor"]},
        headers=headers,
    )
    assert second.status_code == 200
    second_body = second.json()
    assert len(second_body["messages"]) == 2

    seen_ids = {m["id"] for m in first_body["messages"]} | {m["id"] for m in second_body["messages"]}
    assert len(seen_ids) == 4  # no duplicate across the page boundary


async def test_send_message_rejects_over_long_message(client, signed_up):
    headers = {"Authorization": f"Bearer {signed_up['accessToken']}"}

    resp = await client.post("/chat/messages", json={"message": "x" * 2001}, headers=headers)

    assert resp.status_code == 422


async def test_chat_is_rate_limited_per_user(client, signed_up, monkeypatch):
    from src.infrastructure.di import security

    monkeypatch.setattr(security._chat_user_limiter, "limit", 1)
    headers = {"Authorization": f"Bearer {signed_up['accessToken']}"}

    assert (await client.post("/chat/messages", json={"message": "hi"}, headers=headers)).status_code == 200
    resp = await client.post("/chat/messages", json={"message": "hi"}, headers=headers)

    assert resp.status_code == 429


_MEAL = {
    "name": "Pho bo",
    "inputMethod": "manual",
    "totalKcal": 450,
    "carbsG": 60.0,
    "proteinG": 25.0,
    "fatG": 12.0,
    "mealType": "breakfast",
    "clientId": "meal_1",
    "loggedOn": "2026-10-04",
}


async def test_chat_context_includes_the_users_own_meals_for_the_client_date(
    client, signed_up, ai_chat_provider
):
    headers = {"Authorization": f"Bearer {signed_up['accessToken']}"}
    assert (await client.post("/food-entries", json=_MEAL, headers=headers)).status_code in (200, 201)

    resp = await client.post(
        "/chat/messages", json={"message": "am I eating ok?", "date": "2026-10-04"}, headers=headers
    )

    assert resp.status_code == 200
    assert "MEALS TODAY (2026-10-04)" in ai_chat_provider.last_context
    assert "Pho bo" in ai_chat_provider.last_context


async def test_chat_context_excludes_other_users_meals(client, signed_up, ai_chat_provider):
    owner = {"Authorization": f"Bearer {signed_up['accessToken']}"}
    assert (await client.post("/food-entries", json=_MEAL, headers=owner)).status_code in (200, 201)

    other = await client.post(
        "/auth/sign-up",
        json={"email": "other@example.com", "password": "another-pass-123", "displayName": "Other"},
    )
    assert other.status_code == 200
    other_headers = {"Authorization": f"Bearer {other.json()['accessToken']}"}

    resp = await client.post(
        "/chat/messages", json={"message": "hi", "date": "2026-10-04"}, headers=other_headers
    )

    assert resp.status_code == 200
    assert "Pho bo" not in ai_chat_provider.last_context


async def test_chat_rejects_a_malformed_date(client, signed_up):
    headers = {"Authorization": f"Bearer {signed_up['accessToken']}"}

    resp = await client.post("/chat/messages", json={"message": "hi", "date": "yesterday"}, headers=headers)

    assert resp.status_code == 422


async def test_chat_rejects_an_out_of_range_date(client, signed_up):
    headers = {"Authorization": f"Bearer {signed_up['accessToken']}"}

    resp = await client.post("/chat/messages", json={"message": "hi", "date": "0001-01-02"}, headers=headers)

    assert resp.status_code == 422


async def _public_dish(client, make_user, restaurant_body, dish_body, admin):
    """An approved dish of an approved restaurant; returns its id."""
    owner, _ = await make_user("owner@example.com")
    r = (await client.post("/restaurants", json=restaurant_body, headers=owner)).json()
    await client.post(f"/admin/restaurants/{r['id']}/review", json={"decision": "approved"}, headers=admin)
    d = (await client.post("/restaurants/mine/dishes", json=dish_body, headers=owner)).json()
    await client.post(f"/admin/dishes/{d['id']}/review", json={"decision": "approved"}, headers=admin)
    return d["id"]


async def test_fen_dish_cards_are_hydrated_and_markers_never_reach_the_client(
    client, make_user, restaurant_body, dish_body, ai_chat_provider
):
    admin, _ = await make_user("admin@example.com", admin=True)
    dish_id = await _public_dish(client, make_user, restaurant_body, dish_body, admin)
    reader, _ = await make_user("reader@example.com")
    unknown = "00000000-0000-0000-0000-000000000abc"
    ai_chat_provider.deltas = ["Hãy thử phở bò [[di", f"sh:{dish_id}]]", f" nhé [[dish:{unknown}]]!"]

    resp = await client.post("/chat/messages", json={"message": "gợi ý"}, headers=reader)

    frames = _parse_sse(resp.text)
    assert "[[" not in resp.text and "dish:" not in "".join(f["delta"] for e, f in frames if e == "token")
    message = frames[-1][1]["message"]
    assert frames[-1][0] == "done" and message["content"] == "Hãy thử phở bò  nhé !"
    [card] = message["dishes"]
    assert card["id"] == dish_id and card["name"] == "Phở bò" and card["dietTag"] == "none"
    assert card["restaurant"]["name"] == "Quán Ngon"
    assert "fits" not in card and "reasons" not in card

    history = (await client.get("/chat/messages", headers=reader)).json()["messages"]
    assert [m["id"] for m in history[0]["dishes"]] == [dish_id] and history[1]["dishes"] == []

    # unpublished after the reply -> the card disappears from history
    await client.post(
        f"/admin/dishes/{dish_id}/review", json={"decision": "rejected", "reason": "no"}, headers=admin
    )
    history = (await client.get("/chat/messages", headers=reader)).json()["messages"]
    assert history[0]["dishes"] == []


async def test_ordinary_messages_have_empty_dishes(client, signed_up):
    headers = {"Authorization": f"Bearer {signed_up['accessToken']}"}

    resp = await client.post("/chat/messages", json={"message": "hi"}, headers=headers)

    assert _parse_sse(resp.text)[-1][1]["message"]["dishes"] == []
    assert all(m["dishes"] == [] for m in (await client.get("/chat/messages", headers=headers)).json()["messages"])


async def test_context_lists_public_dishes_and_omits_the_section_without_any(
    client, make_user, restaurant_body, dish_body, ai_chat_provider
):
    reader, _ = await make_user("reader@example.com")
    await client.post("/chat/messages", json={"message": "hi"}, headers=reader)
    assert "DISHES" not in ai_chat_provider.last_context

    admin, _ = await make_user("admin@example.com", admin=True)
    dish_id = await _public_dish(client, make_user, restaurant_body, dish_body, admin)
    await client.post("/chat/messages", json={"message": "hi"}, headers=reader)

    assert "DISHES" in ai_chat_provider.last_context and dish_id in ai_chat_provider.last_context
