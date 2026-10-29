"""Opaque pagination cursor for chat history and coin transactions: `created_at|id`, newest-first.

A shared codec so the use case (encodes the next cursor) and the repository
(decodes an incoming one for its WHERE clause) can't drift out of sync. The
`id` tiebreaks messages with the same `created_at`, avoiding skipped or
duplicated rows on a page boundary. Standard library only.
"""

from __future__ import annotations

from datetime import datetime
from typing import Protocol
from uuid import UUID

from src.domain.exceptions import InvalidAttributeException


class Cursored(Protocol):
    created_at: datetime
    id: UUID


def encode_cursor(row: Cursored) -> str:
    return f"{row.created_at.isoformat()}|{row.id}"


def decode_cursor(cursor: str) -> tuple[datetime, UUID]:
    try:
        created_at_raw, id_raw = cursor.split("|", 1)
        return datetime.fromisoformat(created_at_raw), UUID(id_raw)
    except ValueError as exc:
        raise InvalidAttributeException(f"malformed pagination cursor: {cursor!r}") from exc
