"""List-chat-history use case. Standard library + domain only."""

from __future__ import annotations

from dataclasses import dataclass

from src.application.chat_cursor import encode_cursor
from src.application.chat_dishes import to_cards
from src.application.dtos.chat import ChatHistoryPageDTO, ChatMessageDTO
from src.application.ports.chat_message_repository import ChatMessageRepositoryProtocol
from src.application.ports.restaurant_repository import RestaurantRepositoryProtocol


@dataclass
class ListChatMessagesUseCase:
    chat_messages: ChatMessageRepositoryProtocol
    restaurants: RestaurantRepositoryProtocol

    async def execute(self, user_id: int, before: str | None, limit: int) -> ChatHistoryPageDTO:
        rows = await self.chat_messages.list_before(user_id, before, limit + 1)
        has_more = len(rows) > limit
        page = rows[:limit]
        next_cursor = encode_cursor(page[-1]) if has_more and page else None
        # One lookup per page, and none when no message on it carries a card.
        public = {}
        if any(m.dish_ids for m in page):
            public = {d.id: (d, r) for d, r in await self.restaurants.list_public_dishes()}
        return ChatHistoryPageDTO(
            messages=[ChatMessageDTO.from_entity(m, to_cards(m.dish_ids, public)) for m in page],
            next_cursor=next_cursor,
        )
