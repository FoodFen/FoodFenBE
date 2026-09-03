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
)
from src.application.use_cases.login import LoginUseCase
from src.application.use_cases.logout import LogoutUseCase
from src.application.use_cases.refresh_token import RefreshTokenUseCase
from src.application.use_cases.register_user import RegisterUserUseCase
from src.domain.entities.refresh_token import RefreshToken
from src.domain.entities.user import User
from src.domain.exceptions import (
    InvalidCredentialsException,
    InvalidTokenException,
    UserAlreadyExistsException,
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
    """Opaque strings; refresh tokens carry their claims in a side table."""

    def __init__(self) -> None:
        self._refresh: dict[str, RefreshClaims] = {}
        self._n = 0

    def issue_access_token(self, user_id):
        self._n += 1
        return IssuedToken(f"access-{self._n}", datetime.now(UTC) + timedelta(minutes=30))

    def issue_refresh_token(self, user_id, jti):
        self._n += 1
        tok = f"refresh-{self._n}"
        self._refresh[tok] = RefreshClaims(user_id=user_id, jti=jti)
        return IssuedToken(tok, datetime.now(UTC) + timedelta(days=30))

    def read_access_token(self, token):
        raise NotImplementedError

    def read_refresh_token(self, token):
        if token not in self._refresh:
            raise InvalidTokenException("unknown token")
        return self._refresh[token]


def _wire():
    return FakeUserRepo(), FakeRefreshRepo(), FakeHasher(), FakeTokens()


async def test_register_creates_user_and_returns_pair():
    users, refresh, hasher, tokens = _wire()
    uc = RegisterUserUseCase(users=users, refresh_tokens=refresh, hasher=hasher, tokens=tokens)

    pair = await uc.execute(RegisterInputDTO(email="A@Ex.com", password="hunter2!!", name=" Al "))

    stored = await users.get_by_email("a@ex.com")
    assert stored is not None
    assert stored.password_hash == "hashed::hunter2!!"
    assert stored.name == "Al"
    assert pair.access_token and pair.refresh_token
    assert len(refresh.rows) == 1


async def test_register_rejects_weak_password():
    users, refresh, hasher, tokens = _wire()
    uc = RegisterUserUseCase(users=users, refresh_tokens=refresh, hasher=hasher, tokens=tokens)
    with pytest.raises(WeakPasswordException):
        await uc.execute(RegisterInputDTO(email="a@ex.com", password="short", name="Al"))


async def test_register_rejects_duplicate_email():
    users, refresh, hasher, tokens = _wire()
    uc = RegisterUserUseCase(users=users, refresh_tokens=refresh, hasher=hasher, tokens=tokens)
    await uc.execute(RegisterInputDTO(email="dup@ex.com", password="password1", name="One"))
    with pytest.raises(UserAlreadyExistsException):
        await uc.execute(RegisterInputDTO(email="dup@ex.com", password="password1", name="Two"))


async def test_login_ok_then_bad_password():
    users, refresh, hasher, tokens = _wire()
    await RegisterUserUseCase(users, refresh, hasher, tokens).execute(
        RegisterInputDTO(email="u@ex.com", password="password1", name="U")
    )
    login = LoginUseCase(users=users, refresh_tokens=refresh, hasher=hasher, tokens=tokens)

    pair = await login.execute(LoginInputDTO(email="u@ex.com", password="password1"))
    assert pair.refresh_token

    with pytest.raises(InvalidCredentialsException):
        await login.execute(LoginInputDTO(email="u@ex.com", password="wrong-one"))


async def test_login_unknown_email_same_error():
    users, refresh, hasher, tokens = _wire()
    login = LoginUseCase(users=users, refresh_tokens=refresh, hasher=hasher, tokens=tokens)
    with pytest.raises(InvalidCredentialsException):
        await login.execute(LoginInputDTO(email="nobody@ex.com", password="whatever1"))


async def test_refresh_rotates_and_old_token_dies():
    users, refresh, hasher, tokens = _wire()
    pair = await RegisterUserUseCase(users, refresh, hasher, tokens).execute(
        RegisterInputDTO(email="r@ex.com", password="password1", name="R")
    )
    refresher = RefreshTokenUseCase(refresh_tokens=refresh, tokens=tokens)

    new_pair = await refresher.execute(RefreshInputDTO(refresh_token=pair.refresh_token))
    assert new_pair.refresh_token != pair.refresh_token

    # the original is now revoked
    with pytest.raises(InvalidTokenException):
        await refresher.execute(RefreshInputDTO(refresh_token=pair.refresh_token))


async def test_refresh_rejects_expired_row():
    users, refresh, hasher, tokens = _wire()
    uid, jti = uuid4(), uuid4()
    claims = RefreshClaims(user_id=uid, jti=jti)
    tokens._refresh["stale"] = claims
    refresh.rows[jti] = RefreshToken(
        id=uuid4(), user_id=uid, jti=jti,
        expires_at=datetime.now(UTC) - timedelta(seconds=1),
    )
    refresher = RefreshTokenUseCase(refresh_tokens=refresh, tokens=tokens)
    with pytest.raises(InvalidTokenException):
        await refresher.execute(RefreshInputDTO(refresh_token="stale"))


async def test_logout_revokes_and_is_idempotent():
    users, refresh, hasher, tokens = _wire()
    pair = await RegisterUserUseCase(users, refresh, hasher, tokens).execute(
        RegisterInputDTO(email="o@ex.com", password="password1", name="O")
    )
    logout = LogoutUseCase(refresh_tokens=refresh, tokens=tokens)

    await logout.execute(RefreshInputDTO(refresh_token=pair.refresh_token))
    assert all(r.revoked_at is not None for r in refresh.rows.values())

    # second call: no token to revoke, still succeeds
    await logout.execute(RefreshInputDTO(refresh_token=pair.refresh_token))
    await logout.execute(RefreshInputDTO(refresh_token="garbage"))
