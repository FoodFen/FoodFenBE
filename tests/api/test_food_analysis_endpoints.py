"""POST /ai/food/analyze-image|analyze-text — end-to-end against the real app.

The Gemini call and Cloudinary upload are faked (see `food_vision_provider` /
`image_storage` in conftest.py) — neither is something a test suite should
depend on.
"""

from __future__ import annotations


async def test_analyze_image_uploads_and_returns_suggestion(client, signed_up):
    headers = {"Authorization": f"Bearer {signed_up['accessToken']}"}

    resp = await client.post(
        "/ai/food/analyze-image",
        headers=headers,
        files={"image": ("meal.jpg", b"fake-jpeg-bytes", "image/jpeg")},
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["mealName"] == "Pho"
    assert body["ingredients"][0]["name"] == "beef"
    assert body["ingredients"][0]["fiberG"] is None
    assert body["imageUrl"] == "https://cdn.example/meal.jpg"


async def test_analyze_image_rejects_unsupported_content_type(client, signed_up):
    headers = {"Authorization": f"Bearer {signed_up['accessToken']}"}

    resp = await client.post(
        "/ai/food/analyze-image",
        headers=headers,
        files={"image": ("meal.gif", b"gif-bytes", "image/gif")},
    )

    assert resp.status_code == 400


async def test_analyze_image_requires_auth(client):
    resp = await client.post(
        "/ai/food/analyze-image", files={"image": ("meal.jpg", b"bytes", "image/jpeg")}
    )
    assert resp.status_code == 401


async def test_analyze_text_returns_suggestion_with_no_image_url(client, signed_up):
    headers = {"Authorization": f"Bearer {signed_up['accessToken']}"}

    resp = await client.post(
        "/ai/food/analyze-text",
        json={"description": "a bowl of beef pho"},
        headers=headers,
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["mealName"] == "Pho"
    assert body["imageUrl"] is None


async def test_analyze_text_rejects_empty_description(client, signed_up):
    headers = {"Authorization": f"Bearer {signed_up['accessToken']}"}

    resp = await client.post(
        "/ai/food/analyze-text", json={"description": ""}, headers=headers
    )

    assert resp.status_code == 422


async def test_analyze_text_requires_auth(client):
    resp = await client.post("/ai/food/analyze-text", json={"description": "pho"})
    assert resp.status_code == 401
