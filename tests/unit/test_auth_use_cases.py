"""Auth use-case unit tests: fake hasher / token service / repos. No DB, no JWT lib."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest

from src.application.dtos.auth import (
    IssuedToken,
    LoginInputDTO,
    RefreshClaims,
    RefreshInputDTO,
    RegisterInputDTO,
    ResendVerificationInputDTO,
)
from src.application.use_cases.login import LoginUseCase
from src.application.use_cases.logout import LogoutUseCase
from src.application.use_cases.refresh_token import RefreshTokenUseCase
from src.application.use_cases.register_user import RegisterUserUseCase
from src.application.use_cases.resend_verification import ResendVerificationUseCase
from src.application.use_cases.verify_email import VerifyEmailUseCase
from src.domain.entities.refresh_token import RefreshToken
from src.domain.entities.user import User
from src.domain.exceptions import (
    EmailNotVerifiedException,
    InvalidCredentialsException,
    InvalidTokenException,
    UserAlreadyExistsException,
    UserNotFoundException,
    WeakPasswordException,
)


class FakeUserRepo:
    def __init__(self) -> None:
        self._by_id: dict[UUID, User] = {}

    async def get_by_id(self, user_id):
        return self._by_id.get(user_id)

    async def get_by_email(self, email):
        return next((u for u in self._by_id.values() if u.email == email), None)

    async def create(self, user):
        self._by_id[user.id] = user
        return user

    async def update(self, user):
        if user.id not in self._by_id:
            raise UserNotFoundException(str(user.id))
        self._by_id[user.id] = user
        return user


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


class FakeHasher:
    def hash(self, plain: str) -> str:
        return f"hashed::{plain}"

    def verify(self, plain: str, hashed: str) -> bool:
        return hashed == f"hashed::{plain}"


class FakeTokens:
    """Opaque strings; refresh/verification tokens carry claims in side tables."""

    def __init__(self) -> None:
        self._refresh: dict[str, RefreshClaims] = {}
        self._verify: dict[str, UUID] = {}
        self._n = 0

    def issue_access_token(self, user_id):
        self._n += 1
        return IssuedToken(f"access-{self._n}", datetime.now(UTC) + timedelta(minutes=30))

    def issue_refresh_token(self, user_id, jti):
        self._n += 1
        tok = f"refresh-{self._n}"
        self._refresh[tok] = RefreshClaims(user_id=user_id, jti=jti)
        return IssuedToken(tok, datetime.now(UTC) + timedelta(days=30))

    def issue_verification_token(self, user_id):
        self._n += 1
        tok = f"verify-{self._n}"
        self._verify[tok] = user_id
        return IssuedToken(tok, datetime.now(UTC) + timedelta(hours=24))

    def read_access_token(self, token):
        raise NotImplementedError

    def read_refresh_token(self, token):
        if token not in self._refresh:
            raise InvalidTokenException("unknown token")
        return self._refresh[token]

    def read_verification_token(self, token):
        if token not in self._verify:
            raise InvalidTokenException("unknown token")
        return self._verify[token]


def _wire():
    return FakeUserRepo(), FakeRefreshRepo(), FakeHasher(), FakeTokens()


async def _register(users, hasher, tokens, email="u@ex.com", pw="password1", name="U"):
    return await RegisterUserUseCase(users=users, hasher=hasher, tokens=tokens).execute(
        RegisterInputDTO(email=email, password=pw, name=name)
    )


async def _verify(users, tokens, token):
    await VerifyEmailUseCase(users=users, tokens=tokens).execute(token)


# --- register --------------------------------------------------------------


async def test_register_creates_unverified_user_and_returns_dispatch():
    users, _refresh, hasher, tokens = _wire()

    dispatch = await _register(
        users, hasher, tokens, email="A@Ex.com", pw="hunter2!!", name=" Al "
    )

    stored = await users.get_by_email("a@ex.com")
    assert stored is not None
    assert stored.password_hash == "hashed::hunter2!!"
    assert stored.name == "Al"
    assert stored.email_verified_at is None
    assert dispatch.email == "a@ex.com"
    assert dispatch.token


async def test_register_rejects_weak_password():
    users, _refresh, hasher, tokens = _wire()
    with pytest.raises(WeakPasswordException):
        await _register(users, hasher, tokens, pw="short")


async def test_register_rejects_duplicate_email():
    users, _refresh, hasher, tokens = _wire()
    await _register(users, hasher, tokens, email="dup@ex.com", name="One")
    with pytest.raises(UserAlreadyExistsException):
        await _register(users, hasher, tokens, email="dup@ex.com", name="Two")


# --- verify ---------------------------------------------------------------


async def test_verify_marks_user_verified():
    users, _refresh, hasher, tokens = _wire()
    dispatch = await _register(users, hasher, tokens)

    await _verify(users, tokens, dispatch.token)

    assert (await users.get_by_email("u@ex.com")).is_email_verified


async def test_verify_is_idempotent():
    users, _refresh, hasher, tokens = _wire()
    dispatch = await _register(users, hasher, tokens)
    await _verify(users, tokens, dispatch.token)
    first = (await users.get_by_email("u@ex.com")).email_verified_at
    await _verify(users, tokens, dispatch.token)
    assert (await users.get_by_email("u@ex.com")).email_verified_at == first


async def test_verify_rejects_bad_token():
    users, _refresh, _hasher, tokens = _wire()
    with pytest.raises(InvalidTokenException):
        await _verify(users, tokens, "nope")


# --- login --------------------------------------------------------------


async def test_login_blocked_until_verified():
    users, refresh, hasher, tokens = _wire()
    dispatch = await _register(users, hasher, tokens)
    login = LoginUseCase(users=users, refresh_tokens=refresh, hasher=hasher, tokens=tokens)

    with pytest.raises(EmailNotVerifiedException):
        await login.execute(LoginInputDTO(email="u@ex.com", password="password1"))

    await _verify(users, tokens, dispatch.token)
    pair = await login.execute(LoginInputDTO(email="u@ex.com", password="password1"))
    assert pair.refresh_token


async def test_login_wrong_password_before_verify_still_invalid_credentials():
    users, refresh, hasher, tokens = _wire()
    await _register(users, hasher, tokens)
    login = LoginUseCase(users=users, refresh_tokens=refresh, hasher=hasher, tokens=tokens)
    with pytest.raises(InvalidCredentialsException):
        await login.execute(LoginInputDTO(email="u@ex.com", password="wrong-one"))


async def test_login_unknown_email_same_error():
    users, refresh, hasher, tokens = _wire()
    login = LoginUseCase(users=users, refresh_tokens=refresh, hasher=hasher, tokens=tokens)
    with pytest.raises(InvalidCredentialsException):
        await login.execute(LoginInputDTO(email="nobody@ex.com", password="whatever1"))


# --- resend -------------------------------------------------------------


async def test_resend_returns_dispatch_only_for_unverified_known_user():
    users, _refresh, hasher, tokens = _wire()
    await _register(users, hasher, tokens)
    resend = ResendVerificationUseCase(users=users, tokens=tokens)

    assert await resend.execute(ResendVerificationInputDTO(email="ghost@ex.com")) is None

    again = await resend.execute(ResendVerificationInputDTO(email="u@ex.com"))
    assert again is not None
    await _verify(users, tokens, again.token)

    assert await resend.execute(ResendVerificationInputDTO(email="u@ex.com")) is None


# --- refresh / logout (verified path) ---------------------------------------


async def test_refresh_rotates_and_old_token_dies():
    users, refresh, hasher, tokens = _wire()
    dispatch = await _register(users, hasher, tokens)
    await _verify(users, tokens, dispatch.token)
    login = LoginUseCase(users=users, refresh_tokens=refresh, hasher=hasher, tokens=tokens)
    pair = await login.execute(LoginInputDTO(email="u@ex.com", password="password1"))

    refresher = RefreshTokenUseCase(refresh_tokens=refresh, tokens=tokens)
    new_pair = await refresher.execute(RefreshInputDTO(refresh_token=pair.refresh_token))
    assert new_pair.refresh_token != pair.refresh_token

    with pytest.raises(InvalidTokenException):
        await refresher.execute(RefreshInputDTO(refresh_token=pair.refresh_token))


async def test_refresh_rejects_expired_row():
    _users, refresh, _hasher, tokens = _wire()
    uid, jti = uuid4(), uuid4()
    tokens._refresh["stale"] = RefreshClaims(user_id=uid, jti=jti)
    refresh.rows[jti] = RefreshToken(
        id=uuid4(), user_id=uid, jti=jti, expires_at=datetime.now(UTC) - timedelta(seconds=1)
    )
    refresher = RefreshTokenUseCase(refresh_tokens=refresh, tokens=tokens)
    with pytest.raises(InvalidTokenException):
        await refresher.execute(RefreshInputDTO(refresh_token="stale"))


async def test_logout_revokes_and_is_idempotent():
    users, refresh, hasher, tokens = _wire()
    dispatch = await _register(users, hasher, tokens)
    await _verify(users, tokens, dispatch.token)
    login = LoginUseCase(users=users, refresh_tokens=refresh, hasher=hasher, tokens=tokens)
    pair = await login.execute(LoginInputDTO(email="u@ex.com", password="password1"))

    logout = LogoutUseCase(refresh_tokens=refresh, tokens=tokens)
    await logout.execute(RefreshInputDTO(refresh_token=pair.refresh_token))
    assert all(r.revoked_at is not None for r in refresh.rows.values())

    await logout.execute(RefreshInputDTO(refresh_token=pair.refresh_token))
    await logout.execute(RefreshInputDTO(refresh_token="garbage"))
