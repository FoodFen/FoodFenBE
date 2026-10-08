"""Persistence port for tracked refresh tokens. Standard library only."""

from __future__ import annotations

from datetime import datetime
from typing import Protocol
from uuid import UUID

from src.domain.entities.refresh_token import RefreshToken


class RefreshTokenRepositoryProtocol(Protocol):
    async def add(self, token: RefreshToken) -> RefreshToken: ...

    async def get_by_jti(self, jti: UUID) -> RefreshToken | None: ...

    async def revoke(self, token: RefreshToken) -> None:
        """Persist ``token.revoked_at`` for the row with this ``jti``."""
        ...

    async def revoke_all_for_user(self, user_id: int, now: datetime) -> None:
        """Revoke every still-active token of ``user_id``."""
        ...
