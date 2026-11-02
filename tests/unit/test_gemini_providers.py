"""Gemini providers: the cost-control config they send, and the token usage they log.

The SDK client is faked — no network, no real model.
"""

from __future__ import annotations

import logging
from types import SimpleNamespace

from catalog_foods import make_food
from google.genai import types

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
    def __init__(self, chunks=None, parsed=None) -> None:
        self.kwargs: dict = {}
        self._chunks = chunks or []
        self._parsed = parsed

    async def generate_content(self, **kwargs):
        self.kwargs = kwargs
        return SimpleNamespace(parsed=self._parsed, usage_metadata=_USAGE)

    async def generate_content_stream(self, **kwargs):
        self.kwargs = kwargs

        async def stream():
            for chunk in self._chunks:
                yield chunk

        return stream()


def _client(models: _FakeModels) -> SimpleNamespace:
    return SimpleNamespace(aio=SimpleNamespace(models=models))


async def test_food_extraction_uses_minimal_thinking_and_capped_output():
    models = _FakeModels(parsed=_AnalysisSchema(meal_name="Pho", ingredients=[]))
    provider = GeminiFoodVisionProvider(
        api_key="", model="m", client=_client(models)
    )

    await provider.analyze_text("pho", "en")

    config = models.kwargs["config"]
    assert config.thinking_config.thinking_level == types.ThinkingLevel.MINIMAL
    assert config.max_output_tokens == 1024


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


def _food_provider(models, parsed=None):
    models._parsed = parsed or _AnalysisSchema(meal_name="Pho", ingredients=[])
    return GeminiFoodVisionProvider(api_key="", model="m", client=_client(models))


async def test_catalog_block_leads_the_system_instruction_and_is_formatted_per_food():
    models = _FakeModels()
    catalog = [make_food("a-food", name="A", aliases=["x", "y"]), make_food("b-food", aliases=[])]

    await _food_provider(models).analyze_text("pho", "en", catalog)

    instruction = models.kwargs["config"].system_instruction
    assert instruction.startswith(
        f"{_HEADER}\na-food | A | x, y | 550\nb-food | Phở bò |  | 550\n\n{_GROUNDED_PROMPT}"
    )
    assert instruction.endswith("Do not mix languages within mealName or any ingredient name.")
    assert "Respond entirely in English" in instruction


async def test_catalog_block_is_byte_identical_across_languages_and_calls():
    catalog = [make_food("a-food"), make_food("b-food")]
    seen = []
    for language in ("vi", "en", "vi"):
        models = _FakeModels()
        await _food_provider(models).analyze_text("pho", language, catalog)
        instruction = models.kwargs["config"].system_instruction
        seen.append(instruction[: instruction.index(_GROUNDED_PROMPT)])

    assert seen[0] == seen[1] == seen[2]


async def test_image_analysis_is_grounded_too():
    models = _FakeModels()

    await _food_provider(models).analyze_image(b"x", "image/jpeg", "vi", [make_food()])

    assert models.kwargs["config"].system_instruction.startswith(_HEADER)


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
