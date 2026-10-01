"""Gemini providers: the cost-control config they send, and the token usage they log.

The SDK client is faked — no network, no real model.
"""

from __future__ import annotations

import logging
from types import SimpleNamespace

from google.genai import types

from src.domain.entities.chat_message import ChatMessage
from src.domain.enums import ChatRole
from src.infrastructure.ai.gemini_chat_provider import GeminiChatProvider
from src.infrastructure.ai.gemini_food_vision_provider import (
    GeminiFoodVisionProvider,
    _AnalysisSchema,
)

_USAGE = SimpleNamespace(prompt_token_count=120, candidates_token_count=40, thoughts_token_count=7)


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
        api_key="", model="m", system_prompt="p", client=_client(models)
    )

    await provider.analyze_text("pho", "en")

    config = models.kwargs["config"]
    assert config.thinking_config.thinking_level == types.ThinkingLevel.MINIMAL
    assert config.max_output_tokens == 1024


async def test_food_extraction_logs_token_usage(caplog):
    models = _FakeModels(parsed=_AnalysisSchema(meal_name="Pho", ingredients=[]))
    provider = GeminiFoodVisionProvider(
        api_key="", model="m", system_prompt="p", client=_client(models)
    )

    with caplog.at_level(logging.INFO, logger="foodfenbe.ai"):
        await provider.analyze_text("pho", "en")

    assert "prompt=120 output=40 thoughts=7" in caplog.text


async def test_chat_uses_low_thinking_and_logs_token_usage(caplog):
    chunks = [
        SimpleNamespace(text="Hi", usage_metadata=None),
        SimpleNamespace(text=" there", usage_metadata=_USAGE),
    ]
    models = _FakeModels(chunks=chunks)
    provider = GeminiChatProvider(api_key="", model="m", system_prompt="p", client=_client(models))
    history = [ChatMessage.create(1, ChatRole.USER, "hello")]

    with caplog.at_level(logging.INFO, logger="foodfenbe.ai"):
        reply = [d async for d in provider.stream_reply(history, "again")]

    assert reply == ["Hi", " there"]
    assert models.kwargs["config"].thinking_config.thinking_level == types.ThinkingLevel.LOW
    assert "prompt=120 output=40 thoughts=7" in caplog.text
