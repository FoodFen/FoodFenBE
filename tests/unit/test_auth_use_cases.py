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
    RequestPasswordResetInputDTO,
    ResendVerificationInputDTO,
    ResetPasswordInputDTO,
)
from src.application.use_cases.login import LoginUseCase
from src.application.use_cases.logout import LogoutUseCase
from src.application.use_cases.refresh_token import RefreshTokenUseCase
from src.application.use_cases.register_user import RegisterUserUseCase
from src.application.use_cases.request_password_reset import RequestPasswordResetUseCase
from src.application.use_cases.resend_verification import ResendVerificationUseCase
from src.application.use_cases.reset_password import ResetPasswordUseCase
from src.application.use_cases.verify_email import VerifyEmailUseCase
from src.domain.entities.refresh_token import RefreshToken
from src.domain.entities.user import User
from src.domain.exceptions import (
    InvalidCredentialsException,
    InvalidTokenException,
    UserAlreadyExistsException,
    UserNotFoundException,
    WeakPasswordException,
)


class FakeUserRepo:
    """Simulates the autoincrement PK: ``create`` assigns the id."""

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
    """Opaque strings; refresh/verification/reset tokens carry claims in side tables."""

    def __init__(self) -> None:
        self._refresh: dict[str, RefreshClaims] = {}
        self._verify: dict[str, int] = {}
        self._reset: dict[str, int] = {}
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

    def issue_password_reset_token(self, user_id):
        self._n += 1
        tok = f"reset-{self._n}"
        self._reset[tok] = user_id
        return IssuedToken(tok, datetime.now(UTC) + timedelta(hours=1))

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

    def read_password_reset_token(self, token):
        if token not in self._reset:
            raise InvalidTokenException("unknown token")
        return self._reset[token]


def _wire():
    return FakeUserRepo(), FakeRefreshRepo(), FakeHasher(), FakeTokens()


async def _register(users, refresh, hasher, tokens, email="u@ex.com", pw="password1", name="U"):
    return await RegisterUserUseCase(
        users=users, refresh_tokens=refresh, hasher=hasher, tokens=tokens
    ).execute(RegisterInputDTO(email=email, password=pw, name=name))


async def _verify(users, tokens, token):
    await VerifyEmailUseCase(users=users, tokens=tokens).execute(token)


# --- register --------------------------------------------------------------


async def test_register_creates_user_and_returns_live_session():
    users, refresh, hasher, tokens = _wire()

    result = await _register(
        users, refresh, hasher, tokens, email="A@Ex.com", pw="hunter2!!", name=" Al "
    )

    stored = await users.get_by_email("a@ex.com")
    assert stored is not None
    assert stored.password_hash == "hashed::hunter2!!"
    assert stored.name == "Al"
    assert stored.email_verified_at is None  # not gated on this, but still unverified

    session = result.session
    assert session.access_token and session.refresh_token
    assert session.user.id == stored.id
    assert session.user.email == "a@ex.com"
    assert result.verification_token  # still sent, just not required


async def test_register_rejects_weak_password():
    users, refresh, hasher, tokens = _wire()
    with pytest.raises(WeakPasswordException):
        await _register(users, refresh, hasher, tokens, pw="short")


async def test_register_rejects_duplicate_email():
    users, refresh, hasher, tokens = _wire()
    await _register(users, refresh, hasher, tokens, email="dup@ex.com", name="One")
    with pytest.raises(UserAlreadyExistsException):
        await _register(users, refresh, hasher, tokens, email="dup@ex.com", name="Two")


async def test_register_allows_missing_display_name():
    users, refresh, hasher, tokens = _wire()
    result = await RegisterUserUseCase(
        users=users, refresh_tokens=refresh, hasher=hasher, tokens=tokens
    ).execute(RegisterInputDTO(email="noname@ex.com", password="password1", name=None))
    assert result.session.user.name is None


# --- verify (extra, not contract-required) ----------------------------------


async def test_verify_marks_user_verified():
    users, refresh, hasher, tokens = _wire()
    result = await _register(users, refresh, hasher, tokens)

    await _verify(users, tokens, result.verification_token)

    assert (await users.get_by_email("u@ex.com")).is_email_verified


async def test_verify_is_idempotent():
    users, refresh, hasher, tokens = _wire()
    result = await _register(users, refresh, hasher, tokens)
    await _verify(users, tokens, result.verification_token)
    first = (await users.get_by_email("u@ex.com")).email_verified_at
    await _verify(users, tokens, result.verification_token)
    assert (await users.get_by_email("u@ex.com")).email_verified_at == first


async def test_verify_rejects_bad_token():
    users, _refresh, _hasher, tokens = _wire()
    with pytest.raises(InvalidTokenException):
        await _verify(users, tokens, "nope")


# --- login --------------------------------------------------------------


async def test_login_works_without_verification():
    """Verification no longer gates login — the contract's sign-up already
    returns a live session, so sign-in for the same (still unverified) account
    must succeed too."""
    users, refresh, hasher, tokens = _wire()
    await _register(users, refresh, hasher, tokens)
    login = LoginUseCase(users=users, refresh_tokens=refresh, hasher=hasher, tokens=tokens)

    session = await login.execute(LoginInputDTO(email="u@ex.com", password="password1"))
    assert session.refresh_token
    assert session.user.email == "u@ex.com"


async def test_login_wrong_password():
    users, refresh, hasher, tokens = _wire()
    await _register(users, refresh, hasher, tokens)
    login = LoginUseCase(users=users, refresh_tokens=refresh, hasher=hasher, tokens=tokens)
    with pytest.raises(InvalidCredentialsException):
        await login.execute(LoginInputDTO(email="u@ex.com", password="wrong-one"))


async def test_login_unknown_email_same_error():
    users, refresh, hasher, tokens = _wire()
    login = LoginUseCase(users=users, refresh_tokens=refresh, hasher=hasher, tokens=tokens)
    with pytest.raises(InvalidCredentialsException):
        await login.execute(LoginInputDTO(email="nobody@ex.com", password="whatever1"))


# --- resend verification (extra) --------------------------------------------


async def test_resend_returns_dispatch_only_for_unverified_known_user():
    users, refresh, hasher, tokens = _wire()
    await _register(users, refresh, hasher, tokens)
    resend = ResendVerificationUseCase(users=users, tokens=tokens)

    assert await resend.execute(ResendVerificationInputDTO(email="ghost@ex.com")) is None

    again = await resend.execute(ResendVerificationInputDTO(email="u@ex.com"))
    assert again is not None
    await _verify(users, tokens, again.token)

    assert await resend.execute(ResendVerificationInputDTO(email="u@ex.com")) is None


# --- password reset (extra) -------------------------------------------------


async def test_request_password_reset_enumeration_safe():
    users, refresh, hasher, tokens = _wire()
    await _register(users, refresh, hasher, tokens)
    request_reset = RequestPasswordResetUseCase(users=users, tokens=tokens)

    assert await request_reset.execute(RequestPasswordResetInputDTO(email="ghost@ex.com")) is None

    dispatch = await request_reset.execute(RequestPasswordResetInputDTO(email="u@ex.com"))
    assert dispatch is not None
    assert dispatch.token


async def test_reset_password_changes_hash_and_allows_login_with_new_password():
    users, refresh, hasher, tokens = _wire()
    await _register(users, refresh, hasher, tokens)
    request_reset = RequestPasswordResetUseCase(users=users, tokens=tokens)
    dispatch = await request_reset.execute(RequestPasswordResetInputDTO(email="u@ex.com"))

    reset = ResetPasswordUseCase(users=users, hasher=hasher, tokens=tokens)
    await reset.execute(ResetPasswordInputDTO(token=dispatch.token, new_password="newpassword1"))

    login = LoginUseCase(users=users, refresh_tokens=refresh, hasher=hasher, tokens=tokens)
    with pytest.raises(InvalidCredentialsException):
        await login.execute(LoginInputDTO(email="u@ex.com", password="password1"))
    session = await login.execute(LoginInputDTO(email="u@ex.com", password="newpassword1"))
    assert session.access_token


async def test_reset_password_rejects_bad_token():
    users, _refresh, hasher, tokens = _wire()
    reset = ResetPasswordUseCase(users=users, hasher=hasher, tokens=tokens)
    with pytest.raises(InvalidTokenException):
        await reset.execute(ResetPasswordInputDTO(token="nope", new_password="newpassword1"))


# --- refresh / logout --------------------------------------------------------


async def test_refresh_rotates_and_old_token_dies():
    users, refresh, hasher, tokens = _wire()
    result = await _register(users, refresh, hasher, tokens)

    refresher = RefreshTokenUseCase(users=users, refresh_tokens=refresh, tokens=tokens)
    new_session = await refresher.execute(
        RefreshInputDTO(refresh_token=result.session.refresh_token)
    )
    assert new_session.refresh_token != result.session.refresh_token
    assert new_session.user.email == "u@ex.com"

    with pytest.raises(InvalidTokenException):
        await refresher.execute(RefreshInputDTO(refresh_token=result.session.refresh_token))


async def test_refresh_rejects_expired_row():
    users, refresh, _hasher, tokens = _wire()
    uid, jti = 1, uuid4()
    tokens._refresh["stale"] = RefreshClaims(user_id=uid, jti=jti)
    refresh.rows[jti] = RefreshToken(
        id=uuid4(), user_id=uid, jti=jti, expires_at=datetime.now(UTC) - timedelta(seconds=1)
    )
    refresher = RefreshTokenUseCase(users=users, refresh_tokens=refresh, tokens=tokens)
    with pytest.raises(InvalidTokenException):
        await refresher.execute(RefreshInputDTO(refresh_token="stale"))


async def test_logout_revokes_and_is_idempotent():
    users, refresh, hasher, tokens = _wire()
    result = await _register(users, refresh, hasher, tokens)

    logout = LogoutUseCase(refresh_tokens=refresh, tokens=tokens)
    await logout.execute(RefreshInputDTO(refresh_token=result.session.refresh_token))
    assert all(r.revoked_at is not None for r in refresh.rows.values())

    await logout.execute(RefreshInputDTO(refresh_token=result.session.refresh_token))
    await logout.execute(RefreshInputDTO(refresh_token="garbage"))
