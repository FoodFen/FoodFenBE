"""Auth DTOs crossing the application boundary. Standard library only."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True)
class RegisterInputDTO:
    email: str
    password: str
    name: str


@dataclass(frozen=True)
class LoginInputDTO:
    email: str
    password: str


@dataclass(frozen=True)
class RefreshInputDTO:
    refresh_token: str


@dataclass(frozen=True)
class IssuedToken:
    """A freshly minted JWT and the moment it stops being valid."""

    token: str
    expires_at: datetime


@dataclass(frozen=True)
class RefreshClaims:
    """The parts of a verified refresh token the application cares about."""

    user_id: UUID
    jti: UUID


@dataclass(frozen=True)
class TokenPairDTO:
    access_token: str
    refresh_token: str
    expires_in: int  # seconds until the access token expires
    token_type: str = "bearer"
