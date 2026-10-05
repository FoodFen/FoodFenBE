"""Auth primitives: password hasher, token service, and the current-user guard.

The hasher and token service are process-wide singletons — they only hold config
(bcrypt cost, JWT secret/TTLs) and are otherwise stateless, so there is no reason
to rebuild them per request.
"""

from __future__ import annotations

from datetime import date, timedelta
from functools import lru_cache
from typing import Annotated

from fastapi import Depends, Header, Request
from fastapi.security import OAuth2PasswordBearer

from src.application.dtos.ai_trial import AiCallerDTO
from src.application.ports.ai_chat_provider import AiChatProviderProtocol
from src.application.ports.food_vision_provider import FoodVisionProviderProtocol
from src.application.ports.image_storage import ImageStorageProtocol
from src.application.ports.password_hasher import PasswordHasherProtocol
from src.application.ports.payment_provider import PaymentProviderProtocol
from src.application.ports.social_identity_verifier import SocialIdentityVerifierProtocol
from src.application.ports.token_service import TokenServiceProtocol
from src.domain.entities.user import User
from src.domain.enums import PaymentProvider, SubscriptionStatus, SubscriptionTier
from src.domain.exceptions import (
    InvalidTokenException,
    PremiumRequiredException,
    RateLimitedException,
)
from src.infrastructure.ai.gemini_chat_provider import GeminiChatProvider
from src.infrastructure.ai.gemini_food_vision_provider import GeminiFoodVisionProvider
from src.infrastructure.config import settings
from src.infrastructure.di.repositories import SubscriptionRepositoryDep, UserRepositoryDep
from src.infrastructure.images.cloudinary_image_storage import CloudinaryImageStorage
from src.infrastructure.payments.payos_provider import PayOsPaymentProvider
from src.infrastructure.rate_limiter import SlidingWindowLimiter
from src.infrastructure.security.jwt_service import JwtTokenService
from src.infrastructure.security.password_hasher import BcryptPasswordHasher
from src.infrastructure.security.social_identity_verifier import JwtSocialIdentityVerifier


def _split_ids(raw: str) -> frozenset[str]:
    return frozenset(part.strip() for part in raw.split(",") if part.strip())


@lru_cache
def _password_hasher() -> BcryptPasswordHasher:
    return BcryptPasswordHasher()


def get_password_hasher() -> PasswordHasherProtocol:
    return _password_hasher()


PasswordHasherDep = Annotated[PasswordHasherProtocol, Depends(get_password_hasher)]


@lru_cache
def _token_service() -> JwtTokenService:
    return JwtTokenService(
        secret=settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
        access_ttl=timedelta(minutes=settings.access_token_expire_minutes),
        refresh_ttl=timedelta(days=settings.refresh_token_expire_days),
        verification_ttl=timedelta(hours=settings.verification_token_expire_hours),
        password_reset_ttl=timedelta(minutes=settings.password_reset_token_expire_minutes),
    )


def get_token_service() -> TokenServiceProtocol:
    return _token_service()


TokenServiceDep = Annotated[TokenServiceProtocol, Depends(get_token_service)]


@lru_cache
def _social_identity_verifier() -> JwtSocialIdentityVerifier:
    return JwtSocialIdentityVerifier(
        google_client_ids=_split_ids(settings.google_oauth_client_ids),
        apple_client_ids=_split_ids(settings.apple_client_ids),
    )


def get_social_identity_verifier() -> SocialIdentityVerifierProtocol:
    return _social_identity_verifier()


SocialIdentityVerifierDep = Annotated[
    SocialIdentityVerifierProtocol, Depends(get_social_identity_verifier)
]


@lru_cache
def _ai_chat_provider() -> GeminiChatProvider:
    return GeminiChatProvider(
        api_key=settings.gemini_api_key,
        model=settings.gemini_model,
        system_prompt=settings.gemini_system_prompt,
    )


def get_ai_chat_provider() -> AiChatProviderProtocol:
    return _ai_chat_provider()


AiChatProviderDep = Annotated[AiChatProviderProtocol, Depends(get_ai_chat_provider)]


@lru_cache
def _food_vision_provider() -> GeminiFoodVisionProvider:
    return GeminiFoodVisionProvider(
        api_key=settings.gemini_api_key,
        model=settings.gemini_model,
        system_prompt=settings.gemini_food_analysis_prompt,
    )


def get_food_vision_provider() -> FoodVisionProviderProtocol:
    return _food_vision_provider()


FoodVisionProviderDep = Annotated[FoodVisionProviderProtocol, Depends(get_food_vision_provider)]


@lru_cache
def _image_storage() -> CloudinaryImageStorage:
    return CloudinaryImageStorage(cloudinary_url=settings.cloudinary_url)


def get_image_storage() -> ImageStorageProtocol:
    return _image_storage()


ImageStorageDep = Annotated[ImageStorageProtocol, Depends(get_image_storage)]


@lru_cache
def _payment_providers() -> dict[PaymentProvider, PaymentProviderProtocol]:
    """Only providers with credentials configured — the rest are simply not offered."""
    providers: dict[PaymentProvider, PaymentProviderProtocol] = {}
    if settings.payos_client_id and settings.payos_api_key and settings.payos_checksum_key:
        from payos import AsyncPayOS

        client = AsyncPayOS(
            client_id=settings.payos_client_id,
            api_key=settings.payos_api_key,
            checksum_key=settings.payos_checksum_key,
        )
        providers[PaymentProvider.PAYOS] = PayOsPaymentProvider(
            client=client, checksum_key=settings.payos_checksum_key
        )
    return providers


def get_payment_providers() -> dict[PaymentProvider, PaymentProviderProtocol]:
    return _payment_providers()


PaymentProvidersDep = Annotated[
    dict[PaymentProvider, PaymentProviderProtocol], Depends(get_payment_providers)
]

# Over plain HTTPBearer so Swagger's Authorize button gets a login form
# (POSTs to tokenUrl) instead of a bare token field. auto_error=False: we
# raise our own exception below rather than FastAPI's default HTTPException.
_oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/token", auto_error=False)


async def _user_from_token(token: str, tokens: TokenServiceProtocol, users) -> User:
    user_id = tokens.read_access_token(token)
    user = await users.get_by_id(user_id)
    if user is None or not user.is_active:
        raise InvalidTokenException("user no longer exists or is inactive")
    return user


async def get_current_user(
    token: Annotated[str | None, Depends(_oauth2_scheme)],
    tokens: TokenServiceDep,
    users: UserRepositoryDep,
) -> User:
    if token is None:
        raise InvalidTokenException("missing bearer token")
    return await _user_from_token(token, tokens, users)


CurrentUserDep = Annotated[User, Depends(get_current_user)]


async def _reconcile_premium(user: User, subscriptions, users) -> bool:
    """Whether ``user`` is entitled to Premium right now — reconciling a lapsed
    subscription first. There is no cron (manual-renewal model), so this is the
    only place expiry is enforced. Used both by the hard gate below and by
    features that only soft-degrade (e.g. dropping a Premium-only field)
    instead of denying the whole request.
    """
    subscription = await subscriptions.get_by_user_id(user.id)
    if user.is_premium and subscription is not None and not subscription.covers(date.today()):
        subscription.status = SubscriptionStatus.EXPIRED
        await subscriptions.save(subscription)
        user.subscription_tier = SubscriptionTier.FREE
        await users.update(user)
        return False
    return user.is_premium


async def get_premium_status(
    user: CurrentUserDep,
    subscriptions: SubscriptionRepositoryDep,
    users: UserRepositoryDep,
) -> bool:
    return await _reconcile_premium(user, subscriptions, users)


PremiumStatusDep = Annotated[bool, Depends(get_premium_status)]


async def get_current_premium_user(user: CurrentUserDep, is_premium: PremiumStatusDep) -> User:
    if not is_premium:
        raise PremiumRequiredException("an active Premium subscription is required")
    return user


CurrentPremiumUserDep = Annotated[User, Depends(get_current_premium_user)]


def _enforce(limiter: SlidingWindowLimiter, key: str) -> None:
    if not limiter.allow(key):
        raise RateLimitedException("too many requests, try again later")


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


# Per-process limiters (see SlidingWindowLimiter's ponytail note). Auth endpoints cost bcrypt CPU,
# send email, and are the brute-force surface; chat and signed-in AI calls are paid Gemini calls
# that the daily trial quota doesn't cover (chat has none; premium AI is unlimited).
_auth_ip_limiter = SlidingWindowLimiter(limit=30, window_seconds=60)
_chat_user_limiter = SlidingWindowLimiter(limit=10, window_seconds=60)
_ai_user_limiter = SlidingWindowLimiter(limit=20, window_seconds=60)


async def limit_auth_by_ip(request: Request) -> None:
    _enforce(_auth_ip_limiter, _client_ip(request))


async def limit_chat_by_user(user: CurrentUserDep) -> None:
    _enforce(_chat_user_limiter, str(user.id))


# Anonymous AI calls per client IP. The device id is client-supplied and spoofable, so this is
# what bounds the paid-AI cost of someone minting fresh ids. Signed-in calls skip it.
# ponytail: per-process, 30/hour/IP; shared NATs share the budget. Tune or move to Redis if needed.
_anon_ip_limiter = SlidingWindowLimiter(limit=30, window_seconds=3600)


async def get_ai_caller(
    request: Request,
    token: Annotated[str | None, Depends(_oauth2_scheme)],
    tokens: TokenServiceDep,
    users: UserRepositoryDep,
    subscriptions: SubscriptionRepositoryDep,
    device_id: Annotated[str | None, Header(alias="X-Device-Id", min_length=1, max_length=64)] = None,
) -> AiCallerDTO:
    """Who is calling an AI endpoint: a signed-in user (bearer, optionally plus a device) or an
    anonymous device. Neither is a 401. Quota keys include both, so a device's used trials
    carry over when its owner signs in."""
    keys = [f"device:{device_id}"] if device_id else []
    if token is not None:
        user = await _user_from_token(token, tokens, users)
        _enforce(_ai_user_limiter, str(user.id))
        keys.append(f"user:{user.id}")
        is_premium = await _reconcile_premium(user, subscriptions, users)
        return AiCallerDTO(tuple(keys), is_premium, signed_in=True)
    if not keys:
        raise InvalidTokenException("missing bearer token or X-Device-Id header")
    _enforce(_anon_ip_limiter, _client_ip(request))
    return AiCallerDTO(tuple(keys), is_premium=False, signed_in=False)


AiCallerDep = Annotated[AiCallerDTO, Depends(get_ai_caller)]
