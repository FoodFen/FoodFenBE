"""Persistence port for chat messages. Structural typing via Protocol."""

from __future__ import annotations

from typing import Protocol

from src.domain.entities.chat_message import ChatMessage


class ChatMessageRepositoryProtocol(Protocol):
    async def create(self, message: ChatMessage) -> ChatMessage: ...

    async def list_before(
        self, user_id: int, before: str | None, limit: int
    ) -> list[ChatMessage]:
        """Newest-first page of `user_id`'s history, strictly older than the
        opaque `before` cursor. `None` starts from the newest message. May
        return up to `limit` rows."""
        ...
