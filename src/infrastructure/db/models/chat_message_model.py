"""ORM model for one turn of a user's AI chat history."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import JSON, DateTime, Index, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from src.domain.entities.chat_message import ChatMessage
from src.domain.enums import ChatRole
from src.infrastructure.db.base import Base
from src.infrastructure.db.mixins import UserOwned, UUIDPrimaryKey
from src.infrastructure.db.types import enum_column


class ChatMessageORM(UUIDPrimaryKey, UserOwned, Base):
    __tablename__ = "chat_messages"
    __table_args__ = (Index("ix_chat_messages_user_created", "user_id", "created_at"),)

    role: Mapped[ChatRole] = mapped_column(enum_column(ChatRole, "chat_role"), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    dish_ids: Mapped[list[str]] = mapped_column(JSON, nullable=False, server_default=text("'[]'"))  # UUID strings

    def to_domain(self) -> ChatMessage:
        return ChatMessage(
            id=self.id,
            user_id=self.user_id,
            role=self.role,
            content=self.content,
            created_at=self.created_at,
            dish_ids=[UUID(i) for i in self.dish_ids],
        )

    @staticmethod
    def from_domain(message: ChatMessage) -> ChatMessageORM:
        return ChatMessageORM(
            id=message.id,
            user_id=message.user_id,
            role=message.role,
            content=message.content,
            created_at=message.created_at,
            dish_ids=[str(i) for i in message.dish_ids],
        )
