"""Auth primitives: password hasher, token service, and the current-user guard.

The hasher and token service are process-wide singletons — they only hold config
(bcrypt cost, JWT secret/TTLs) and are otherwise stateless, so there is no reason
to rebuild them per request.
"""

from __future__ import annotations

from datetime import date, timedelta
from functools import lru_cache
from typing import Annotated

from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer

from src.application.ports.ai_chat_provider import AiChatProviderProtocol
from src.application.ports.food_vision_provider import FoodVisionProviderProtocol
from src.application.ports.image_storage import ImageStorageProtocol
from src.application.ports.password_hasher import PasswordHasherProtocol
from src.application.ports.payment_provider import PaymentProviderProtocol
from src.application.ports.social_identity_verifier import SocialIdentityVerifierProtocol
from src.application.ports.token_service import TokenServiceProtocol
from src.domain.entities.user import User
from src.domain.enums import SubscriptionStatus, SubscriptionTier
from src.domain.exceptions import InvalidTokenException, PremiumRequiredException
from src.infrastructure.ai.gemini_chat_provider import GeminiChatProvider
from src.infrastructure.ai.gemini_food_vision_provider import GeminiFoodVisionProvider
from src.infrastructure.config import settings
from src.infrastructure.di.repositories import SubscriptionRepositoryDep, UserRepositoryDep
from src.infrastructure.images.cloudinary_image_storage import CloudinaryImageStorage
from src.infrastructure.payments.payos_provider import PayOsPaymentProvider
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
def _payment_provider() -> PayOsPaymentProvider:
    from payos import AsyncPayOS

    client = AsyncPayOS(
        client_id=settings.payos_client_id,
        api_key=settings.payos_api_key,
        checksum_key=settings.payos_checksum_key,
    )
    return PayOsPaymentProvider(client=client, checksum_key=settings.payos_checksum_key)


def get_payment_provider() -> PaymentProviderProtocol:
    return _payment_provider()


PaymentProviderDep = Annotated[PaymentProviderProtocol, Depends(get_payment_provider)]

# Over plain HTTPBearer so Swagger's Authorize button gets a login form
# (POSTs to tokenUrl) instead of a bare token field. auto_error=False: we
# raise our own exception below rather than FastAPI's default HTTPException.
_oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/token", auto_error=False)


async def get_current_user(
    token: Annotated[str | None, Depends(_oauth2_scheme)],
    tokens: TokenServiceDep,
    users: UserRepositoryDep,
) -> User:
    if token is None:
        raise InvalidTokenException("missing bearer token")
    user_id = tokens.read_access_token(token)
    user = await users.get_by_id(user_id)
    if user is None or not user.is_active:
        raise InvalidTokenException("user no longer exists or is inactive")
    return user


CurrentUserDep = Annotated[User, Depends(get_current_user)]


async def get_current_premium_user(
    user: CurrentUserDep,
    subscriptions: SubscriptionRepositoryDep,
    users: UserRepositoryDep,
) -> User:
    subscription = await subscriptions.get_by_user_id(user.id)
    if user.is_premium and subscription is not None and not subscription.covers(date.today()):
        # Lapsed since the last check-in — there is no cron, so this is the
        # only place expiry is enforced (manual-renewal model).
        subscription.status = SubscriptionStatus.EXPIRED
        await subscriptions.save(subscription)
        user.subscription_tier = SubscriptionTier.FREE
        user = await users.update(user)

    if not user.is_premium:
        raise PremiumRequiredException("an active Premium subscription is required")
    return user


CurrentPremiumUserDep = Annotated[User, Depends(get_current_premium_user)]
