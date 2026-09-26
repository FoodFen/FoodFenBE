"""Port: persist an uploaded image somewhere durable, return its URL.

Standard library only.
"""

from __future__ import annotations

from typing import Protocol


class ImageStorageProtocol(Protocol):
    async def upload(self, data: bytes, content_type: str) -> str: ...
