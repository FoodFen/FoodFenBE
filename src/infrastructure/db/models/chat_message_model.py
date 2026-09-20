"""ORM model for one turn of a user's AI chat history."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Index, Text
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

    def to_domain(self) -> ChatMessage:
        return ChatMessage(
            id=self.id,
            user_id=self.user_id,
            role=self.role,
            content=self.content,
            created_at=self.created_at,
        )

    @staticmethod
    def from_domain(message: ChatMessage) -> ChatMessageORM:
        return ChatMessageORM(
            id=message.id,
            user_id=message.user_id,
            role=message.role,
            content=message.content,
            created_at=message.created_at,
        )
