"""Send a chat message and stream the assistant's reply.

Persists the user's message before calling the provider, so it's part of
history even if generation then fails. A failed generation is discarded, not
persisted partially — only a fully-generated reply counts as the assistant's
turn.
Each turn is grounded in the user's own data via _build_context; it is rebuilt per turn and never persisted.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta

from src.application.chat_context import WINDOW_DAYS, render_user_context
from src.application.dtos.chat import (
    ChatMessageDTO,
    ChatStreamDone,
    ChatStreamError,
    ChatStreamEvent,
    ChatStreamToken,
)
from src.application.ports.ai_chat_provider import AiChatProviderProtocol
from src.application.ports.chat_message_repository import ChatMessageRepositoryProtocol
from src.application.ports.daily_goal_repository import DailyGoalRepositoryProtocol
from src.application.ports.food_entry_repository import FoodEntryRepositoryProtocol
from src.application.ports.user_repository import UserRepositoryProtocol
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
    users: UserRepositoryProtocol
    daily_goals: DailyGoalRepositoryProtocol
    food_entries: FoodEntryRepositoryProtocol
    history_limit: int

    async def execute(
        self, user_id: int, message: str, today: date | None = None
    ) -> AsyncIterator[ChatStreamEvent]:
        # Fetch history before persisting the new message, or it would appear
        # twice: once in `history`, once as the separate `user_message` param.
        recent = await self.chat_messages.list_before(user_id, None, self.history_limit)
        history = list(reversed(recent))
        context = await self._build_context(user_id, today or datetime.now(UTC).date())

        await self.chat_messages.create(ChatMessage.create(user_id, ChatRole.USER, message))

        chunks: list[str] = []
        try:
            async for delta in self.provider.stream_reply(history, message, context):
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

    async def _build_context(self, user_id: int, today: date) -> str:
        """One section per source. A new source (food catalog, RAG retriever) appends its own."""
        user = await self.users.get_by_id(user_id)
        goals = await self.daily_goals.list_by_user(user_id)
        entries = await self.food_entries.list_by_date_range(
            user_id, today - timedelta(days=WINDOW_DAYS - 1), today
        )
        sections = [render_user_context(user, goals, entries, today)]
        return "\n\n".join(sections)
