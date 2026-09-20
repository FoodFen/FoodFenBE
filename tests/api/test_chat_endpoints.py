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
