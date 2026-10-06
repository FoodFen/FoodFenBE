"""AI chat endpoints. HTTP <-> application DTO translation only.

`POST /chat/messages` streams via SSE. Auth/validation failures happen before
the generator ever runs (normal 401/422), matching the contract's rule that
only a failure *after* streaming starts becomes an `event: error` frame
instead of a non-200 status.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from src.adapters.schemas.chat_schemas import (
    ChatHistoryResponse,
    ChatMessageResponse,
    SendChatMessageRequest,
)
from src.application.dtos.chat import ChatStreamDone, ChatStreamError, ChatStreamToken
from src.infrastructure.di import (
    CurrentUserDep,
    ListChatMessagesUseCaseDep,
    SendChatMessageUseCaseDep,
    get_current_user,
    limit_chat_by_user,
)

router = APIRouter(prefix="/chat", tags=["chat"], dependencies=[Depends(get_current_user)])


@router.get("/messages", response_model=ChatHistoryResponse)
async def list_messages(
    current_user: CurrentUserDep,
    use_case: ListChatMessagesUseCaseDep,
    before: str | None = None,
    limit: int = 30,
) -> ChatHistoryResponse:
    page = await use_case.execute(current_user.id, before, limit)
    return ChatHistoryResponse.from_dto(page)


@router.post("/messages", dependencies=[Depends(limit_chat_by_user)])
async def send_message(
    body: SendChatMessageRequest,
    current_user: CurrentUserDep,
    use_case: SendChatMessageUseCaseDep,
) -> StreamingResponse:
    async def sse() -> AsyncIterator[str]:
        async for event in use_case.execute(current_user.id, body.message, body.date):
            if isinstance(event, ChatStreamToken):
                yield f"event: token\ndata: {json.dumps({'delta': event.delta})}\n\n"
            elif isinstance(event, ChatStreamDone):
                payload = ChatMessageResponse.from_dto(event.message).model_dump(
                    mode="json", by_alias=True
                )
                yield f"event: done\ndata: {json.dumps({'message': payload})}\n\n"
            elif isinstance(event, ChatStreamError):
                yield f"event: error\ndata: {json.dumps({'message': event.message})}\n\n"

    return StreamingResponse(sse(), media_type="text/event-stream")
