"""JwtSocialIdentityVerifier tests: real RS256 signing against a local keypair,
no network call to Google/Apple. The JWKS lookup is swapped for a fake that
returns our own test public key, so signature/issuer/audience/expiry checks
run for real.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from src.domain.enums import AuthProvider
from src.domain.exceptions import InvalidTokenException
from src.infrastructure.security.social_identity_verifier import (
    JwtSocialIdentityVerifier,
    _as_bool,
)


def _generate_keypair() -> tuple[bytes, bytes]:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    public_pem = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    return private_pem, public_pem


PRIVATE_PEM, PUBLIC_PEM = _generate_keypair()
OTHER_PRIVATE_PEM, _OTHER_PUBLIC_PEM = _generate_keypair()

_GOOGLE_CLIENT = "my-google-client"
_APPLE_CLIENT = "com.example.app"


class _FakeSigningKey:
    def __init__(self, key: bytes) -> None:
        self.key = key


class _FakeJwks:
    """Stands in for ``PyJWKClient`` — always hands back our own test key."""

    def __init__(self, public_pem: bytes = PUBLIC_PEM) -> None:
        self._public_pem = public_pem

    def get_signing_key_from_jwt(self, token: str) -> _FakeSigningKey:
        return _FakeSigningKey(self._public_pem)


def _verifier(**overrides) -> JwtSocialIdentityVerifier:
    return JwtSocialIdentityVerifier(
        google_client_ids=frozenset({_GOOGLE_CLIENT}),
        apple_client_ids=frozenset({_APPLE_CLIENT}),
        google_jwks=_FakeJwks(),
        apple_jwks=_FakeJwks(),
        **overrides,
    )


def _token(
    *,
    iss: str,
    aud: str,
    sub: str = "user-123",
    exp_delta: timedelta = timedelta(minutes=5),
    extra: dict | None = None,
    key: bytes = PRIVATE_PEM,
) -> str:
    now = datetime.now(UTC)
    payload = {
        "iss": iss,
        "aud": aud,
        "sub": sub,
        "iat": now,
        "exp": now + exp_delta,
        **(extra or {}),
    }
    return jwt.encode(payload, key, algorithm="RS256")


def test_valid_google_token_returns_identity():
    token = _token(
        iss="https://accounts.google.com",
        aud=_GOOGLE_CLIENT,
        extra={"email": "a@example.com", "email_verified": True},
    )
    identity = _verifier().verify(AuthProvider.GOOGLE, token)
    assert identity.subject == "user-123"
    assert identity.email == "a@example.com"
    assert identity.email_verified is True


def test_valid_apple_token_with_string_email_verified():
    token = _token(
        iss="https://appleid.apple.com",
        aud=_APPLE_CLIENT,
        extra={"email": "a@example.com", "email_verified": "true"},
    )
    identity = _verifier().verify(AuthProvider.APPLE, token)
    assert identity.email_verified is True


def test_google_bare_issuer_variant_accepted():
    token = _token(iss="accounts.google.com", aud=_GOOGLE_CLIENT)
    identity = _verifier().verify(AuthProvider.GOOGLE, token)
    assert identity.subject == "user-123"


def test_wrong_issuer_rejected():
    token = _token(iss="https://evil.example.com", aud=_GOOGLE_CLIENT)
    with pytest.raises(InvalidTokenException):
        _verifier().verify(AuthProvider.GOOGLE, token)


def test_wrong_audience_rejected():
    token = _token(iss="https://accounts.google.com", aud="someone-elses-client")
    with pytest.raises(InvalidTokenException):
        _verifier().verify(AuthProvider.GOOGLE, token)


def test_expired_token_rejected():
    token = _token(
        iss="https://accounts.google.com", aud=_GOOGLE_CLIENT, exp_delta=timedelta(minutes=-5)
    )
    with pytest.raises(InvalidTokenException):
        _verifier().verify(AuthProvider.GOOGLE, token)


def test_tampered_signature_rejected():
    """Signed by a DIFFERENT private key — the fake JWKS still serves our real
    public key, so this must fail signature verification."""
    token = _token(iss="https://accounts.google.com", aud=_GOOGLE_CLIENT, key=OTHER_PRIVATE_PEM)
    with pytest.raises(InvalidTokenException):
        _verifier().verify(AuthProvider.GOOGLE, token)


def test_missing_subject_rejected():
    token = _token(iss="https://accounts.google.com", aud=_GOOGLE_CLIENT, sub="")
    with pytest.raises(InvalidTokenException):
        _verifier().verify(AuthProvider.GOOGLE, token)


def test_unconfigured_client_ids_fail_closed_not_open():
    verifier = JwtSocialIdentityVerifier(
        google_client_ids=frozenset(),
        apple_client_ids=frozenset(),
        google_jwks=_FakeJwks(),
        apple_jwks=_FakeJwks(),
    )
    token = _token(iss="https://accounts.google.com", aud="anything-at-all")
    with pytest.raises(RuntimeError):
        verifier.verify(AuthProvider.GOOGLE, token)


def test_as_bool_normalizes_google_and_apple_shapes():
    assert _as_bool(True) is True
    assert _as_bool(False) is False
    assert _as_bool("true") is True
    assert _as_bool("True") is True
    assert _as_bool("false") is False
    assert _as_bool(None) is False
