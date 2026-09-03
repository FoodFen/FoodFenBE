"""Persistence port for tracked refresh tokens. Standard library only."""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from src.domain.entities.refresh_token import RefreshToken


class RefreshTokenRepositoryProtocol(Protocol):
    async def add(self, token: RefreshToken) -> RefreshToken: ...

    async def get_by_jti(self, jti: UUID) -> RefreshToken | None: ...

    async def revoke(self, token: RefreshToken) -> None:
        """Persist ``token.revoked_at`` for the row with this ``jti``."""
        ...
