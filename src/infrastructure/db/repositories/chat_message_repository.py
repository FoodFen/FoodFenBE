"""Concrete ``ChatMessageRepositoryProtocol`` implementation backed by async SQLAlchemy."""

from sqlalchemy import select, tuple_
from sqlalchemy.ext.asyncio import AsyncSession

from src.application.chat_cursor import decode_cursor
from src.domain.entities.chat_message import ChatMessage
from src.infrastructure.db.models.chat_message_model import ChatMessageORM


class SQLAlchemyChatMessageRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, message: ChatMessage) -> ChatMessage:
        row = ChatMessageORM.from_domain(message)
        self._session.add(row)
        await self._session.flush()
        await self._session.refresh(row)
        return row.to_domain()

    async def list_before(
        self, user_id: int, before: str | None, limit: int
    ) -> list[ChatMessage]:
        query = select(ChatMessageORM).where(ChatMessageORM.user_id == user_id)
        if before is not None:
            cursor_created_at, cursor_id = decode_cursor(before)
            query = query.where(
                tuple_(ChatMessageORM.created_at, ChatMessageORM.id) < (cursor_created_at, cursor_id)
            )
        query = query.order_by(ChatMessageORM.created_at.desc(), ChatMessageORM.id.desc()).limit(
            limit
        )
        rows = (await self._session.execute(query)).scalars().all()
        return [row.to_domain() for row in rows]
