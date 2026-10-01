"""Anonymous / free-tier AI trial: 3 successful analyses per input method, then 403."""

from __future__ import annotations

import dataclasses

import pytest
from sqlalchemy import update

from src.infrastructure.db.models import UserORM
from src.infrastructure.db.session import SessionLocal
from src.infrastructure.di import security

_JPEG = {"image": ("meal.jpg", b"fake-jpeg-bytes", "image/jpeg")}


@pytest.fixture(autouse=True)
def _fresh_ip_limiter():
    security._anon_ip_limiter.hits.clear()
    yield
    security._anon_ip_limiter.hits.clear()


def _device(device_id: str = "device-aaaaaaaa") -> dict[str, str]:
    return {"X-Device-Id": device_id}


async def _image(client, headers):
    return await client.post("/ai/food/analyze-image", headers=headers, files=_JPEG)


async def _text(client, headers, method: str = "text"):
    return await client.post(
        "/ai/food/analyze-text",
        headers=headers,
        json={"description": "a bowl of beef pho", "inputMethod": method},
    )


async def test_anonymous_device_can_analyze_three_times_then_403(client):
    for _ in range(3):
        assert (await _image(client, _device())).status_code == 200

    resp = await _image(client, _device())

    assert resp.status_code == 403
    body = resp.json()
    assert body["code"] == "ai_trial_exhausted"
    assert body["inputMethod"] == "image"


async def test_anonymous_without_device_id_is_401(client):
    assert (await _image(client, {})).status_code == 401


async def test_counters_are_independent_per_input_method(client):
    for _ in range(3):
        await _image(client, _device())

    assert (await _text(client, _device())).status_code == 200
    for _ in range(2):
        await _text(client, _device())
    exhausted = await _text(client, _device())
    assert exhausted.status_code == 403
    assert exhausted.json()["inputMethod"] == "text"

    # voice shares the endpoint with text but has its own counter
    assert (await _text(client, _device(), "voice")).status_code == 200


async def test_other_device_has_its_own_trials(client):
    for _ in range(3):
        await _image(client, _device("device-aaaaaaaa"))

    assert (await _image(client, _device("device-bbbbbbbb"))).status_code == 200


async def test_empty_result_does_not_consume_a_trial(client, food_vision_provider):
    empty = dataclasses.replace(food_vision_provider.result, ingredients=[])
    real = food_vision_provider.result
    food_vision_provider.result = empty
    for _ in range(5):
        assert (await _image(client, _device())).status_code == 200

    food_vision_provider.result = real
    for _ in range(3):
        assert (await _image(client, _device())).status_code == 200
    assert (await _image(client, _device())).status_code == 403


async def test_provider_failure_does_not_consume_a_trial(client, food_vision_provider):
    async def boom(*_args):
        raise RuntimeError("gemini down")

    food_vision_provider.analyze_image = boom
    with pytest.raises(RuntimeError):
        await _image(client, _device())
    del food_vision_provider.analyze_image

    for _ in range(3):
        assert (await _image(client, _device())).status_code == 200


async def test_signing_in_inherits_the_devices_used_trials(client, signed_up):
    for _ in range(3):
        await _image(client, _device())
    bearer = {"Authorization": f"Bearer {signed_up['accessToken']}", **_device()}

    assert (await _image(client, bearer)).status_code == 403


async def test_account_without_device_header_still_gets_trials(client, signed_up):
    bearer = {"Authorization": f"Bearer {signed_up['accessToken']}"}
    for _ in range(3):
        assert (await _image(client, bearer)).status_code == 200

    assert (await _image(client, bearer)).status_code == 403


async def test_premium_is_unlimited(client, signed_up):
    async with SessionLocal() as session:
        await session.execute(update(UserORM).values(subscription_tier="premium"))
        await session.commit()
    bearer = {"Authorization": f"Bearer {signed_up['accessToken']}", **_device()}

    for _ in range(5):
        assert (await _image(client, bearer)).status_code == 200


async def test_quota_endpoint_reports_remaining(client):
    await _image(client, _device())
    await _text(client, _device(), "voice")

    resp = await client.get("/ai/food/quota", headers=_device())

    assert resp.status_code == 200
    assert resp.json() == {
        "unlimited": False,
        "image": {"limit": 3, "remaining": 2},
        "text": {"limit": 3, "remaining": 3},
        "voice": {"limit": 3, "remaining": 2},
    }


async def test_quota_endpoint_for_premium_is_unlimited(client, signed_up):
    async with SessionLocal() as session:
        await session.execute(update(UserORM).values(subscription_tier="premium"))
        await session.commit()
    bearer = {"Authorization": f"Bearer {signed_up['accessToken']}"}

    resp = await client.get("/ai/food/quota", headers=bearer)

    assert resp.json() == {"unlimited": True, "image": None, "text": None, "voice": None}


async def test_quota_endpoint_requires_identity(client):
    assert (await client.get("/ai/food/quota")).status_code == 401


async def test_anonymous_calls_are_rate_limited_per_ip(client, monkeypatch):
    monkeypatch.setattr(security._anon_ip_limiter, "limit", 2)

    assert (await _image(client, _device("device-aaaaaaaa"))).status_code == 200
    assert (await _image(client, _device("device-bbbbbbbb"))).status_code == 200
    resp = await _image(client, _device("device-cccccccc"))

    assert resp.status_code == 429


async def test_signed_in_calls_skip_the_ip_limit(client, signed_up, monkeypatch):
    monkeypatch.setattr(security._anon_ip_limiter, "limit", 0)
    bearer = {"Authorization": f"Bearer {signed_up['accessToken']}"}

    assert (await _image(client, bearer)).status_code == 200
