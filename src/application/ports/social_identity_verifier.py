"""Port: verify a Google/Apple identity token. Standard library only.

The implementation must verify the token's signature against the provider's
public keys, plus its issuer, audience, and expiry — never trust the claims
without verifying the signature server-side.
"""

from __future__ import annotations

from typing import Protocol

from src.application.dtos.auth import VerifiedIdentity
from src.domain.enums import AuthProvider


class SocialIdentityVerifierProtocol(Protocol):
    def verify(self, provider: AuthProvider, id_token: str) -> VerifiedIdentity:
        """Raise ``InvalidTokenException`` if the token is missing, malformed,
        unsigned by the provider, or its issuer/audience/expiry don't check out."""
        ...
