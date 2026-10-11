"""ChatMessage entity — one turn (user or assistant) in a user's AI chat history.

Standard library only.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import UUID, uuid4

from src.domain.enums import ChatRole
from src.domain.validation import require_non_empty


@dataclass
class ChatMessage:
    id: UUID
    user_id: int
    role: ChatRole
    content: str
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    dish_ids: list[UUID] = field(default_factory=list)  # dishes Fen recommended (assistant turns)

    def __post_init__(self) -> None:
        self.content = require_non_empty(self.content, "content")

    @classmethod
    def create(
        cls, user_id: int, role: ChatRole, content: str, dish_ids: list[UUID] | None = None
    ) -> ChatMessage:
        return cls(
            id=uuid4(), user_id=user_id, role=role, content=content, created_at=datetime.now(UTC),
            dish_ids=dish_ids or [],
        )
