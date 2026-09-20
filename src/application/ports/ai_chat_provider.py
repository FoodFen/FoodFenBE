"""Port: stream an assistant reply from an LLM. Standard library only.

Yields raw text deltas — no HTTP, SSE, or vendor request/response shape leaks
past this boundary. `history` is oldest-first, ending right before the new
`user_message` (which is not yet persisted when this is called).
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Protocol

from src.domain.entities.chat_message import ChatMessage


class AiChatProviderProtocol(Protocol):
    def stream_reply(
        self, history: list[ChatMessage], user_message: str
    ) -> AsyncIterator[str]: ...
