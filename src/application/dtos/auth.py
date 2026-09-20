"""Auth DTOs crossing the application boundary. Standard library only."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from src.application.dtos.user import UserOutputDTO
from src.domain.enums import AuthProvider


@dataclass(frozen=True)
class RegisterInputDTO:
    email: str
    password: str
    name: str | None = None


@dataclass(frozen=True)
class LoginInputDTO:
    email: str
    password: str


@dataclass(frozen=True)
class RefreshInputDTO:
    refresh_token: str


@dataclass(frozen=True)
class ResendVerificationInputDTO:
    email: str


@dataclass(frozen=True)
class RequestPasswordResetInputDTO:
    email: str


@dataclass(frozen=True)
class ResetPasswordInputDTO:
    token: str
    new_password: str


@dataclass(frozen=True)
class SocialSignInInputDTO:
    provider: AuthProvider
    id_token: str
    full_name: str | None = None  # Apple only, first authorization only
    email: str | None = None


@dataclass(frozen=True)
class VerifiedIdentity:
    """What a verified provider identity token actually told us."""

    subject: str  # the provider's stable per-user id (the token's `sub` claim)
    email: str | None
    email_verified: bool


@dataclass(frozen=True)
class VerificationDispatchDTO:
    """Everything the controller needs to send a verification email in the background."""

    email: str
    name: str | None
    token: str


@dataclass(frozen=True)
class IssuedToken:
    """A freshly minted JWT and the moment it stops being valid."""

    token: str
    expires_at: datetime


@dataclass(frozen=True)
class RefreshClaims:
    """The parts of a verified refresh token the application cares about."""

    user_id: int
    jti: UUID


@dataclass(frozen=True)
class AuthSessionDTO:
    """A full session: what every session-establishing endpoint returns."""

    access_token: str
    refresh_token: str
    access_expires_at: datetime
    user: UserOutputDTO


@dataclass(frozen=True)
class RegisterResultDTO:
    """Sign-up returns a live session *and* (still, best-effort) a verification
    email — the email no longer gates login, it's just a nice-to-have."""

    session: AuthSessionDTO
    verification_token: str
