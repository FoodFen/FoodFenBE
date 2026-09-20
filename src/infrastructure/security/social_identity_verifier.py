"""PyJWT implementation of ``SocialIdentityVerifierProtocol``.

Issuer and audience are checked by hand rather than via PyJWT's own
``issuer=``/``audience=`` options, to support a *list* of allowed audiences
without depending on PyJWT-version-specific list behaviour there.
"""

from __future__ import annotations

import jwt
from jwt import PyJWKClient

from src.application.dtos.auth import VerifiedIdentity
from src.domain.enums import AuthProvider
from src.domain.exceptions import InvalidTokenException

_GOOGLE_JWKS_URI = "https://www.googleapis.com/oauth2/v3/certs"
_GOOGLE_ISSUERS = frozenset({"accounts.google.com", "https://accounts.google.com"})

_APPLE_JWKS_URI = "https://appleid.apple.com/auth/keys"
_APPLE_ISSUERS = frozenset({"https://appleid.apple.com"})


def _as_bool(value: object) -> bool:
    """Google sends a real bool; Apple sends the string `"true"`/`"false"`."""
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() == "true"
    return False


class JwtSocialIdentityVerifier:
    def __init__(
        self,
        *,
        google_client_ids: frozenset[str],
        apple_client_ids: frozenset[str],
        google_jwks: PyJWKClient | None = None,
        apple_jwks: PyJWKClient | None = None,
    ) -> None:
        self._google_client_ids = google_client_ids
        self._apple_client_ids = apple_client_ids
        # Overridable so tests can inject a local keypair instead of a real JWKS fetch.
        self._google_jwks = google_jwks or PyJWKClient(_GOOGLE_JWKS_URI)
        self._apple_jwks = apple_jwks or PyJWKClient(_APPLE_JWKS_URI)

    def verify(self, provider: AuthProvider, id_token: str) -> VerifiedIdentity:
        if provider is AuthProvider.GOOGLE:
            return self._verify(
                id_token, self._google_jwks, _GOOGLE_ISSUERS, self._google_client_ids, provider
            )
        if provider is AuthProvider.APPLE:
            return self._verify(
                id_token, self._apple_jwks, _APPLE_ISSUERS, self._apple_client_ids, provider
            )
        raise InvalidTokenException(f"unsupported identity provider: {provider}")

    def _verify(
        self,
        id_token: str,
        jwks: PyJWKClient,
        allowed_issuers: frozenset[str],
        allowed_audiences: frozenset[str],
        provider: AuthProvider,
    ) -> VerifiedIdentity:
        if not allowed_audiences:
            # Misconfiguration -> fail loud (500), never silently accept any audience.
            raise RuntimeError(
                f"no OAuth client ids configured for provider {provider!r}; "
                f"set GOOGLE_OAUTH_CLIENT_IDS / APPLE_CLIENT_IDS"
            )

        try:
            signing_key = jwks.get_signing_key_from_jwt(id_token)
            # verify_aud=False: PyJWT refuses to decode any token with an `aud`
            # claim unless `audience=` is also passed — every real Google/Apple
            # token has one. We check audience ourselves, against a list, below.
            payload = jwt.decode(
                id_token, signing_key.key, algorithms=["RS256"], options={"verify_aud": False}
            )
        except jwt.PyJWTError as exc:
            raise InvalidTokenException(str(exc) or "invalid identity token") from exc

        if payload.get("iss") not in allowed_issuers:
            raise InvalidTokenException("identity token has an unexpected issuer")

        aud = payload.get("aud")
        auds = aud if isinstance(aud, list) else [aud]
        if not any(a in allowed_audiences for a in auds):
            raise InvalidTokenException("identity token audience does not match this app")

        subject = payload.get("sub")
        if not subject:
            raise InvalidTokenException("identity token is missing a subject")

        return VerifiedIdentity(
            subject=str(subject),
            email=payload.get("email"),
            email_verified=_as_bool(payload.get("email_verified")),
        )
