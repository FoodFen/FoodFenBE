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
from datetime import date, datetime, timedelta, timezone
from uuid import UUID

from src.application.chat_context import WINDOW_DAYS, render_user_context
from src.application.chat_dishes import MarkerStripper, pick_candidates, render_dishes, to_cards, valid_ids
from src.application.dish_fit import rank_dishes, remaining_on
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
from src.application.ports.restaurant_repository import RestaurantRepositoryProtocol
from src.application.ports.user_repository import UserRepositoryProtocol
from src.domain.entities.chat_message import ChatMessage
from src.domain.entities.dish import Dish
from src.domain.entities.restaurant import Restaurant
from src.domain.enums import ChatRole

# Child of the "foodfenbe" logger configured in infrastructure/logging.py — the
# application layer can't import that module (stdlib-only rule), but a child
# logger name still propagates up to its handler.
_log = logging.getLogger("foodfenbe.chat")

_VN = timezone(timedelta(hours=7))  # Vietnam day, same convention as ai_trial.py

_GENERATION_FAILED_MESSAGE = "The assistant couldn't generate a reply. Please try again."


@dataclass
class SendChatMessageUseCase:
    chat_messages: ChatMessageRepositoryProtocol
    provider: AiChatProviderProtocol
    users: UserRepositoryProtocol
    daily_goals: DailyGoalRepositoryProtocol
    food_entries: FoodEntryRepositoryProtocol
    restaurants: RestaurantRepositoryProtocol
    history_limit: int

    async def execute(
        self, user_id: int, message: str, today: date | None = None
    ) -> AsyncIterator[ChatStreamEvent]:
        # Fetch history before persisting the new message, or it would appear
        # twice: once in `history`, once as the separate `user_message` param.
        recent = await self.chat_messages.list_before(user_id, None, self.history_limit)
        history = list(reversed(recent))
        context, candidates = await self._build_context(user_id, today or datetime.now(_VN).date())

        await self.chat_messages.create(ChatMessage.create(user_id, ChatRole.USER, message))

        chunks: list[str] = []
        markers = MarkerStripper()
        try:
            async for delta in self.provider.stream_reply(history, message, context):
                if text := markers.feed(delta):
                    chunks.append(text)
                    yield ChatStreamToken(text)
            if text := markers.finish():
                chunks.append(text)
                yield ChatStreamToken(text)
        except Exception:
            _log.exception("chat generation failed for user %s", user_id)
            yield ChatStreamError(_GENERATION_FAILED_MESSAGE)
            return

        full_text = "".join(chunks).strip()
        if not full_text:
            _log.warning("chat generation for user %s produced an empty response", user_id)
            yield ChatStreamError(_GENERATION_FAILED_MESSAGE)
            return

        dish_ids = valid_ids(markers.ids, set(candidates))
        reply = await self.chat_messages.create(
            ChatMessage.create(user_id, ChatRole.ASSISTANT, full_text, dish_ids)
        )
        yield ChatStreamDone(ChatMessageDTO.from_entity(reply, to_cards(reply.dish_ids, candidates)))

    async def _build_context(
        self, user_id: int, today: date
    ) -> tuple[str, dict[UUID, tuple[Dish, Restaurant]]]:
        """The context text (one section per source; a new source appends its own) and the dishes Fen was
        offered this turn (id -> dish, restaurant), the only ones it may turn into cards."""
        user = await self.users.get_by_id(user_id)
        goals = await self.daily_goals.list_by_user(user_id)
        entries = await self.food_entries.list_by_date_range(
            user_id, today - timedelta(days=WINDOW_DAYS - 1), today
        )
        sections = [render_user_context(user, goals, entries, today)]

        public = {d.id: (d, r) for d, r in await self.restaurants.list_public_dishes()}
        diet = user.diet_type if user else None
        _, left = remaining_on(goals, (e for e in entries if e.logged_on == today), today)
        offered = pick_candidates(rank_dishes((d for d, _ in public.values()), left, diet), diet)
        if section := render_dishes(offered, public):
            sections.append(section)
        return "\n\n".join(sections), {r.dish.id: public[r.dish.id] for r in offered}
