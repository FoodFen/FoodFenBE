"""JWT issuing/verifying port. Standard library only."""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from src.application.dtos.auth import IssuedToken, RefreshClaims


class TokenServiceProtocol(Protocol):
    def issue_access_token(self, user_id: UUID) -> IssuedToken: ...

    def issue_refresh_token(self, user_id: UUID, jti: UUID) -> IssuedToken: ...

    def issue_verification_token(self, user_id: UUID) -> IssuedToken: ...

    def read_access_token(self, token: str) -> UUID:
        """Return the subject user id. Raise ``InvalidTokenException`` if unusable."""
        ...

    def read_refresh_token(self, token: str) -> RefreshClaims:
        """Return the verified claims. Raise ``InvalidTokenException`` if unusable."""
        ...

    def read_verification_token(self, token: str) -> UUID:
        """Return the subject user id. Raise ``InvalidTokenException`` if unusable."""
        ...
