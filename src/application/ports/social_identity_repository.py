"""Persistence port for social identities. Structural typing via Protocol."""

from __future__ import annotations

from typing import Protocol

from src.domain.entities.social_identity import SocialIdentity
from src.domain.enums import AuthProvider


class SocialIdentityRepositoryProtocol(Protocol):
    async def get_by_provider_subject(
        self, provider: AuthProvider, provider_user_id: str
    ) -> SocialIdentity | None: ...

    async def create(self, identity: SocialIdentity) -> SocialIdentity: ...
