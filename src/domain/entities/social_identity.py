"""SocialIdentity entity — links one (provider, provider_user_id) pair to a user.

Standard library only. The row is what makes a returning Google/Apple sign-in
resolve to the same account: the client can't be trusted to say who it is, but
the provider's verified `sub` claim is stable across sign-ins, so it's the key.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import UUID, uuid4

from src.domain.enums import AuthProvider
from src.domain.validation import require_non_empty


@dataclass
class SocialIdentity:
    id: UUID
    user_id: int
    provider: AuthProvider
    provider_user_id: str
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        self.provider_user_id = require_non_empty(self.provider_user_id, "provider_user_id")

    @classmethod
    def create(cls, user_id: int, provider: AuthProvider, provider_user_id: str) -> SocialIdentity:
        return cls(
            id=uuid4(),
            user_id=user_id,
            provider=provider,
            provider_user_id=provider_user_id,
            created_at=datetime.now(UTC),
        )
