"""Chat DTOs crossing the application boundary. Standard library only."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from src.application.dtos.restaurant import PublicDishDTO, PublicRestaurantSummaryDTO
from src.domain.entities.chat_message import ChatMessage
from src.domain.enums import ChatRole


@dataclass(frozen=True)
class ChatDishDTO:
    """A dish card under Fen's reply: a public dish and its restaurant, no fits/reasons (it may be stale)."""

    dish: PublicDishDTO
    restaurant: PublicRestaurantSummaryDTO


@dataclass(frozen=True)
class ChatMessageDTO:
    id: str
    role: ChatRole
    content: str
    created_at: datetime
    dishes: list[ChatDishDTO] = field(default_factory=list)

    @classmethod
    def from_entity(cls, message: ChatMessage, dishes: list[ChatDishDTO] | None = None) -> ChatMessageDTO:
        return cls(
            id=str(message.id),
            role=message.role,
            content=message.content,
            created_at=message.created_at,
            dishes=dishes or [],
        )


@dataclass(frozen=True)
class ChatHistoryPageDTO:
    messages: list[ChatMessageDTO]
    next_cursor: str | None


@dataclass(frozen=True)
class ChatStreamToken:
    delta: str


@dataclass(frozen=True)
class ChatStreamDone:
    message: ChatMessageDTO


@dataclass(frozen=True)
class ChatStreamError:
    message: str


ChatStreamEvent = ChatStreamToken | ChatStreamDone | ChatStreamError
