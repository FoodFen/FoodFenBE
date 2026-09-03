"""PyJWT implementation of ``TokenServiceProtocol`` (HS256 by default)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

import jwt

from src.application.dtos.auth import IssuedToken, RefreshClaims
from src.domain.exceptions import InvalidTokenException

_ACCESS = "access"
_REFRESH = "refresh"


class JwtTokenService:
    def __init__(
        self,
        secret: str,
        algorithm: str,
        access_ttl: timedelta,
        refresh_ttl: timedelta,
    ) -> None:
        self._secret = secret
        self._algorithm = algorithm
        self._access_ttl = access_ttl
        self._refresh_ttl = refresh_ttl

    def issue_access_token(self, user_id: UUID) -> IssuedToken:
        return self._issue(user_id, _ACCESS, self._access_ttl, {})

    def issue_refresh_token(self, user_id: UUID, jti: UUID) -> IssuedToken:
        return self._issue(user_id, _REFRESH, self._refresh_ttl, {"jti": str(jti)})

    def read_access_token(self, token: str) -> UUID:
        payload = self._decode(token, _ACCESS)
        return UUID(payload["sub"])

    def read_refresh_token(self, token: str) -> RefreshClaims:
        payload = self._decode(token, _REFRESH)
        try:
            return RefreshClaims(user_id=UUID(payload["sub"]), jti=UUID(payload["jti"]))
        except (KeyError, ValueError) as exc:
            raise InvalidTokenException("refresh token is missing claims") from exc

    def _issue(
        self, user_id: UUID, token_type: str, ttl: timedelta, extra: dict[str, str]
    ) -> IssuedToken:
        now = datetime.now(UTC)
        expires_at = now + ttl
        payload = {"sub": str(user_id), "type": token_type, "iat": now, "exp": expires_at, **extra}
        return IssuedToken(
            token=jwt.encode(payload, self._secret, algorithm=self._algorithm),
            expires_at=expires_at,
        )

    def _decode(self, token: str, expected_type: str) -> dict:
        try:
            payload = jwt.decode(token, self._secret, algorithms=[self._algorithm])
        except jwt.PyJWTError as exc:
            raise InvalidTokenException(str(exc) or "invalid token") from exc
        if payload.get("type") != expected_type:
            raise InvalidTokenException(f"expected a {expected_type} token")
        return payload
