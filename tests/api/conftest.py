"""Shared fixtures for API tests: schema reset, HTTP client, a recording notifier."""

from __future__ import annotations

import pytest_asyncio
from httpx import ASGITransport, AsyncClient

import src.infrastructure.db.models  # noqa: F401 — register every table on Base.metadata
from src.application.dtos.auth import VerifiedIdentity
from src.application.dtos.food_analysis import FoodAnalysisDTO, IngredientSuggestionDTO
from src.application.ports.payment_provider import (
    CheckoutLinkResult,
    ProviderPaymentStatus,
    WebhookPayload,
)
from src.domain.enums import PaymentStatus
from src.domain.exceptions import InvalidTokenException, InvalidWebhookSignatureException
from src.infrastructure.db.base import Base
from src.infrastructure.db.session import engine
from src.infrastructure.di import security
from src.infrastructure.di import (
    get_ai_chat_provider,
    get_email_verification_notifier,
    get_food_vision_provider,
    get_image_storage,
    get_payment_provider,
    get_social_identity_verifier,
)
from src.infrastructure.rate_limiter import SlidingWindowLimiter
from src.main import app

_CREDENTIALS = {"email": "user@example.com", "password": "s3cret-pass", "displayName": "User"}


class RecordingNotifier:
    """Captures tokens instead of sending an email."""

    def __init__(self) -> None:
        self.sent: list[dict[str, str]] = []
        self.password_resets: list[dict[str, str]] = []

    async def send_verification(self, email: str, name: str | None, token: str) -> None:
        self.sent.append({"email": email, "name": name, "token": token})

    async def send_password_reset(self, email: str, name: str | None, token: str) -> None:
        self.password_resets.append({"email": email, "name": name, "token": token})

    @property
    def last_token(self) -> str:
        return self.sent[-1]["token"]

    @property
    def last_reset_token(self) -> str:
        return self.password_resets[-1]["token"]


@pytest_asyncio.fixture(autouse=True)
async def _reset_schema():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture(autouse=True)
def _fresh_rate_limiters():
    limiters = [v for v in vars(security).values() if isinstance(v, SlidingWindowLimiter)]
    for limiter in limiters:
        limiter.hits.clear()
    yield
    for limiter in limiters:
        limiter.hits.clear()


@pytest_asyncio.fixture
def notifier():
    recorder = RecordingNotifier()
    app.dependency_overrides[get_email_verification_notifier] = lambda: recorder
    yield recorder
    app.dependency_overrides.pop(get_email_verification_notifier, None)


class FakeSocialVerifier:
    """Maps a raw token string to a canned identity — no real Google/Apple call."""

    def __init__(self) -> None:
        self._identities: dict[str, VerifiedIdentity] = {}

    def stub(self, token: str, identity: VerifiedIdentity) -> None:
        self._identities[token] = identity

    def verify(self, provider, id_token):
        if id_token not in self._identities:
            raise InvalidTokenException("invalid identity token")
        return self._identities[id_token]


@pytest_asyncio.fixture
def social_verifier():
    fake = FakeSocialVerifier()
    app.dependency_overrides[get_social_identity_verifier] = lambda: fake
    yield fake
    app.dependency_overrides.pop(get_social_identity_verifier, None)


class FakeAiChatProvider:
    """Yields a scripted reply instead of calling a real LLM; records the context it was given."""

    def __init__(self) -> None:
        self.deltas = ["Hello", ", world!"]
        self.last_context: str | None = None

    async def stream_reply(self, history, user_message, context):
        self.last_context = context
        for delta in self.deltas:
            yield delta


@pytest_asyncio.fixture
def ai_chat_provider():
    fake = FakeAiChatProvider()
    app.dependency_overrides[get_ai_chat_provider] = lambda: fake
    yield fake
    app.dependency_overrides.pop(get_ai_chat_provider, None)


class FakeFoodVisionProvider:
    """Returns a scripted analysis instead of calling a real LLM."""

    def __init__(self) -> None:
        self.result = FoodAnalysisDTO(
            meal_name="Pho",
            ingredients=[
                IngredientSuggestionDTO(
                    name="beef",
                    quantity_g=200.0,
                    kcal=300,
                    carbs_g=0.0,
                    protein_g=40.0,
                    fat_g=15.0,
                    fiber_g=None,
                    confidence=0.9,
                )
            ],
            image_url=None,
        )

    async def analyze_image(self, image_bytes, content_type, language):
        return self.result

    async def analyze_text(self, description, language):
        return self.result


@pytest_asyncio.fixture
def food_vision_provider():
    fake = FakeFoodVisionProvider()
    app.dependency_overrides[get_food_vision_provider] = lambda: fake
    yield fake
    app.dependency_overrides.pop(get_food_vision_provider, None)


class FakeImageStorage:
    """Records uploads instead of calling Cloudinary."""

    def __init__(self) -> None:
        self.url = "https://cdn.example/meal.jpg"
        self.uploads: list[tuple[bytes, str]] = []

    async def upload(self, data, content_type):
        self.uploads.append((data, content_type))
        return self.url


@pytest_asyncio.fixture
def image_storage():
    fake = FakeImageStorage()
    app.dependency_overrides[get_image_storage] = lambda: fake
    yield fake
    app.dependency_overrides.pop(get_image_storage, None)


class FakePaymentProvider:
    """Scripted PayOS provider — no real network call."""

    def __init__(self) -> None:
        self.status_by_order_code: dict[int, ProviderPaymentStatus] = {}
        self.cancelled: list[int] = []
        self.next_webhook: WebhookPayload | None = None
        self.webhook_should_fail_signature = False

    async def create_checkout_link(self, order_code, amount, description, cancel_url, return_url):
        return CheckoutLinkResult(
            payment_link_id=f"link-{order_code}",
            checkout_url=f"https://pay.example/{order_code}",
            qr_code=f"qr-{order_code}",
        )

    async def get_payment_status(self, order_code):
        return self.status_by_order_code.get(
            order_code,
            ProviderPaymentStatus(order_code=order_code, status=PaymentStatus.PENDING, succeeded=False),
        )

    async def cancel(self, order_code, reason):
        self.cancelled.append(order_code)

    def verify_webhook(self, raw_body):
        if self.webhook_should_fail_signature:
            raise InvalidWebhookSignatureException("bad signature")
        assert self.next_webhook is not None
        return self.next_webhook


@pytest_asyncio.fixture
def payment_provider():
    fake = FakePaymentProvider()
    app.dependency_overrides[get_payment_provider] = lambda: fake
    yield fake
    app.dependency_overrides.pop(get_payment_provider, None)


@pytest_asyncio.fixture
async def client(
    notifier, social_verifier, ai_chat_provider, food_vision_provider, image_storage, payment_provider
):  # overrides before requests
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest_asyncio.fixture
async def signed_up(client, notifier):
    """A freshly signed-up user: sign-up returns a live session immediately —
    no verification step required to use the app."""
    resp = await client.post("/auth/sign-up", json=_CREDENTIALS)
    assert resp.status_code == 200
    body = resp.json()
    return {**_CREDENTIALS, **body, "verificationToken": notifier.last_token}
