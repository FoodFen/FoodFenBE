"""HTTP wire models for the AI chat API contract."""

from __future__ import annotations

# `date` is also the field name below; aliasing the type keeps Pydantic from
# resolving the annotation to the field's own default (None).
from datetime import date as LocalDate
from datetime import datetime
from typing import Literal

from pydantic import Field

from src.adapters.schemas.base import CamelModel
from src.application.dtos.chat import ChatHistoryPageDTO, ChatMessageDTO


class ChatMessageResponse(CamelModel):
    id: str
    role: Literal["user", "assistant"]
    content: str
    created_at: datetime

    @classmethod
    def from_dto(cls, dto: ChatMessageDTO) -> ChatMessageResponse:
        return cls(id=dto.id, role=dto.role, content=dto.content, created_at=dto.created_at)


class ChatHistoryResponse(CamelModel):
    messages: list[ChatMessageResponse]
    next_cursor: str | None

    @classmethod
    def from_dto(cls, dto: ChatHistoryPageDTO) -> ChatHistoryResponse:
        return cls(
            messages=[ChatMessageResponse.from_dto(m) for m in dto.messages],
            next_cursor=dto.next_cursor,
        )


class SendChatMessageRequest(CamelModel):
    message: str = Field(max_length=2000)
    # The client's local day (same convention as loggedOn / GET /quests?date=).
    # Omitted → the server's UTC day.
    date: LocalDate | None = None
