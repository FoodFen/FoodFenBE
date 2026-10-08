"""SocialSignInUseCase unit tests: fake verifier / repos. No DB, no real JWKS call."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest

from src.application.dtos.auth import IssuedToken, SocialSignInInputDTO, VerifiedIdentity
from src.application.use_cases.social_sign_in import SocialSignInUseCase
from src.domain.entities.refresh_token import RefreshToken
from src.domain.entities.social_identity import SocialIdentity
from src.domain.entities.user import User
from src.domain.enums import AuthProvider
from src.domain.exceptions import InvalidTokenException, InvalidUserAttributeException, UserNotFoundException


class FakeUserRepo:
    def __init__(self) -> None:
        self._by_id: dict[int, User] = {}
        self._next_id = 1

    async def get_by_id(self, user_id):
        return self._by_id.get(user_id)

    async def get_by_email(self, email):
        return next((u for u in self._by_id.values() if u.email == email), None)

    async def create(self, user):
        user.id = self._next_id
        self._next_id += 1
        self._by_id[user.id] = user
        return user

    async def update(self, user):
        if user.id not in self._by_id:
            raise UserNotFoundException(str(user.id))
        self._by_id[user.id] = user
        return user

    def seed(self, user: User) -> User:
        """Insert a pre-existing (e.g. password-based) account for linking tests."""
        user.id = self._next_id
        self._next_id += 1
        self._by_id[user.id] = user
        return user


class FakeSocialIdentityRepo:
    def __init__(self) -> None:
        self._by_key: dict[tuple[AuthProvider, str], SocialIdentity] = {}

    async def get_by_provider_subject(self, provider, provider_user_id):
        return self._by_key.get((provider, provider_user_id))

    async def create(self, identity):
        self._by_key[(identity.provider, identity.provider_user_id)] = identity
        return identity


class FakeRefreshRepo:
    def __init__(self) -> None:
        self.rows: dict[UUID, RefreshToken] = {}

    async def add(self, token):
        self.rows[token.jti] = token
        return token

    async def get_by_jti(self, jti):
        return self.rows.get(jti)

    async def revoke(self, token):
        self.rows[token.jti].revoked_at = token.revoked_at


class FakeVerifier:
    """Maps a raw token string to a canned identity, or raises."""

    def __init__(self) -> None:
        self._identities: dict[str, VerifiedIdentity] = {}

    def stub(self, token: str, identity: VerifiedIdentity) -> None:
        self._identities[token] = identity

    def verify(self, provider, id_token):
        if id_token not in self._identities:
            raise InvalidTokenException("invalid identity token")
        return self._identities[id_token]


class FakeTokens:
    def __init__(self) -> None:
        self._n = 0

    def issue_access_token(self, user_id):
        self._n += 1
        return IssuedToken(f"access-{self._n}", datetime.now(UTC) + timedelta(minutes=30))

    def issue_refresh_token(self, user_id, jti):
        self._n += 1
        return IssuedToken(f"refresh-{self._n}", datetime.now(UTC) + timedelta(days=30))


def _wire():
    return FakeUserRepo(), FakeSocialIdentityRepo(), FakeRefreshRepo(), FakeVerifier(), FakeTokens()


def _use_case(users, socials, refresh, verifier, tokens):
    return SocialSignInUseCase(
        users=users,
        social_identities=socials,
        refresh_tokens=refresh,
        verifier=verifier,
        tokens=tokens,
    )


async def test_new_google_user_is_created_and_verified():
    users, socials, refresh, verifier, tokens = _wire()
    verifier.stub(
        "good-token",
        VerifiedIdentity(subject="google-sub-1", email="new@example.com", email_verified=True),
    )
    uc = _use_case(users, socials, refresh, verifier, tokens)

    session = await uc.execute(
        SocialSignInInputDTO(provider=AuthProvider.GOOGLE, id_token="good-token")
    )

    assert session.user.email == "new@example.com"
    stored = await users.get_by_email("new@example.com")
    assert stored.is_email_verified  # provider already verified it
    assert stored.password_hash is None  # passwordless account

    linked = await socials.get_by_provider_subject(AuthProvider.GOOGLE, "google-sub-1")
    assert linked is not None
    assert linked.user_id == stored.id


async def test_apple_first_time_uses_token_email_and_body_full_name():
    users, socials, refresh, verifier, tokens = _wire()
    verifier.stub(
        "apple-token",
        VerifiedIdentity(subject="apple-sub-1", email="ada@example.com", email_verified=True),
    )
    uc = _use_case(users, socials, refresh, verifier, tokens)

    session = await uc.execute(
        SocialSignInInputDTO(
            provider=AuthProvider.APPLE, id_token="apple-token", full_name="Ada Lovelace"
        )
    )

    assert session.user.email == "ada@example.com"
    assert session.user.name == "Ada Lovelace"


async def test_unverified_token_email_is_rejected():
    users, socials, refresh, verifier, tokens = _wire()
    users.seed(User.create(email="victim@example.com", name="Victim", password_hash="h"))
    verifier.stub(
        "unverified-token",
        VerifiedIdentity(subject="g-x", email="victim@example.com", email_verified=False),
    )
    uc = _use_case(users, socials, refresh, verifier, tokens)

    with pytest.raises(InvalidUserAttributeException):
        await uc.execute(
            SocialSignInInputDTO(provider=AuthProvider.GOOGLE, id_token="unverified-token")
        )


async def test_returning_user_reuses_linked_account_without_new_email():
    users, socials, refresh, verifier, tokens = _wire()
    verifier.stub(
        "good-token",
        VerifiedIdentity(subject="google-sub-1", email="new@example.com", email_verified=True),
    )
    uc = _use_case(users, socials, refresh, verifier, tokens)
    first = await uc.execute(SocialSignInInputDTO(provider=AuthProvider.GOOGLE, id_token="good-token"))

    # second sign-in: same subject, no email/fullName in the request at all
    # (a returning user's client can't resupply what it no longer has)
    again = await uc.execute(SocialSignInInputDTO(provider=AuthProvider.GOOGLE, id_token="good-token"))

    assert again.user.id == first.user.id
    assert len(socials._by_key) == 1  # no duplicate identity row


async def test_auto_links_to_existing_password_account_with_same_email():
    users, socials, refresh, verifier, tokens = _wire()
    existing = users.seed(User.create(email="shared@example.com", name="Existing", password_hash="hashed::x"))
    verifier.stub(
        "good-token",
        VerifiedIdentity(subject="google-sub-9", email="shared@example.com", email_verified=True),
    )
    uc = _use_case(users, socials, refresh, verifier, tokens)

    session = await uc.execute(
        SocialSignInInputDTO(provider=AuthProvider.GOOGLE, id_token="good-token")
    )

    assert session.user.id == existing.id  # signed into the SAME account, not a new one
    linked = await socials.get_by_provider_subject(AuthProvider.GOOGLE, "google-sub-9")
    assert linked.user_id == existing.id


async def test_auto_link_to_unverified_existing_account_invalidates_its_password():
    """Pre-account-takeover guard: email verification is non-gating at
    sign-up, so an attacker can register a password account with an email
    they don't own. If the real owner later proves ownership via a
    provider-verified social sign-in, auto-linking must not leave the
    attacker's password credential valid on the now-legitimized account."""
    users, socials, refresh, verifier, tokens = _wire()
    existing = users.seed(
        User.create(email="squatted@example.com", name="Squatter", password_hash="hashed::attacker")
    )
    assert not existing.is_email_verified
    verifier.stub(
        "good-token",
        VerifiedIdentity(subject="google-sub-9", email="squatted@example.com", email_verified=True),
    )
    uc = _use_case(users, socials, refresh, verifier, tokens)

    session = await uc.execute(
        SocialSignInInputDTO(provider=AuthProvider.GOOGLE, id_token="good-token")
    )

    assert session.user.id == existing.id
    stored = await users.get_by_id(existing.id)
    assert stored.password_hash is None
    assert stored.is_email_verified


async def test_auto_link_to_already_verified_existing_account_keeps_its_password():
    """No overreach: if the existing account's email was already verified
    through our own flow, ownership is already proven — the password stays
    valid (this is the ordinary "add a second sign-in method" case, not a
    suspected squat)."""
    users, socials, refresh, verifier, tokens = _wire()
    existing = users.seed(
        User.create(email="verified@example.com", name="Real Owner", password_hash="hashed::real")
    )
    existing.verify_email(datetime.now(UTC))
    verifier.stub(
        "good-token",
        VerifiedIdentity(subject="google-sub-10", email="verified@example.com", email_verified=True),
    )
    uc = _use_case(users, socials, refresh, verifier, tokens)

    await uc.execute(SocialSignInInputDTO(provider=AuthProvider.GOOGLE, id_token="good-token"))

    stored = await users.get_by_id(existing.id)
    assert stored.password_hash == "hashed::real"


async def test_missing_email_everywhere_is_rejected():
    users, socials, refresh, verifier, tokens = _wire()
    verifier.stub("no-email", VerifiedIdentity(subject="sub-x", email=None, email_verified=False))
    uc = _use_case(users, socials, refresh, verifier, tokens)

    with pytest.raises(InvalidUserAttributeException):
        await uc.execute(SocialSignInInputDTO(provider=AuthProvider.APPLE, id_token="no-email"))


async def test_bad_token_propagates_invalid_token_exception():
    users, socials, refresh, verifier, tokens = _wire()
    uc = _use_case(users, socials, refresh, verifier, tokens)

    with pytest.raises(InvalidTokenException):
        await uc.execute(SocialSignInInputDTO(provider=AuthProvider.GOOGLE, id_token="garbage"))


async def test_orphaned_identity_raises_not_found():
    """Defensive: the linked user row is gone (e.g. hard-deleted) even though
    the social_identities row survived — should not silently issue a session
    for a nonexistent user."""
    users, socials, refresh, verifier, tokens = _wire()
    await socials.create(SocialIdentity.create(user_id=999_999, provider=AuthProvider.GOOGLE, provider_user_id="ghost"))
    verifier.stub("ghost-token", VerifiedIdentity(subject="ghost", email="x@example.com", email_verified=True))
    uc = _use_case(users, socials, refresh, verifier, tokens)

    with pytest.raises(UserNotFoundException):
        await uc.execute(SocialSignInInputDTO(provider=AuthProvider.GOOGLE, id_token="ghost-token"))
