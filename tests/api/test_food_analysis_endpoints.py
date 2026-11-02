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


async def test_analyze_image_accepts_language(client, signed_up):
    headers = {"Authorization": f"Bearer {signed_up['accessToken']}"}

    resp = await client.post(
        "/ai/food/analyze-image",
        headers=headers,
        files={"image": ("meal.jpg", b"fake-jpeg-bytes", "image/jpeg")},
        data={"language": "en"},
    )

    assert resp.status_code == 200


async def test_analyze_image_rejects_invalid_language(client, signed_up):
    headers = {"Authorization": f"Bearer {signed_up['accessToken']}"}

    resp = await client.post(
        "/ai/food/analyze-image",
        headers=headers,
        files={"image": ("meal.jpg", b"fake-jpeg-bytes", "image/jpeg")},
        data={"language": "fr"},
    )

    assert resp.status_code == 422


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


async def test_analyze_text_rejects_invalid_language(client, signed_up):
    headers = {"Authorization": f"Bearer {signed_up['accessToken']}"}

    resp = await client.post(
        "/ai/food/analyze-text",
        json={"description": "pho", "language": "fr"},
        headers=headers,
    )

    assert resp.status_code == 422


async def test_analyze_text_rejects_empty_description(client, signed_up):
    headers = {"Authorization": f"Bearer {signed_up['accessToken']}"}

    resp = await client.post(
        "/ai/food/analyze-text", json={"description": ""}, headers=headers
    )

    assert resp.status_code == 422


async def test_analyze_text_requires_auth(client):
    resp = await client.post("/ai/food/analyze-text", json={"description": "pho"})
    assert resp.status_code == 401


async def test_analyze_text_rejects_over_long_description(client, signed_up):
    headers = {"Authorization": f"Bearer {signed_up['accessToken']}"}

    resp = await client.post(
        "/ai/food/analyze-text", json={"description": "x" * 1001}, headers=headers
    )

    assert resp.status_code == 422


async def test_analyze_image_rejects_oversized_upload(client, signed_up):
    headers = {"Authorization": f"Bearer {signed_up['accessToken']}"}
    too_big = b"0" * (15 * 1024 * 1024 + 1)

    resp = await client.post(
        "/ai/food/analyze-image",
        headers=headers,
        files={"image": ("meal.jpg", too_big, "image/jpeg")},
    )

    assert resp.status_code == 400


async def _insert_pho_bo() -> None:
    from datetime import UTC, datetime
    from uuid import uuid4

    from src.domain.enums import FoodCategory, FoodSourceKind
    from src.infrastructure.db.models.food_model import FoodORM
    from src.infrastructure.db.session import SessionLocal

    now = datetime.now(UTC)
    async with SessionLocal() as session:
        session.add(FoodORM(
            id=uuid4(), slug="pho-bo", name="Phở bò", aliases=["pho"],
            category=FoodCategory.MON_NUOC, source_kind=FoodSourceKind.NIN, source_ref="nin:1",
            kcal=81, carbs_g=10.2, protein_g=4.5, fat_g=2.4, fiber_g=0.2,
            servings=[{"label": "1 tô", "grams": 550, "default": True}],
            archived=False, created_at=now, updated_at=now, updated_by_admin_id=None,
        ))
        await session.commit()


def _model_row(name: str, catalog_food_id: str):
    from src.application.dtos.food_analysis import IngredientSuggestionDTO

    return IngredientSuggestionDTO(
        name=name, quantity_g=550.0, kcal=999, carbs_g=1.0, protein_g=1.0, fat_g=1.0,
        fiber_g=None, confidence=0.8, catalog_food_id=catalog_food_id,
    )


async def test_analyze_text_grounds_catalog_rows_and_leaves_unknown_ones(
    client, signed_up, food_vision_provider
):
    await _insert_pho_bo()
    food_vision_provider.result = food_vision_provider.result.__class__(
        meal_name="Pho",
        ingredients=[_model_row("pho", "pho-bo"), _model_row("mystery", "not-in-catalog")],
        image_url=None,
    )
    headers = {"Authorization": f"Bearer {signed_up['accessToken']}"}

    resp = await client.post(
        "/ai/food/analyze-text", json={"description": "pho"}, headers=headers
    )

    assert resp.status_code == 200
    grounded, ungrounded = resp.json()["ingredients"]
    assert grounded == {
        "name": "pho", "quantityG": 550.0, "kcal": 446, "carbsG": 56.1, "proteinG": 24.8,
        "fatG": 13.2, "fiberG": 1.1, "confidence": 0.8,
        "catalogFoodId": "pho-bo", "catalogName": "Phở bò", "verified": True,
        "sourceRef": "nin:1",
        "per100g": {"kcal": 81, "carbsG": 10.2, "proteinG": 4.5, "fatG": 2.4, "fiberG": 0.2},
    }
    assert ungrounded == {
        "name": "mystery", "quantityG": 550.0, "kcal": 999, "carbsG": 1.0, "proteinG": 1.0,
        "fatG": 1.0, "fiberG": None, "confidence": 0.8,
        "catalogFoodId": None, "catalogName": None, "verified": False, "sourceRef": None,
        "per100g": None,
    }
