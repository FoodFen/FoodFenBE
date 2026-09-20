"""Send a chat message and stream the assistant's reply.

Persists the user's message before calling the provider, so it's part of
history even if generation then fails. A failed generation is discarded, not
persisted partially — only a fully-generated reply counts as the assistant's
turn.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from dataclasses import dataclass

from src.application.dtos.chat import (
    ChatMessageDTO,
    ChatStreamDone,
    ChatStreamError,
    ChatStreamEvent,
    ChatStreamToken,
)
from src.application.ports.ai_chat_provider import AiChatProviderProtocol
from src.application.ports.chat_message_repository import ChatMessageRepositoryProtocol
from src.domain.entities.chat_message import ChatMessage
from src.domain.enums import ChatRole

# Child of the "foodfenbe" logger configured in infrastructure/logging.py — the
# application layer can't import that module (stdlib-only rule), but a child
# logger name still propagates up to its handler.
_log = logging.getLogger("foodfenbe.chat")

_GENERATION_FAILED_MESSAGE = "The assistant couldn't generate a reply. Please try again."


@dataclass
class SendChatMessageUseCase:
    chat_messages: ChatMessageRepositoryProtocol
    provider: AiChatProviderProtocol
    history_limit: int

    async def execute(self, user_id: int, message: str) -> AsyncIterator[ChatStreamEvent]:
        # Fetch history before persisting the new message, or it would appear
        # twice: once in `history`, once as the separate `user_message` param.
        recent = await self.chat_messages.list_before(user_id, None, self.history_limit)
        history = list(reversed(recent))

        await self.chat_messages.create(ChatMessage.create(user_id, ChatRole.USER, message))

        chunks: list[str] = []
        try:
            async for delta in self.provider.stream_reply(history, message):
                chunks.append(delta)
                yield ChatStreamToken(delta)
        except Exception:
            _log.exception("chat generation failed for user %s", user_id)
            yield ChatStreamError(_GENERATION_FAILED_MESSAGE)
            return

        full_text = "".join(chunks).strip()
        if not full_text:
            _log.warning("chat generation for user %s produced an empty response", user_id)
            yield ChatStreamError(_GENERATION_FAILED_MESSAGE)
            return

        reply = await self.chat_messages.create(ChatMessage.create(user_id, ChatRole.ASSISTANT, full_text))
        yield ChatStreamDone(ChatMessageDTO.from_entity(reply))
