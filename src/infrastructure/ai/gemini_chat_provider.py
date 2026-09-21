"""Gemini implementation of ``AiChatProviderProtocol``.

Gemini's role vocabulary is `user`/`model`, not `user`/`assistant` — that
translation is confined to this class; the domain `ChatRole` enum never
changes to match a vendor.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

from google import genai
from google.genai import types

from src.domain.entities.chat_message import ChatMessage
from src.domain.enums import ChatRole

_GEMINI_ROLE = {ChatRole.USER: "user", ChatRole.ASSISTANT: "model"}


class GeminiChatProvider:
    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        system_prompt: str,
        client: genai.Client | None = None,
    ) -> None:
        self._model = model
        self._system_prompt = system_prompt
        # Overridable so tests can inject a fake client instead of a real API call.
        self._client = client or genai.Client(api_key=api_key)

    async def stream_reply(
        self, history: list[ChatMessage], user_message: str
    ) -> AsyncIterator[str]:
        contents = [
            types.Content(role=_GEMINI_ROLE[m.role], parts=[types.Part(text=m.content)])
            for m in history
        ]
        contents.append(types.Content(role="user", parts=[types.Part(text=user_message)]))

        stream = await self._client.aio.models.generate_content_stream(
            model=self._model,
            contents=contents,
            config=types.GenerateContentConfig(system_instruction=self._system_prompt),
        )
        async for chunk in stream:
            if chunk.text:
                yield chunk.text
