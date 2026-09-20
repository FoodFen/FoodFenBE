"""HTTP wire models for the auth endpoints — camelCase, per the front-end contract."""

from __future__ import annotations

from pydantic import Field

from src.adapters.schemas.base import CamelModel
from src.adapters.schemas.user_schemas import UserResponse
from src.application.dtos.auth import AuthSessionDTO
from src.domain.enums import AuthProvider


class SignUpRequest(CamelModel):
    email: str = Field(min_length=3, max_length=320)
    # 8..72: lower bound is the policy, upper bound is bcrypt's byte limit.
    password: str = Field(min_length=8, max_length=72)
    display_name: str | None = None


class SignInRequest(CamelModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=1, max_length=72)


class RefreshRequest(CamelModel):
    refresh_token: str = Field(min_length=1)


class SignOutRequest(CamelModel):
    refresh_token: str = Field(min_length=1)


class PasswordResetRequest(CamelModel):
    email: str = Field(min_length=3, max_length=320)


class ResendVerificationRequest(CamelModel):
    email: str = Field(min_length=3, max_length=320)


class ResetPasswordRequest(CamelModel):
    token: str = Field(min_length=1)
    new_password: str = Field(min_length=8, max_length=72)


class SocialSignInRequest(CamelModel):
    provider: AuthProvider
    id_token: str = Field(min_length=1)
    full_name: str | None = None  # Apple only, first authorization only
    email: str | None = None


class MessageResponse(CamelModel):
    message: str


class AuthSessionResponse(CamelModel):
    access_token: str
    refresh_token: str
    expires_at: int  # epoch milliseconds — the contract's type, not seconds/ISO
    user: UserResponse

    @classmethod
    def from_dto(cls, dto: AuthSessionDTO) -> AuthSessionResponse:
        return cls(
            access_token=dto.access_token,
            refresh_token=dto.refresh_token,
            expires_at=int(dto.access_expires_at.timestamp() * 1000),
            user=UserResponse.from_dto(dto.user),
        )
