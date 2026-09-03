"""RefreshToken entity — one issued refresh JWT, tracked so it can be revoked.

The token string itself is a signed JWT held by the client; this row records its
``jti`` (JWT ID), expiry, and revocation state. A refresh JWT is only accepted if
a matching, unrevoked, unexpired row exists — so logout and rotation take effect
immediately instead of waiting for the JWT to expire on its own.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import UUID, uuid4


@dataclass
class RefreshToken:
    id: UUID
    user_id: UUID
    jti: UUID
    expires_at: datetime
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    revoked_at: datetime | None = None

    def is_active(self, now: datetime) -> bool:
        return self.revoked_at is None and now < self.expires_at

    def revoke(self, now: datetime) -> None:
        if self.revoked_at is None:
            self.revoked_at = now

    @classmethod
    def issue(cls, user_id: UUID, jti: UUID, expires_at: datetime) -> RefreshToken:
        return cls(id=uuid4(), user_id=user_id, jti=jti, expires_at=expires_at)
