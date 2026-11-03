"""Gemini providers: the cost-control config they send, and the token usage they log.

The SDK client is faked — no network, no real model.
"""

from __future__ import annotations

import logging
from types import SimpleNamespace

import pytest
from catalog_foods import make_food
from google.genai import errors, types

from src.domain.entities.chat_message import ChatMessage
from src.domain.enums import ChatRole
from src.infrastructure.ai.gemini_chat_provider import GeminiChatProvider
from src.infrastructure.ai.gemini_food_vision_provider import (
    _GROUNDED_PROMPT,
    _LEGACY_PROMPT,
    GeminiFoodVisionProvider,
    _AnalysisSchema,
    _IngredientSchema,
)

_USAGE = SimpleNamespace(
    prompt_token_count=120,
    candidates_token_count=40,
    thoughts_token_count=7,
    cached_content_token_count=90,
)


class _FakeModels:
    def __init__(self, chunks=None, parsed=None, fail=()) -> None:
        self.kwargs: dict = {}
        self.calls: list[dict] = []
        self._chunks = chunks or []
        self._parsed = parsed
        self._fail = list(fail)  # one exception raised per generate call, in order

    async def generate_content(self, **kwargs):
        self.kwargs = kwargs
        self.calls.append(kwargs)
        if self._fail:
            raise self._fail.pop(0)
        return SimpleNamespace(parsed=self._parsed, usage_metadata=_USAGE)

    async def generate_content_stream(self, **kwargs):
        self.kwargs = kwargs

        async def stream():
            for chunk in self._chunks:
                yield chunk

        return stream()


class _FakeCaches:
    def __init__(self, error: Exception | None = None) -> None:
        self.calls: list[dict] = []
        self._error = error

    async def create(self, **kwargs):
        self.calls.append(kwargs)
        if self._error:
            raise self._error
        return SimpleNamespace(
            name=f"cachedContents/{len(self.calls)}",
            usage_metadata=SimpleNamespace(total_token_count=19000),
        )


def _client(models: _FakeModels, caches: _FakeCaches | None = None) -> SimpleNamespace:
    return SimpleNamespace(aio=SimpleNamespace(models=models, caches=caches or _FakeCaches()))


async def test_food_extraction_uses_low_thinking_and_capped_output():
    models = _FakeModels(parsed=_AnalysisSchema(meal_name="Pho", ingredients=[]))
    provider = GeminiFoodVisionProvider(
        api_key="", model="m", client=_client(models)
    )

    await provider.analyze_text("pho", "en")

    config = models.kwargs["config"]
    assert config.thinking_config.thinking_level == types.ThinkingLevel.LOW
    assert config.max_output_tokens == 4096


async def test_food_extraction_logs_token_usage(caplog):
    models = _FakeModels(parsed=_AnalysisSchema(meal_name="Pho", ingredients=[]))
    provider = GeminiFoodVisionProvider(api_key="", model="m", client=_client(models))

    with caplog.at_level(logging.INFO, logger="foodfenbe.ai"):
        await provider.analyze_text("pho", "en")

    assert "prompt=120 output=40 thoughts=7 cached=90" in caplog.text


async def test_chat_uses_low_thinking_and_logs_token_usage(caplog):
    chunks = [
        SimpleNamespace(text="Hi", usage_metadata=None),
        SimpleNamespace(text=" there", usage_metadata=_USAGE),
    ]
    models = _FakeModels(chunks=chunks)
    provider = GeminiChatProvider(api_key="", model="m", system_prompt="p", client=_client(models))
    history = [ChatMessage.create(1, ChatRole.USER, "hello")]

    with caplog.at_level(logging.INFO, logger="foodfenbe.ai"):
        reply = [d async for d in provider.stream_reply(history, "again", "")]

    assert reply == ["Hi", " there"]
    assert models.kwargs["config"].thinking_config.thinking_level == types.ThinkingLevel.LOW
    assert "prompt=120 output=40 thoughts=7" in caplog.text


async def test_chat_appends_context_after_the_system_prompt():
    models = _FakeModels(chunks=[SimpleNamespace(text="ok", usage_metadata=_USAGE)])
    provider = GeminiChatProvider(api_key="", model="m", system_prompt="p", client=_client(models))

    _ = [d async for d in provider.stream_reply([], "hi", "PROFILE\n- Age: 20")]

    instruction = models.kwargs["config"].system_instruction
    assert instruction.startswith("p\n\nDATA ABOUT THIS USER")
    assert instruction.endswith("PROFILE\n- Age: 20")


async def test_chat_without_context_sends_the_bare_system_prompt():
    models = _FakeModels(chunks=[SimpleNamespace(text="ok", usage_metadata=_USAGE)])
    provider = GeminiChatProvider(api_key="", model="m", system_prompt="p", client=_client(models))

    _ = [d async for d in provider.stream_reply([], "hi", "")]

    assert models.kwargs["config"].system_instruction == "p"


_HEADER = "FOOD CATALOG (one food per line: id | name | aliases | default serving grams):"


class _Clock:
    now = 1000.0

    def __call__(self) -> float:
        return self.now


def _food_provider(models, parsed=None, caches=None, clock=None):
    models._parsed = parsed or _AnalysisSchema(meal_name="Pho", ingredients=[])
    return GeminiFoodVisionProvider(
        api_key="", model="m", client=_client(models, caches), clock=clock or _Clock()
    )


def _not_found():
    return errors.ClientError(
        404, {"error": {"code": 404, "message": "CachedContent not found", "status": "NOT_FOUND"}}
    )


async def test_cache_is_created_once_and_reused_without_a_system_instruction():
    models, caches = _FakeModels(), _FakeCaches()
    provider = _food_provider(models, caches=caches)
    catalog = [make_food("a-food")]

    await provider.analyze_text("pho", "en", catalog)
    await provider.analyze_text("bun", "vi", catalog)

    assert len(caches.calls) == 1
    assert len(models.calls) == 2
    for call in models.calls:
        assert call["config"].cached_content == "cachedContents/1"
        assert call["config"].system_instruction is None
        assert call["config"].max_output_tokens == 4096
        assert call["config"].response_schema is _AnalysisSchema


async def test_cached_prefix_is_language_free_and_language_goes_last_in_contents():
    catalog = [make_food("a-food", name="A", aliases=["x", "y"]), make_food("b-food", aliases=[])]
    prefixes, contents = [], []
    for language, send in (("vi", "text"), ("en", "image")):
        models, caches = _FakeModels(), _FakeCaches()
        provider = _food_provider(models, caches=caches)
        if send == "text":
            await provider.analyze_text("pho", language, catalog)
        else:
            await provider.analyze_image(b"x", "image/jpeg", language, catalog)
        create = caches.calls[0]
        assert create["model"] == "m"
        assert create["config"].ttl == "3600s"
        assert create["config"].display_name == "food-analysis-catalog"
        prefixes.append(create["config"].system_instruction)
        contents.append(models.calls[0]["contents"])

    assert prefixes[0] == prefixes[1]
    assert prefixes[0].startswith(
        f"{_HEADER}\na-food | A | x, y | 550\nb-food | Phở bò |  | 550\n\n{_GROUNDED_PROMPT}"
    )
    assert "Respond entirely in" not in prefixes[0]
    assert contents[0][0] == "pho"
    assert isinstance(contents[1][0], types.Part)
    assert contents[0][-1].startswith("Respond entirely in Vietnamese.")
    assert contents[1][-1].startswith("Respond entirely in English.")
    assert contents[0][-1].endswith("Do not mix languages within mealName or any ingredient name.")


async def test_cache_is_recreated_within_five_minutes_of_expiry_and_reused_before():
    clock, caches = _Clock(), _FakeCaches()
    provider = _food_provider(_FakeModels(), caches=caches, clock=clock)
    catalog = [make_food()]

    await provider.analyze_text("a", "en", catalog)
    clock.now += 3600 - 301
    await provider.analyze_text("b", "en", catalog)
    assert len(caches.calls) == 1

    clock.now += 2  # 299s left
    await provider.analyze_text("c", "en", catalog)
    assert len(caches.calls) == 2


async def test_a_different_catalog_creates_a_second_cache():
    models, caches = _FakeModels(), _FakeCaches()
    provider = _food_provider(models, caches=caches)

    await provider.analyze_text("a", "en", [make_food("a-food")])
    await provider.analyze_text("a", "en", [make_food("a-food"), make_food("b-food")])

    assert len(caches.calls) == 2
    assert [c["config"].cached_content for c in models.calls] == [
        "cachedContents/1",
        "cachedContents/2",
    ]


async def test_cache_creation_is_logged(caplog):
    provider = _food_provider(_FakeModels())

    with caplog.at_level(logging.INFO, logger="foodfenbe.ai"):
        await provider.analyze_text("a", "en", [make_food()])

    assert (
        "gemini food-analysis cache created: name=cachedContents/1 tokens=19000 ttl=3600s"
        in caplog.text
    )


async def test_a_gone_cache_is_replaced_and_the_request_retried_once():
    models, caches = _FakeModels(fail=[_not_found()]), _FakeCaches()

    result = await _food_provider(models, caches=caches).analyze_text("a", "en", [make_food()])

    assert result.meal_name == "Pho"
    assert len(caches.calls) == 2
    assert [c["config"].cached_content for c in models.calls] == [
        "cachedContents/1",
        "cachedContents/2",
    ]


async def test_a_second_consecutive_cache_error_propagates():
    models = _FakeModels(fail=[_not_found(), _not_found()])

    with pytest.raises(errors.ClientError):
        await _food_provider(models).analyze_text("a", "en", [make_food()])

    assert len(models.calls) == 2


@pytest.mark.parametrize(
    "error",
    [
        errors.ClientError(400, {"error": {"code": 400, "message": "bad schema", "status": "X"}}),
        errors.ServerError(503, {"error": {"code": 503, "message": "overloaded", "status": "X"}}),
    ],
)
async def test_other_generate_errors_propagate_without_retry(error):
    models, caches = _FakeModels(fail=[error]), _FakeCaches()

    with pytest.raises(type(error)):
        await _food_provider(models, caches=caches).analyze_text("a", "en", [make_food()])

    assert len(models.calls) == 1
    assert len(caches.calls) == 1


async def test_a_cache_mentioning_error_is_retried_even_without_404():
    error = errors.ClientError(
        400, {"error": {"code": 400, "message": "Cached content expired", "status": "X"}}
    )
    models = _FakeModels(fail=[error])

    await _food_provider(models).analyze_text("a", "en", [make_food()])

    assert len(models.calls) == 2


async def test_cache_creation_failure_falls_back_to_an_uncached_request(caplog):
    models, caches = _FakeModels(), _FakeCaches(error=RuntimeError("quota"))
    provider = _food_provider(models, caches=caches)

    with caplog.at_level(logging.WARNING, logger="foodfenbe.ai"):
        await provider.analyze_text("a", "en", [make_food()])
        await provider.analyze_text("b", "en", [make_food()])

    config = models.calls[0]["config"]
    assert config.cached_content is None
    assert config.system_instruction == caches.calls[0]["config"].system_instruction
    assert config.system_instruction.startswith(_HEADER)
    assert "cache" in caplog.text and "quota" in caplog.text
    assert len(caches.calls) == 2  # nothing stored, so the next request tries again


async def test_without_a_catalog_there_is_no_cache_and_the_language_stays_in_the_instruction():
    models, caches = _FakeModels(), _FakeCaches()

    await _food_provider(models, caches=caches).analyze_text("pho", "en", None)

    assert caches.calls == []
    assert models.kwargs["contents"] == ["pho"]
    assert models.kwargs["config"].cached_content is None
    assert models.kwargs["config"].system_instruction.endswith(
        "Respond entirely in English. Do not mix languages within mealName or any ingredient name."
    )


async def test_model_catalog_id_is_mapped_when_a_catalog_was_sent():
    row = _IngredientSchema(
        name="pho", quantity_g=500, kcal=1, carbs_g=1, protein_g=1, fat_g=1, confidence=0.9,
        catalog_id="pho-bo",
    )
    parsed = _AnalysisSchema(meal_name="Pho", ingredients=[row])

    result = await _food_provider(_FakeModels(), parsed).analyze_text("pho", "en", [make_food()])

    assert result.ingredients[0].catalog_food_id == "pho-bo"


async def test_without_a_catalog_the_legacy_prompt_is_used_and_catalog_id_is_ignored():
    row = _IngredientSchema(
        name="pho", quantity_g=500, kcal=1, carbs_g=1, protein_g=1, fat_g=1, confidence=0.9,
        catalog_id="pho-bo",
    )
    models = _FakeModels()
    provider = _food_provider(models, _AnalysisSchema(meal_name="Pho", ingredients=[row]))

    result = await provider.analyze_text("pho", "vi", None)

    assert models.kwargs["config"].system_instruction.startswith(_LEGACY_PROMPT)
    assert "FOOD CATALOG" not in models.kwargs["config"].system_instruction
    assert result.ingredients[0].catalog_food_id is None
