# PayOS Payment Feature Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let a user buy a Premium plan (monthly/annual) via a PayOS checkout link, and have a confirmed payment flip `User.subscription_tier` to `PREMIUM` for the paid period, with a reusable `CurrentPremiumUserDep` gate for future premium endpoints.

**Architecture:** Clean Architecture, inside-out: a new `Payment` domain entity + a `Subscription.renew` factory, application ports/use-cases behind `PaymentProviderProtocol`/`PaymentRepositoryProtocol`/`SubscriptionRepositoryProtocol`, an infrastructure adapter wrapping the official `payos` SDK plus SQLAlchemy repositories, and thin FastAPI controllers. `User.subscription_tier`/`is_premium` (already in the codebase) remains the single premium flag; `Subscription` is the detailed billing record that drives it.

**Tech Stack:** Python 3.11+, FastAPI, async SQLAlchemy 2.0 + asyncpg, Pydantic v2, Alembic, `payos` (official async SDK), pytest/pytest-asyncio/httpx.

**Spec:** `docs/superpowers/specs/2026-09-24-payos-payment-design.md`

## Global Constraints

- Layering: `domain` imports stdlib only; `application` imports stdlib + `domain` only (no FastAPI/SQLAlchemy/Pydantic); `adapters`/`infrastructure` may depend inward. Run `uv run lint-imports` after touching imports — must stay green.
- Money is always `Decimal`, never `float`. VND has no minor unit, so `Numeric(12, 0)`.
- Every new ORM model is registered in `src/infrastructure/db/models/__init__.py` and gets an Alembic migration — `create_all`/Alembic only see registered models.
- Wire format is camelCase via `CamelModel` (`alias_generator=to_camel`); Python stays snake_case.
- Never raise `HTTPException` from application/domain — raise a `DomainException` subclass; `src/adapters/exception_handlers.py` maps it to a status code.
- New use-case providers go in `src/infrastructure/di/use_cases.py`; repository providers in `src/infrastructure/di/repositories.py`; controllers only import from `src.infrastructure.di`.
- CHECK-constraint names passed to `enum_column`/`sa.CheckConstraint` are bare (the naming convention in `src/infrastructure/db/base.py` prefixes `ck_<table>_` itself).
- Tests: `tests/unit/` = in-memory fakes, no DB, one `Fake*` class set per test file (this repo's existing convention — no shared fakes module). `tests/integration/` = real Postgres via `TEST_DATABASE_URL` (default `postgresql+asyncpg://postgres:postgres@localhost:5433/foodfen`), schema dropped/recreated per test. `tests/api/` = `httpx.AsyncClient` against the real app with `app.dependency_overrides` swapping in fakes (see `tests/api/conftest.py`).
- Run tests with `uv run pytest <path> -v`. Integration/api tests need `make docker-up` first.

---

### Task 1: Domain foundations — `PaymentStatus`, new exceptions, `Payment` entity

**Files:**
- Modify: `src/domain/enums.py` (append `PaymentStatus`)
- Modify: `src/domain/exceptions.py` (append 4 exceptions)
- Create: `src/domain/entities/payment.py`
- Test: `tests/unit/test_payment_entity.py`

**Interfaces:**
- Consumes: `src.domain.enums.PlanType` (existing), `src.domain.validation.require_positive` (existing), `src.domain.exceptions.InvalidAttributeException` (existing)
- Produces: `PaymentStatus(StrEnum)` with members `PENDING/PAID/CANCELLED/EXPIRED/FAILED`; `PaymentNotFoundException`, `InvalidPaymentStateException`, `InvalidWebhookSignatureException`, `PremiumRequiredException`; `Payment` dataclass with fields `id: UUID, user_id: int, plan_type: PlanType, amount: Decimal, status: PaymentStatus, order_code: int | None, payment_link_id: str | None, checkout_url: str | None, qr_code: str | None, created_at: datetime, paid_at: datetime | None`, classmethod `Payment.create(user_id, plan_type, amount) -> Payment`, methods `attach_checkout(payment_link_id, checkout_url, qr_code)`, `mark_paid()`, `mark_failed()`, `mark_cancelled()`.

- [ ] **Step 1: Write the failing test**

Create `tests/unit/test_payment_entity.py`:

```python
"""Payment entity unit tests: invariants + state transitions. Pure domain, no I/O."""

from __future__ import annotations

from decimal import Decimal

import pytest

from src.domain.entities.payment import Payment
from src.domain.enums import PaymentStatus, PlanType
from src.domain.exceptions import InvalidAttributeException, InvalidPaymentStateException


def _payment(amount="49000") -> Payment:
    return Payment.create(user_id=1, plan_type=PlanType.MONTHLY, amount=amount)


def test_create_defaults_to_pending_with_no_order_code():
    payment = _payment()
    assert payment.status is PaymentStatus.PENDING
    assert payment.order_code is None
    assert payment.amount == Decimal("49000")


def test_amount_must_be_positive():
    with pytest.raises(InvalidAttributeException):
        _payment(amount="0")


def test_attach_checkout_sets_fields_while_pending():
    payment = _payment()
    payment.attach_checkout("link-1", "https://pay.example/link-1", "qr-data")
    assert payment.payment_link_id == "link-1"
    assert payment.checkout_url == "https://pay.example/link-1"
    assert payment.qr_code == "qr-data"


def test_attach_checkout_rejects_non_pending():
    payment = _payment()
    payment.mark_paid()
    with pytest.raises(InvalidPaymentStateException):
        payment.attach_checkout("link-1", "https://pay.example/link-1", "qr-data")


def test_mark_paid_sets_status_and_paid_at():
    payment = _payment()
    payment.mark_paid()
    assert payment.status is PaymentStatus.PAID
    assert payment.paid_at is not None


def test_mark_paid_is_idempotent():
    payment = _payment()
    payment.mark_paid()
    first_paid_at = payment.paid_at
    payment.mark_paid()
    assert payment.paid_at == first_paid_at


def test_mark_cancelled_rejects_non_pending():
    payment = _payment()
    payment.mark_paid()
    with pytest.raises(InvalidPaymentStateException):
        payment.mark_cancelled()


def test_mark_cancelled_sets_status_while_pending():
    payment = _payment()
    payment.mark_cancelled()
    assert payment.status is PaymentStatus.CANCELLED
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_payment_entity.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.domain.entities.payment'`

- [ ] **Step 3: Add `PaymentStatus` to `src/domain/enums.py`**

Append after `class SubscriptionStatus(StrEnum): ...`:

```python
class PaymentStatus(StrEnum):
    PENDING = "pending"
    PAID = "paid"
    CANCELLED = "cancelled"
    EXPIRED = "expired"
    FAILED = "failed"
```

- [ ] **Step 4: Add the 4 exceptions to `src/domain/exceptions.py`**

Append at the end of the file:

```python
class PaymentNotFoundException(EntityNotFoundException):
    """A requested payment does not exist."""


class InvalidPaymentStateException(InvalidAttributeException):
    """An operation is not valid for a payment's current status."""


class InvalidWebhookSignatureException(AuthenticationException):
    """A webhook payload's signature does not match the expected checksum."""


class PremiumRequiredException(DomainException):
    """The user does not have an active Premium subscription. Maps to HTTP 402."""
```

- [ ] **Step 5: Write `src/domain/entities/payment.py`**

```python
"""Payment entity — one row per PayOS checkout attempt."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from src.domain.enums import PaymentStatus, PlanType
from src.domain.exceptions import InvalidPaymentStateException
from src.domain.validation import require_positive


@dataclass
class Payment:
    """A single PayOS checkout attempt for one plan purchase.

    ``order_code`` is ``None`` until the row is inserted: PayOS requires a
    numeric order id, and the database's identity column is the only way to
    hand one out with no collision risk — the same reason ``User.id`` is
    ``None`` until insert.
    """

    id: UUID
    user_id: int
    plan_type: PlanType
    amount: Decimal
    status: PaymentStatus
    order_code: int | None = None
    payment_link_id: str | None = None
    checkout_url: str | None = None
    qr_code: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    paid_at: datetime | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.amount, Decimal):
            self.amount = Decimal(str(self.amount))
        require_positive(self.amount, "amount")

    @classmethod
    def create(cls, user_id: int, plan_type: PlanType, amount: Decimal | int | str) -> Payment:
        return cls(
            id=uuid4(),
            user_id=user_id,
            plan_type=plan_type,
            amount=Decimal(str(amount)),
            status=PaymentStatus.PENDING,
        )

    def attach_checkout(self, payment_link_id: str, checkout_url: str, qr_code: str) -> None:
        if self.status is not PaymentStatus.PENDING:
            raise InvalidPaymentStateException(
                f"cannot attach checkout info to a payment in status {self.status}"
            )
        self.payment_link_id = payment_link_id
        self.checkout_url = checkout_url
        self.qr_code = qr_code

    def mark_paid(self) -> None:
        """Idempotent: a webhook retry after we've already recorded PAID is a no-op."""
        if self.status is not PaymentStatus.PENDING:
            return
        self.status = PaymentStatus.PAID
        self.paid_at = datetime.now(UTC)

    def mark_failed(self) -> None:
        if self.status is not PaymentStatus.PENDING:
            return
        self.status = PaymentStatus.FAILED

    def mark_cancelled(self) -> None:
        if self.status is not PaymentStatus.PENDING:
            raise InvalidPaymentStateException(
                f"cannot cancel a payment in status {self.status}"
            )
        self.status = PaymentStatus.CANCELLED
```

- [ ] **Step 6: Run test to verify it passes**

Run: `uv run pytest tests/unit/test_payment_entity.py -v`
Expected: PASS (8 tests)

- [ ] **Step 7: Commit**

```bash
git add src/domain/enums.py src/domain/exceptions.py src/domain/entities/payment.py tests/unit/test_payment_entity.py
git commit -m "feat: add Payment entity, PaymentStatus, and payment exceptions"
```

---

### Task 2: `Subscription.renew` factory (renewal date math)

**Files:**
- Modify: `src/domain/entities/subscription.py`
- Test: `tests/unit/test_subscription_renew.py`

**Interfaces:**
- Consumes: `Subscription` (existing, from Task 0/pre-existing code), `PlanType`, `SubscriptionStatus`
- Produces: `Subscription.renew(existing: Subscription | None, user_id: int, plan_type: PlanType, price: Decimal | int | str, today: date) -> Subscription`

- [ ] **Step 1: Write the failing test**

Create `tests/unit/test_subscription_renew.py`:

```python
"""Subscription.renew unit tests: renewal date math. Pure domain, no I/O."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from src.domain.entities.subscription import Subscription
from src.domain.enums import PlanType, SubscriptionStatus


def test_renew_from_none_starts_today_monthly():
    sub = Subscription.renew(
        None, user_id=1, plan_type=PlanType.MONTHLY, price="49000", today=date(2026, 1, 15)
    )
    assert sub.start_date == date(2026, 1, 15)
    assert sub.end_date == date(2026, 2, 15)
    assert sub.status is SubscriptionStatus.ACTIVE


def test_renew_monthly_clamps_end_of_month():
    sub = Subscription.renew(
        None, user_id=1, plan_type=PlanType.MONTHLY, price="49000", today=date(2026, 1, 31)
    )
    assert sub.end_date == date(2026, 2, 28)


def test_renew_annual_clamps_leap_day():
    sub = Subscription.renew(
        None, user_id=1, plan_type=PlanType.ANNUAL, price="499000", today=date(2024, 2, 29)
    )
    assert sub.end_date == date(2025, 2, 28)


def test_renew_before_expiry_stacks_from_existing_end_date():
    existing = Subscription.create(
        user_id=1,
        plan_type=PlanType.MONTHLY,
        start_date=date(2026, 1, 1),
        end_date=date(2026, 2, 1),
        price=Decimal("49000"),
    )
    sub = Subscription.renew(
        existing, user_id=1, plan_type=PlanType.MONTHLY, price="49000", today=date(2026, 1, 20)
    )
    assert sub.start_date == date(2026, 2, 2)
    assert sub.end_date == date(2026, 3, 2)
    assert sub.id == existing.id


def test_renew_after_expiry_starts_today_not_old_end_date():
    existing = Subscription.create(
        user_id=1,
        plan_type=PlanType.MONTHLY,
        start_date=date(2025, 1, 1),
        end_date=date(2025, 2, 1),
        price=Decimal("49000"),
    )
    sub = Subscription.renew(
        existing, user_id=1, plan_type=PlanType.ANNUAL, price="499000", today=date(2026, 1, 15)
    )
    assert sub.start_date == date(2026, 1, 15)
    assert sub.id == existing.id
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_subscription_renew.py -v`
Expected: FAIL — `AttributeError: type object 'Subscription' has no attribute 'renew'`

- [ ] **Step 3: Add `calendar`/`timedelta` imports and the `renew` factory to `src/domain/entities/subscription.py`**

Change the import block at the top from:

```python
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from uuid import UUID, uuid4

from src.domain.enums import PlanType, SubscriptionStatus
from src.domain.validation import require_non_negative, require_not_before
```

to:

```python
import calendar
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

from src.domain.enums import PlanType, SubscriptionStatus
from src.domain.validation import require_non_negative, require_not_before
```

Then append, after the existing `create` classmethod (still inside the `Subscription` class), a new classmethod, plus a module-level helper after the class:

```python
    @classmethod
    def renew(
        cls,
        existing: Subscription | None,
        user_id: int,
        plan_type: PlanType,
        price: Decimal | int | str,
        today: date,
    ) -> Subscription:
        """Extend or start a subscription. An early renewal (before ``existing``
        expires) stacks the new period after the current one instead of
        wasting the days already paid for."""
        if existing is not None and existing.end_date is not None and existing.end_date >= today:
            start = existing.end_date + timedelta(days=1)
        else:
            start = today
        end = _add_period(start, plan_type)
        return cls(
            id=existing.id if existing is not None else uuid4(),
            user_id=user_id,
            plan_type=plan_type,
            status=SubscriptionStatus.ACTIVE,
            start_date=start,
            end_date=end,
            price=Decimal(str(price)),
        )


def _add_period(start: date, plan_type: PlanType) -> date:
    if plan_type is PlanType.ANNUAL:
        try:
            return start.replace(year=start.year + 1)
        except ValueError:
            # Feb 29 in a source year, but the target year isn't a leap year.
            return start.replace(year=start.year + 1, day=28)
    month = start.month % 12 + 1
    year = start.year + (start.month // 12)
    last_day = calendar.monthrange(year, month)[1]
    return start.replace(year=year, month=month, day=min(start.day, last_day))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/test_subscription_renew.py -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
git add src/domain/entities/subscription.py tests/unit/test_subscription_renew.py
git commit -m "feat: add Subscription.renew factory for plan renewal date math"
```

---

### Task 3: Application layer — payment ports/DTOs + `CreateCheckoutUseCase`

**Files:**
- Create: `src/application/ports/payment_provider.py`
- Create: `src/application/ports/payment_repository.py`
- Create: `src/application/dtos/payment.py`
- Create: `src/application/use_cases/create_checkout.py`
- Test: `tests/unit/test_create_checkout_use_case.py`

**Interfaces:**
- Consumes: `Payment`, `PaymentStatus`, `PlanType`, `PaymentNotFoundException` (Task 1)
- Produces: `CheckoutLinkResult(payment_link_id, checkout_url, qr_code)`, `ProviderPaymentStatus(order_code, status, succeeded)`, `WebhookPayload(order_code, succeeded)`, `PaymentProviderProtocol` (methods `create_checkout_link`, `get_payment_status`, `cancel`, `verify_webhook`), `PaymentRepositoryProtocol` (methods `create`, `get_by_order_code`, `update`), `CreateCheckoutInputDTO(user_id, plan_type)`, `CheckoutOutputDTO(order_code, checkout_url, qr_code, amount, plan_type, status)` with `.from_entity(Payment)`, `PaymentOutputDTO(order_code, status, amount, plan_type, paid_at, created_at)` with `.from_entity(Payment)`, `CreateCheckoutUseCase(payments, provider, monthly_price_vnd, annual_price_vnd, return_url, cancel_url)` with `async def execute(input_dto: CreateCheckoutInputDTO) -> CheckoutOutputDTO`.

- [ ] **Step 1: Write the failing test**

Create `tests/unit/test_create_checkout_use_case.py`:

```python
"""CreateCheckoutUseCase unit tests: in-memory repo + scripted provider. No I/O."""

from __future__ import annotations

from decimal import Decimal

import pytest

from src.application.dtos.payment import CreateCheckoutInputDTO
from src.application.ports.payment_provider import CheckoutLinkResult
from src.application.use_cases.create_checkout import CreateCheckoutUseCase
from src.domain.entities.payment import Payment
from src.domain.enums import PaymentStatus, PlanType
from src.domain.exceptions import PaymentNotFoundException


class FakePaymentRepo:
    def __init__(self) -> None:
        self._by_order_code: dict[int, Payment] = {}
        self._next_order_code = 1000

    async def create(self, payment: Payment) -> Payment:
        payment.order_code = self._next_order_code
        self._next_order_code += 1
        self._by_order_code[payment.order_code] = payment
        return payment

    async def get_by_order_code(self, order_code: int) -> Payment | None:
        return self._by_order_code.get(order_code)

    async def update(self, payment: Payment) -> Payment:
        if payment.order_code not in self._by_order_code:
            raise PaymentNotFoundException(str(payment.order_code))
        self._by_order_code[payment.order_code] = payment
        return payment


class FakePaymentProvider:
    def __init__(self) -> None:
        self.created_with: dict | None = None

    async def create_checkout_link(self, order_code, amount, description, cancel_url, return_url):
        self.created_with = {
            "order_code": order_code,
            "amount": amount,
            "description": description,
            "cancel_url": cancel_url,
            "return_url": return_url,
        }
        return CheckoutLinkResult(
            payment_link_id=f"link-{order_code}",
            checkout_url=f"https://pay.example/{order_code}",
            qr_code="qr-data",
        )

    async def get_payment_status(self, order_code):
        raise NotImplementedError

    async def cancel(self, order_code, reason):
        raise NotImplementedError

    def verify_webhook(self, raw_body):
        raise NotImplementedError


@pytest.fixture
def use_case() -> CreateCheckoutUseCase:
    return CreateCheckoutUseCase(
        payments=FakePaymentRepo(),
        provider=FakePaymentProvider(),
        monthly_price_vnd=49_000,
        annual_price_vnd=499_000,
        return_url="https://app.example/return",
        cancel_url="https://app.example/cancel",
    )


async def test_execute_creates_pending_payment_then_attaches_checkout(use_case):
    result = await use_case.execute(CreateCheckoutInputDTO(user_id=1, plan_type=PlanType.MONTHLY))
    assert result.status is PaymentStatus.PENDING
    assert result.amount == Decimal("49000")
    assert result.checkout_url == f"https://pay.example/{result.order_code}"
    assert result.qr_code == "qr-data"


async def test_execute_prices_annual_plan_separately(use_case):
    result = await use_case.execute(CreateCheckoutInputDTO(user_id=1, plan_type=PlanType.ANNUAL))
    assert result.amount == Decimal("499000")


async def test_execute_passes_order_code_and_amount_to_provider(use_case):
    result = await use_case.execute(CreateCheckoutInputDTO(user_id=1, plan_type=PlanType.MONTHLY))
    assert use_case.provider.created_with["order_code"] == result.order_code
    assert use_case.provider.created_with["amount"] == Decimal("49000")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_create_checkout_use_case.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.application.ports.payment_provider'`

- [ ] **Step 3: Write `src/application/ports/payment_provider.py`**

```python
"""Port for the payment provider (PayOS). Structural typing via Protocol."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol

from src.domain.enums import PaymentStatus


@dataclass(frozen=True)
class CheckoutLinkResult:
    payment_link_id: str
    checkout_url: str
    qr_code: str


@dataclass(frozen=True)
class ProviderPaymentStatus:
    order_code: int
    status: PaymentStatus
    succeeded: bool


@dataclass(frozen=True)
class WebhookPayload:
    order_code: int
    succeeded: bool


class PaymentProviderProtocol(Protocol):
    async def create_checkout_link(
        self,
        order_code: int,
        amount: Decimal,
        description: str,
        cancel_url: str,
        return_url: str,
    ) -> CheckoutLinkResult: ...

    async def get_payment_status(self, order_code: int) -> ProviderPaymentStatus: ...

    async def cancel(self, order_code: int, reason: str | None) -> None: ...

    def verify_webhook(self, raw_body: bytes) -> WebhookPayload:
        """Raise ``InvalidWebhookSignatureException`` if the signature doesn't match."""
        ...
```

- [ ] **Step 4: Write `src/application/ports/payment_repository.py`**

```python
"""Persistence port for payments. Structural typing via Protocol."""

from __future__ import annotations

from typing import Protocol

from src.domain.entities.payment import Payment


class PaymentRepositoryProtocol(Protocol):
    async def create(self, payment: Payment) -> Payment:
        """Insert. Assigns ``order_code`` (a DB identity column) and returns it set."""
        ...

    async def get_by_order_code(self, order_code: int) -> Payment | None: ...

    async def update(self, payment: Payment) -> Payment:
        """Raise ``PaymentNotFoundException`` if the row is gone."""
        ...
```

- [ ] **Step 5: Write `src/application/dtos/payment.py`**

```python
"""Payment DTOs — frozen dataclasses, never a Pydantic model or ORM row."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from src.domain.entities.payment import Payment
from src.domain.enums import PaymentStatus, PlanType


@dataclass(frozen=True)
class CreateCheckoutInputDTO:
    user_id: int
    plan_type: PlanType


@dataclass(frozen=True)
class CheckoutOutputDTO:
    order_code: int
    checkout_url: str
    qr_code: str
    amount: Decimal
    plan_type: PlanType
    status: PaymentStatus

    @classmethod
    def from_entity(cls, payment: Payment) -> CheckoutOutputDTO:
        assert payment.order_code is not None
        assert payment.checkout_url is not None
        assert payment.qr_code is not None
        return cls(
            order_code=payment.order_code,
            checkout_url=payment.checkout_url,
            qr_code=payment.qr_code,
            amount=payment.amount,
            plan_type=payment.plan_type,
            status=payment.status,
        )


@dataclass(frozen=True)
class PaymentOutputDTO:
    order_code: int
    status: PaymentStatus
    amount: Decimal
    plan_type: PlanType
    paid_at: datetime | None
    created_at: datetime

    @classmethod
    def from_entity(cls, payment: Payment) -> PaymentOutputDTO:
        assert payment.order_code is not None
        return cls(
            order_code=payment.order_code,
            status=payment.status,
            amount=payment.amount,
            plan_type=payment.plan_type,
            paid_at=payment.paid_at,
            created_at=payment.created_at,
        )
```

- [ ] **Step 6: Write `src/application/use_cases/create_checkout.py`**

```python
"""Use case: start a PayOS checkout for a plan purchase."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from src.application.dtos.payment import CheckoutOutputDTO, CreateCheckoutInputDTO
from src.application.ports.payment_provider import PaymentProviderProtocol
from src.application.ports.payment_repository import PaymentRepositoryProtocol
from src.domain.entities.payment import Payment
from src.domain.enums import PlanType


@dataclass
class CreateCheckoutUseCase:
    payments: PaymentRepositoryProtocol
    provider: PaymentProviderProtocol
    monthly_price_vnd: int
    annual_price_vnd: int
    return_url: str
    cancel_url: str

    def _price_for(self, plan_type: PlanType) -> Decimal:
        vnd = self.monthly_price_vnd if plan_type is PlanType.MONTHLY else self.annual_price_vnd
        return Decimal(vnd)

    async def execute(self, input_dto: CreateCheckoutInputDTO) -> CheckoutOutputDTO:
        amount = self._price_for(input_dto.plan_type)
        payment = Payment.create(input_dto.user_id, input_dto.plan_type, amount)
        payment = await self.payments.create(payment)
        assert payment.order_code is not None  # DB identity column, assigned on insert

        link = await self.provider.create_checkout_link(
            order_code=payment.order_code,
            amount=amount,
            description=f"FoodFen {input_dto.plan_type.value} premium",
            cancel_url=self.cancel_url,
            return_url=self.return_url,
        )
        payment.attach_checkout(link.payment_link_id, link.checkout_url, link.qr_code)
        payment = await self.payments.update(payment)
        return CheckoutOutputDTO.from_entity(payment)
```

- [ ] **Step 7: Run test to verify it passes**

Run: `uv run pytest tests/unit/test_create_checkout_use_case.py -v`
Expected: PASS (3 tests)

- [ ] **Step 8: Commit**

```bash
git add src/application/ports/payment_provider.py src/application/ports/payment_repository.py src/application/dtos/payment.py src/application/use_cases/create_checkout.py tests/unit/test_create_checkout_use_case.py
git commit -m "feat: add payment ports/DTOs and CreateCheckoutUseCase"
```

---

### Task 4: Subscription port/DTO + `apply_payment_result` + `HandlePaymentWebhookUseCase` + `GetMySubscriptionUseCase`

**Files:**
- Create: `src/application/ports/subscription_repository.py`
- Create: `src/application/dtos/subscription.py`
- Create: `src/application/use_cases/apply_payment_result.py`
- Create: `src/application/use_cases/handle_payment_webhook.py`
- Create: `src/application/use_cases/get_my_subscription.py`
- Test: `tests/unit/test_handle_payment_webhook_use_case.py`
- Test: `tests/unit/test_get_my_subscription_use_case.py`

**Interfaces:**
- Consumes: `Payment`, `PaymentStatus` (Task 1); `Subscription`, `Subscription.renew` (Task 2); `CheckoutLinkResult`/`WebhookPayload`/`PaymentProviderProtocol`/`PaymentRepositoryProtocol` (Task 3); `src.application.ports.user_repository.UserRepositoryProtocol` (existing); `src.domain.enums.SubscriptionTier` (existing)
- Produces: `SubscriptionRepositoryProtocol` (methods `get_by_user_id`, `save`), `SubscriptionOutputDTO(plan_type, status, start_date, end_date)` with `.from_entity(Subscription)`, `async def apply_payment_result(payment, succeeded, payments, subscriptions, users) -> Payment`, `HandlePaymentWebhookUseCase(payments, provider, subscriptions, users)` with `async def execute(raw_body: bytes) -> None`, `GetMySubscriptionUseCase(subscriptions)` with `async def execute(user_id: int) -> SubscriptionOutputDTO | None`.

- [ ] **Step 1: Write the failing tests**

Create `tests/unit/test_handle_payment_webhook_use_case.py`:

```python
"""HandlePaymentWebhookUseCase unit tests. No I/O — in-memory repos, scripted provider."""

from __future__ import annotations

import pytest

from src.application.ports.payment_provider import WebhookPayload
from src.application.use_cases.handle_payment_webhook import HandlePaymentWebhookUseCase
from src.domain.entities.payment import Payment
from src.domain.entities.subscription import Subscription
from src.domain.entities.user import User
from src.domain.enums import PlanType, SubscriptionTier
from src.domain.exceptions import InvalidWebhookSignatureException, PaymentNotFoundException


class FakePaymentRepo:
    def __init__(self) -> None:
        self._by_order_code: dict[int, Payment] = {}

    def seed(self, payment: Payment, order_code: int) -> Payment:
        payment.order_code = order_code
        self._by_order_code[order_code] = payment
        return payment

    async def create(self, payment):
        raise NotImplementedError

    async def get_by_order_code(self, order_code):
        return self._by_order_code.get(order_code)

    async def update(self, payment):
        self._by_order_code[payment.order_code] = payment
        return payment


class FakeSubscriptionRepo:
    def __init__(self) -> None:
        self._by_user_id: dict[int, Subscription] = {}

    async def get_by_user_id(self, user_id):
        return self._by_user_id.get(user_id)

    async def save(self, subscription):
        self._by_user_id[subscription.user_id] = subscription
        return subscription


class FakeUserRepo:
    def __init__(self, user: User) -> None:
        self._user = user

    async def get_by_id(self, user_id):
        return self._user if user_id == self._user.id else None

    async def get_by_email(self, email):
        raise NotImplementedError

    async def create(self, user):
        raise NotImplementedError

    async def update(self, user):
        self._user = user
        return user


class FakeProvider:
    def __init__(self, payload: WebhookPayload | None = None, raise_invalid: bool = False) -> None:
        self._payload = payload
        self._raise_invalid = raise_invalid

    async def create_checkout_link(self, *a, **kw):
        raise NotImplementedError

    async def get_payment_status(self, order_code):
        raise NotImplementedError

    async def cancel(self, order_code, reason):
        raise NotImplementedError

    def verify_webhook(self, raw_body):
        if self._raise_invalid:
            raise InvalidWebhookSignatureException("bad signature")
        assert self._payload is not None
        return self._payload


def _user() -> User:
    user = User.create(email="a@example.com")
    user.id = 1
    return user


async def test_successful_webhook_marks_paid_creates_subscription_and_upgrades_user():
    user = _user()
    payments = FakePaymentRepo()
    payment = payments.seed(
        Payment.create(user_id=1, plan_type=PlanType.MONTHLY, amount="49000"), order_code=42
    )
    subscriptions = FakeSubscriptionRepo()
    users = FakeUserRepo(user)
    provider = FakeProvider(WebhookPayload(order_code=42, succeeded=True))
    use_case = HandlePaymentWebhookUseCase(
        payments=payments, provider=provider, subscriptions=subscriptions, users=users
    )

    await use_case.execute(b"raw-body")

    assert payment.status.value == "paid"
    subscription = await subscriptions.get_by_user_id(1)
    assert subscription is not None and subscription.status.value == "active"
    assert users._user.subscription_tier is SubscriptionTier.PREMIUM


async def test_failed_webhook_marks_failed_without_touching_subscription():
    payments = FakePaymentRepo()
    payment = payments.seed(
        Payment.create(user_id=1, plan_type=PlanType.MONTHLY, amount="49000"), order_code=42
    )
    subscriptions = FakeSubscriptionRepo()
    provider = FakeProvider(WebhookPayload(order_code=42, succeeded=False))
    use_case = HandlePaymentWebhookUseCase(
        payments=payments, provider=provider, subscriptions=subscriptions, users=FakeUserRepo(_user())
    )

    await use_case.execute(b"raw-body")

    assert payment.status.value == "failed"
    assert await subscriptions.get_by_user_id(1) is None


async def test_webhook_replay_is_idempotent():
    payments = FakePaymentRepo()
    payment = payments.seed(
        Payment.create(user_id=1, plan_type=PlanType.MONTHLY, amount="49000"), order_code=42
    )
    provider = FakeProvider(WebhookPayload(order_code=42, succeeded=True))
    use_case = HandlePaymentWebhookUseCase(
        payments=payments,
        provider=provider,
        subscriptions=FakeSubscriptionRepo(),
        users=FakeUserRepo(_user()),
    )

    await use_case.execute(b"raw-body")
    first_paid_at = payment.paid_at
    await use_case.execute(b"raw-body")  # replay
    assert payment.paid_at == first_paid_at


async def test_invalid_signature_raises():
    provider = FakeProvider(raise_invalid=True)
    use_case = HandlePaymentWebhookUseCase(
        payments=FakePaymentRepo(),
        provider=provider,
        subscriptions=FakeSubscriptionRepo(),
        users=FakeUserRepo(_user()),
    )

    with pytest.raises(InvalidWebhookSignatureException):
        await use_case.execute(b"raw-body")


async def test_unknown_order_code_raises_not_found():
    provider = FakeProvider(WebhookPayload(order_code=999, succeeded=True))
    use_case = HandlePaymentWebhookUseCase(
        payments=FakePaymentRepo(),
        provider=provider,
        subscriptions=FakeSubscriptionRepo(),
        users=FakeUserRepo(_user()),
    )

    with pytest.raises(PaymentNotFoundException):
        await use_case.execute(b"raw-body")
```

Create `tests/unit/test_get_my_subscription_use_case.py`:

```python
"""GetMySubscriptionUseCase unit tests. No I/O."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from src.application.use_cases.get_my_subscription import GetMySubscriptionUseCase
from src.domain.entities.subscription import Subscription
from src.domain.enums import PlanType


class FakeSubscriptionRepo:
    def __init__(self, subscription: Subscription | None = None) -> None:
        self._subscription = subscription

    async def get_by_user_id(self, user_id):
        return self._subscription

    async def save(self, subscription):
        raise NotImplementedError


async def test_returns_none_when_no_subscription():
    use_case = GetMySubscriptionUseCase(subscriptions=FakeSubscriptionRepo(None))
    assert await use_case.execute(1) is None


async def test_returns_dto_when_subscription_exists():
    sub = Subscription.create(
        user_id=1,
        plan_type=PlanType.MONTHLY,
        start_date=date(2026, 1, 1),
        end_date=date(2026, 2, 1),
        price=Decimal("49000"),
    )
    use_case = GetMySubscriptionUseCase(subscriptions=FakeSubscriptionRepo(sub))
    result = await use_case.execute(1)
    assert result is not None
    assert result.plan_type is PlanType.MONTHLY
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/test_handle_payment_webhook_use_case.py tests/unit/test_get_my_subscription_use_case.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.application.ports.subscription_repository'`

- [ ] **Step 3: Write `src/application/ports/subscription_repository.py`**

```python
"""Persistence port for subscriptions. Structural typing via Protocol."""

from __future__ import annotations

from typing import Protocol

from src.domain.entities.subscription import Subscription


class SubscriptionRepositoryProtocol(Protocol):
    async def get_by_user_id(self, user_id: int) -> Subscription | None: ...

    async def save(self, subscription: Subscription) -> Subscription:
        """Upsert keyed on ``user_id`` — at most one row per user."""
        ...
```

- [ ] **Step 4: Write `src/application/dtos/subscription.py`**

```python
"""Subscription DTO — frozen dataclass, never a Pydantic model or ORM row."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from src.domain.entities.subscription import Subscription
from src.domain.enums import PlanType, SubscriptionStatus


@dataclass(frozen=True)
class SubscriptionOutputDTO:
    plan_type: PlanType
    status: SubscriptionStatus
    start_date: date
    end_date: date | None

    @classmethod
    def from_entity(cls, subscription: Subscription) -> SubscriptionOutputDTO:
        return cls(
            plan_type=subscription.plan_type,
            status=subscription.status,
            start_date=subscription.start_date,
            end_date=subscription.end_date,
        )
```

- [ ] **Step 5: Write `src/application/use_cases/apply_payment_result.py`**

```python
"""Shared helper: apply a payment provider's outcome to Payment/Subscription/User.

Used by both the webhook handler and the status-reconciliation fallback (the
same role as ``token_pair.py::issue_session`` for the auth slice) so the
"success -> extend premium" branch exists exactly once.
"""

from __future__ import annotations

from datetime import date

from src.application.ports.payment_repository import PaymentRepositoryProtocol
from src.application.ports.subscription_repository import SubscriptionRepositoryProtocol
from src.application.ports.user_repository import UserRepositoryProtocol
from src.domain.entities.payment import Payment
from src.domain.entities.subscription import Subscription
from src.domain.enums import PaymentStatus, SubscriptionTier


async def apply_payment_result(
    payment: Payment,
    succeeded: bool,
    payments: PaymentRepositoryProtocol,
    subscriptions: SubscriptionRepositoryProtocol,
    users: UserRepositoryProtocol,
) -> Payment:
    if payment.status is not PaymentStatus.PENDING:
        return payment  # already processed — webhook retry or double reconciliation

    if succeeded:
        payment.mark_paid()
        existing = await subscriptions.get_by_user_id(payment.user_id)
        renewed = Subscription.renew(
            existing, payment.user_id, payment.plan_type, payment.amount, date.today()
        )
        await subscriptions.save(renewed)

        user = await users.get_by_id(payment.user_id)
        if user is not None:
            user.subscription_tier = SubscriptionTier.PREMIUM
            await users.update(user)
    else:
        payment.mark_failed()

    return await payments.update(payment)
```

- [ ] **Step 6: Write `src/application/use_cases/handle_payment_webhook.py`**

```python
"""Use case: apply an incoming PayOS webhook (IPN) call."""

from __future__ import annotations

from dataclasses import dataclass

from src.application.ports.payment_provider import PaymentProviderProtocol
from src.application.ports.payment_repository import PaymentRepositoryProtocol
from src.application.ports.subscription_repository import SubscriptionRepositoryProtocol
from src.application.ports.user_repository import UserRepositoryProtocol
from src.application.use_cases.apply_payment_result import apply_payment_result
from src.domain.exceptions import PaymentNotFoundException


@dataclass
class HandlePaymentWebhookUseCase:
    payments: PaymentRepositoryProtocol
    provider: PaymentProviderProtocol
    subscriptions: SubscriptionRepositoryProtocol
    users: UserRepositoryProtocol

    async def execute(self, raw_body: bytes) -> None:
        webhook = self.provider.verify_webhook(raw_body)  # raises InvalidWebhookSignatureException
        payment = await self.payments.get_by_order_code(webhook.order_code)
        if payment is None:
            raise PaymentNotFoundException(f"no payment for order_code {webhook.order_code}")
        await apply_payment_result(
            payment, webhook.succeeded, self.payments, self.subscriptions, self.users
        )
```

- [ ] **Step 7: Write `src/application/use_cases/get_my_subscription.py`**

```python
"""Use case: read the current user's subscription, if any."""

from __future__ import annotations

from dataclasses import dataclass

from src.application.dtos.subscription import SubscriptionOutputDTO
from src.application.ports.subscription_repository import SubscriptionRepositoryProtocol


@dataclass
class GetMySubscriptionUseCase:
    subscriptions: SubscriptionRepositoryProtocol

    async def execute(self, user_id: int) -> SubscriptionOutputDTO | None:
        subscription = await self.subscriptions.get_by_user_id(user_id)
        return SubscriptionOutputDTO.from_entity(subscription) if subscription is not None else None
```

- [ ] **Step 8: Run tests to verify they pass**

Run: `uv run pytest tests/unit/test_handle_payment_webhook_use_case.py tests/unit/test_get_my_subscription_use_case.py -v`
Expected: PASS (7 tests)

- [ ] **Step 9: Commit**

```bash
git add src/application/ports/subscription_repository.py src/application/dtos/subscription.py src/application/use_cases/apply_payment_result.py src/application/use_cases/handle_payment_webhook.py src/application/use_cases/get_my_subscription.py tests/unit/test_handle_payment_webhook_use_case.py tests/unit/test_get_my_subscription_use_case.py
git commit -m "feat: add webhook handling, shared payment-result helper, and subscription read use case"
```

---

### Task 5: `GetPaymentStatusUseCase` + `CancelPaymentUseCase`

**Files:**
- Create: `src/application/use_cases/get_payment_status.py`
- Create: `src/application/use_cases/cancel_payment.py`
- Test: `tests/unit/test_get_payment_status_use_case.py`
- Test: `tests/unit/test_cancel_payment_use_case.py`

**Interfaces:**
- Consumes: everything from Tasks 1, 3, 4 (`Payment`, `PaymentOutputDTO`, `PaymentProviderProtocol`, `PaymentRepositoryProtocol`, `SubscriptionRepositoryProtocol`, `UserRepositoryProtocol`, `apply_payment_result`)
- Produces: `GetPaymentStatusUseCase(payments, provider, subscriptions, users)` with `async def execute(user_id, order_code) -> PaymentOutputDTO`; `CancelPaymentUseCase(payments, provider)` with `async def execute(user_id, order_code, reason) -> PaymentOutputDTO`

- [ ] **Step 1: Write the failing tests**

Create `tests/unit/test_get_payment_status_use_case.py`:

```python
"""GetPaymentStatusUseCase unit tests. No I/O."""

from __future__ import annotations

import pytest

from src.application.ports.payment_provider import ProviderPaymentStatus
from src.application.use_cases.get_payment_status import GetPaymentStatusUseCase
from src.domain.entities.payment import Payment
from src.domain.entities.subscription import Subscription
from src.domain.entities.user import User
from src.domain.enums import PaymentStatus, PlanType, SubscriptionTier
from src.domain.exceptions import PaymentNotFoundException


class FakePaymentRepo:
    def __init__(self) -> None:
        self._by_order_code: dict[int, Payment] = {}

    def seed(self, payment: Payment, order_code: int) -> Payment:
        payment.order_code = order_code
        self._by_order_code[order_code] = payment
        return payment

    async def create(self, payment):
        raise NotImplementedError

    async def get_by_order_code(self, order_code):
        return self._by_order_code.get(order_code)

    async def update(self, payment):
        self._by_order_code[payment.order_code] = payment
        return payment


class FakeSubscriptionRepo:
    def __init__(self) -> None:
        self._by_user_id: dict[int, Subscription] = {}

    async def get_by_user_id(self, user_id):
        return self._by_user_id.get(user_id)

    async def save(self, subscription):
        self._by_user_id[subscription.user_id] = subscription
        return subscription


class FakeUserRepo:
    def __init__(self, user: User) -> None:
        self._user = user

    async def get_by_id(self, user_id):
        return self._user if user_id == self._user.id else None

    async def get_by_email(self, email):
        raise NotImplementedError

    async def create(self, user):
        raise NotImplementedError

    async def update(self, user):
        self._user = user
        return user


class FakeProvider:
    def __init__(self, provider_status: ProviderPaymentStatus) -> None:
        self._status = provider_status

    async def create_checkout_link(self, *a, **kw):
        raise NotImplementedError

    async def get_payment_status(self, order_code):
        return self._status

    async def cancel(self, order_code, reason):
        raise NotImplementedError

    def verify_webhook(self, raw_body):
        raise NotImplementedError


def _user() -> User:
    user = User.create(email="a@example.com")
    user.id = 1
    return user


async def test_returns_local_status_without_reconciling_when_not_pending():
    payments = FakePaymentRepo()
    payment = payments.seed(
        Payment.create(user_id=1, plan_type=PlanType.MONTHLY, amount="49000"), order_code=1
    )
    payment.mark_paid()
    provider = FakeProvider(ProviderPaymentStatus(order_code=1, status=PaymentStatus.PAID, succeeded=True))
    use_case = GetPaymentStatusUseCase(
        payments=payments, provider=provider, subscriptions=FakeSubscriptionRepo(), users=FakeUserRepo(_user())
    )
    result = await use_case.execute(user_id=1, order_code=1)
    assert result.status is PaymentStatus.PAID


async def test_reconciles_pending_payment_when_provider_reports_paid():
    user = _user()
    payments = FakePaymentRepo()
    payments.seed(Payment.create(user_id=1, plan_type=PlanType.MONTHLY, amount="49000"), order_code=1)
    provider = FakeProvider(ProviderPaymentStatus(order_code=1, status=PaymentStatus.PAID, succeeded=True))
    users = FakeUserRepo(user)
    use_case = GetPaymentStatusUseCase(
        payments=payments, provider=provider, subscriptions=FakeSubscriptionRepo(), users=users
    )
    result = await use_case.execute(user_id=1, order_code=1)
    assert result.status is PaymentStatus.PAID
    assert users._user.subscription_tier is SubscriptionTier.PREMIUM


async def test_raises_not_found_for_another_users_payment():
    payments = FakePaymentRepo()
    payments.seed(Payment.create(user_id=2, plan_type=PlanType.MONTHLY, amount="49000"), order_code=1)
    provider = FakeProvider(ProviderPaymentStatus(order_code=1, status=PaymentStatus.PENDING, succeeded=False))
    use_case = GetPaymentStatusUseCase(
        payments=payments, provider=provider, subscriptions=FakeSubscriptionRepo(), users=FakeUserRepo(_user())
    )
    with pytest.raises(PaymentNotFoundException):
        await use_case.execute(user_id=1, order_code=1)
```

Create `tests/unit/test_cancel_payment_use_case.py`:

```python
"""CancelPaymentUseCase unit tests. No I/O."""

from __future__ import annotations

import pytest

from src.application.use_cases.cancel_payment import CancelPaymentUseCase
from src.domain.entities.payment import Payment
from src.domain.enums import PaymentStatus, PlanType
from src.domain.exceptions import InvalidPaymentStateException, PaymentNotFoundException


class FakePaymentRepo:
    def __init__(self) -> None:
        self._by_order_code: dict[int, Payment] = {}

    def seed(self, payment: Payment, order_code: int) -> Payment:
        payment.order_code = order_code
        self._by_order_code[order_code] = payment
        return payment

    async def create(self, payment):
        raise NotImplementedError

    async def get_by_order_code(self, order_code):
        return self._by_order_code.get(order_code)

    async def update(self, payment):
        self._by_order_code[payment.order_code] = payment
        return payment


class FakeProvider:
    def __init__(self) -> None:
        self.cancelled_with: tuple[int, str | None] | None = None

    async def create_checkout_link(self, *a, **kw):
        raise NotImplementedError

    async def get_payment_status(self, order_code):
        raise NotImplementedError

    async def cancel(self, order_code, reason):
        self.cancelled_with = (order_code, reason)

    def verify_webhook(self, raw_body):
        raise NotImplementedError


async def test_cancels_a_pending_payment():
    payments = FakePaymentRepo()
    payments.seed(Payment.create(user_id=1, plan_type=PlanType.MONTHLY, amount="49000"), order_code=1)
    provider = FakeProvider()
    use_case = CancelPaymentUseCase(payments=payments, provider=provider)

    result = await use_case.execute(user_id=1, order_code=1, reason="changed my mind")

    assert result.status is PaymentStatus.CANCELLED
    assert provider.cancelled_with == (1, "changed my mind")


async def test_rejects_cancelling_an_already_paid_payment():
    payments = FakePaymentRepo()
    payment = payments.seed(
        Payment.create(user_id=1, plan_type=PlanType.MONTHLY, amount="49000"), order_code=1
    )
    payment.mark_paid()
    use_case = CancelPaymentUseCase(payments=payments, provider=FakeProvider())

    with pytest.raises(InvalidPaymentStateException):
        await use_case.execute(user_id=1, order_code=1, reason=None)


async def test_raises_not_found_for_another_users_payment():
    payments = FakePaymentRepo()
    payments.seed(Payment.create(user_id=2, plan_type=PlanType.MONTHLY, amount="49000"), order_code=1)
    use_case = CancelPaymentUseCase(payments=payments, provider=FakeProvider())

    with pytest.raises(PaymentNotFoundException):
        await use_case.execute(user_id=1, order_code=1, reason=None)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/test_get_payment_status_use_case.py tests/unit/test_cancel_payment_use_case.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.application.use_cases.get_payment_status'`

- [ ] **Step 3: Write `src/application/use_cases/get_payment_status.py`**

```python
"""Use case: read a payment's status, reconciling with the provider if still pending.

The reconciliation step is the fallback for a lost or delayed webhook.
"""

from __future__ import annotations

from dataclasses import dataclass

from src.application.dtos.payment import PaymentOutputDTO
from src.application.ports.payment_provider import PaymentProviderProtocol
from src.application.ports.payment_repository import PaymentRepositoryProtocol
from src.application.ports.subscription_repository import SubscriptionRepositoryProtocol
from src.application.ports.user_repository import UserRepositoryProtocol
from src.application.use_cases.apply_payment_result import apply_payment_result
from src.domain.enums import PaymentStatus
from src.domain.exceptions import PaymentNotFoundException


@dataclass
class GetPaymentStatusUseCase:
    payments: PaymentRepositoryProtocol
    provider: PaymentProviderProtocol
    subscriptions: SubscriptionRepositoryProtocol
    users: UserRepositoryProtocol

    async def execute(self, user_id: int, order_code: int) -> PaymentOutputDTO:
        payment = await self.payments.get_by_order_code(order_code)
        if payment is None or payment.user_id != user_id:
            raise PaymentNotFoundException(f"no payment for order_code {order_code}")

        if payment.status is PaymentStatus.PENDING:
            provider_status = await self.provider.get_payment_status(order_code)
            if provider_status.status is not PaymentStatus.PENDING:
                payment = await apply_payment_result(
                    payment, provider_status.succeeded, self.payments, self.subscriptions, self.users
                )

        return PaymentOutputDTO.from_entity(payment)
```

- [ ] **Step 4: Write `src/application/use_cases/cancel_payment.py`**

```python
"""Use case: cancel a pending checkout."""

from __future__ import annotations

from dataclasses import dataclass

from src.application.dtos.payment import PaymentOutputDTO
from src.application.ports.payment_provider import PaymentProviderProtocol
from src.application.ports.payment_repository import PaymentRepositoryProtocol
from src.domain.enums import PaymentStatus
from src.domain.exceptions import InvalidPaymentStateException, PaymentNotFoundException


@dataclass
class CancelPaymentUseCase:
    payments: PaymentRepositoryProtocol
    provider: PaymentProviderProtocol

    async def execute(self, user_id: int, order_code: int, reason: str | None) -> PaymentOutputDTO:
        payment = await self.payments.get_by_order_code(order_code)
        if payment is None or payment.user_id != user_id:
            raise PaymentNotFoundException(f"no payment for order_code {order_code}")
        if payment.status is not PaymentStatus.PENDING:
            raise InvalidPaymentStateException(f"cannot cancel a payment in status {payment.status}")

        await self.provider.cancel(order_code, reason)
        payment.mark_cancelled()
        payment = await self.payments.update(payment)
        return PaymentOutputDTO.from_entity(payment)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/unit/test_get_payment_status_use_case.py tests/unit/test_cancel_payment_use_case.py -v`
Expected: PASS (6 tests)

- [ ] **Step 6: Commit**

```bash
git add src/application/use_cases/get_payment_status.py src/application/use_cases/cancel_payment.py tests/unit/test_get_payment_status_use_case.py tests/unit/test_cancel_payment_use_case.py
git commit -m "feat: add payment status reconciliation and cancellation use cases"
```

---

### Task 6: `PaymentORM` model + migration `0009`

**Files:**
- Create: `src/infrastructure/db/models/payment_model.py`
- Modify: `src/infrastructure/db/models/__init__.py`
- Create: `alembic/versions/0009_payments_table.py`

**Interfaces:**
- Consumes: `Payment` (Task 1), `PaymentStatus`, `PlanType`, `UUIDPrimaryKey`/`UserOwned` mixins (existing), `enum_column` (existing)
- Produces: `PaymentORM` (table `payments`) with `.to_domain() -> Payment` and `PaymentORM.from_domain(payment: Payment) -> PaymentORM`

- [ ] **Step 1: Write `src/infrastructure/db/models/payment_model.py`**

```python
"""ORM model for payments — one row per PayOS checkout attempt."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import BigInteger, DateTime, Identity, Numeric, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from src.domain.entities.payment import Payment
from src.domain.enums import PaymentStatus, PlanType
from src.infrastructure.db.base import Base
from src.infrastructure.db.mixins import UUIDPrimaryKey, UserOwned
from src.infrastructure.db.types import enum_column


class PaymentORM(UUIDPrimaryKey, UserOwned, Base):
    __tablename__ = "payments"
    __table_args__ = (UniqueConstraint("order_code", name="uq_payments_order_code"),)

    # DB-native identity column: PayOS needs a numeric order id, and this is
    # the only way to hand one out with no collision risk (not the PK — every
    # other table here keeps a UUID PK).
    order_code: Mapped[int] = mapped_column(BigInteger, Identity(), nullable=False)
    plan_type: Mapped[PlanType] = mapped_column(enum_column(PlanType, "plan_type"), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 0), nullable=False)  # VND has no minor unit
    status: Mapped[PaymentStatus] = mapped_column(
        enum_column(PaymentStatus, "payment_status"), nullable=False
    )
    payment_link_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    checkout_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    qr_code: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    def to_domain(self) -> Payment:
        return Payment(
            id=self.id,
            user_id=self.user_id,
            order_code=self.order_code,
            plan_type=self.plan_type,
            amount=self.amount,
            status=self.status,
            payment_link_id=self.payment_link_id,
            checkout_url=self.checkout_url,
            qr_code=self.qr_code,
            created_at=self.created_at,
            paid_at=self.paid_at,
        )

    @staticmethod
    def from_domain(payment: Payment) -> PaymentORM:
        row = PaymentORM(
            id=payment.id,
            user_id=payment.user_id,
            plan_type=payment.plan_type,
            amount=payment.amount,
            status=payment.status,
            payment_link_id=payment.payment_link_id,
            checkout_url=payment.checkout_url,
            qr_code=payment.qr_code,
            created_at=payment.created_at,
            paid_at=payment.paid_at,
        )
        # Identity column: only set it when the entity already has one (an
        # update), never on insert — leave it unset so Postgres assigns it.
        if payment.order_code is not None:
            row.order_code = payment.order_code
        return row
```

- [ ] **Step 2: Register it in `src/infrastructure/db/models/__init__.py`**

Add the import alphabetically (after `IngredientORM`, before `QuestORM`) and to `__all__`:

```python
from src.infrastructure.db.models.payment_model import PaymentORM
```

and in `__all__`, insert `"PaymentORM",` between `"IngredientORM",` and `"QuestORM",`.

- [ ] **Step 3: Write `alembic/versions/0009_payments_table.py`**

```python
"""add payments table

Revision ID: 0009
Revises: 0008
Create Date: 2026-09-24
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0009"
down_revision: str | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_PLAN_TYPE = ("monthly", "annual")
_PAYMENT_STATUS = ("pending", "paid", "cancelled", "expired", "failed")


def upgrade() -> None:
    op.create_table(
        "payments",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("order_code", sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column("plan_type", sa.String(length=7), nullable=False),
        sa.Column("amount", sa.Numeric(12, 0), nullable=False),
        sa.Column("status", sa.String(length=9), nullable=False),
        sa.Column("payment_link_id", sa.String(length=64), nullable=True),
        sa.Column("checkout_url", sa.String(length=512), nullable=True),
        sa.Column("qr_code", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_payments"),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_payments_user_id_users", ondelete="CASCADE"
        ),
        sa.UniqueConstraint("order_code", name="uq_payments_order_code"),
        sa.CheckConstraint(f"plan_type IN {_PLAN_TYPE}", name="plan_type"),
        sa.CheckConstraint(f"status IN {_PAYMENT_STATUS}", name="payment_status"),
    )


def downgrade() -> None:
    op.drop_table("payments")
```

- [ ] **Step 4: Verify the migration matches the model**

Run (needs `make docker-up` first):
`uv run alembic upgrade head --sql`
Expected: DDL for `CREATE TABLE payments (...)` with the same columns/constraints as `PaymentORM`, no errors. Then apply it for real:
`uv run alembic upgrade head`
Expected: exits 0, and `psql`/any DB tool shows the `payments` table.

Also run: `uv run python -c "from src.infrastructure.db.models import PaymentORM; print(PaymentORM.__table__.name)"`
Expected: prints `payments`

- [ ] **Step 5: Commit**

```bash
git add src/infrastructure/db/models/payment_model.py src/infrastructure/db/models/__init__.py alembic/versions/0009_payments_table.py
git commit -m "feat: add PaymentORM model and payments table migration"
```

---

### Task 7: SQLAlchemy repositories for `Payment` and `Subscription`

**Files:**
- Create: `src/infrastructure/db/repositories/payment_repository.py`
- Create: `src/infrastructure/db/repositories/subscription_repository.py`
- Test: `tests/integration/test_payment_repository.py`
- Test: `tests/integration/test_subscription_repository.py`

**Interfaces:**
- Consumes: `PaymentORM` (Task 6), `SubscriptionORM` (pre-existing), `Payment`, `Subscription`, `PaymentNotFoundException`
- Produces: `SQLAlchemyPaymentRepository(session)` implementing `PaymentRepositoryProtocol`; `SQLAlchemySubscriptionRepository(session)` implementing `SubscriptionRepositoryProtocol`

- [ ] **Step 1: Write the failing integration tests**

Create `tests/integration/test_payment_repository.py`:

```python
"""Integration tests: SQLAlchemyPaymentRepository against a real PostgreSQL.

Requires a reachable database. Override with TEST_DATABASE_URL; defaults to the
``foodfen`` database from docker-compose. The schema is (re)created per test.
"""

from __future__ import annotations

import os

import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from src.domain.entities.payment import Payment
from src.domain.entities.user import User
from src.domain.enums import PlanType
from src.infrastructure.db.base import Base
from src.infrastructure.db.models.payment_model import PaymentORM  # noqa: F401 — registers the table
from src.infrastructure.db.models.user_model import UserORM  # noqa: F401 — registers the table
from src.infrastructure.db.repositories.payment_repository import SQLAlchemyPaymentRepository
from src.infrastructure.db.repositories.user_repository import SQLAlchemyUserRepository

TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres@localhost:5433/foodfen",
)


@pytest_asyncio.fixture
async def session():
    engine = create_async_engine(TEST_DATABASE_URL)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as s:
        yield s

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


async def _make_user(session) -> User:
    user = await SQLAlchemyUserRepository(session).create(User.create(email="payer@example.com"))
    await session.commit()
    return user


async def test_create_assigns_a_unique_order_code(session):
    user = await _make_user(session)
    repo = SQLAlchemyPaymentRepository(session)

    first = await repo.create(Payment.create(user_id=user.id, plan_type=PlanType.MONTHLY, amount="49000"))
    second = await repo.create(Payment.create(user_id=user.id, plan_type=PlanType.MONTHLY, amount="49000"))
    await session.commit()

    assert first.order_code is not None
    assert second.order_code is not None
    assert first.order_code != second.order_code


async def test_get_by_order_code_round_trips(session):
    user = await _make_user(session)
    repo = SQLAlchemyPaymentRepository(session)
    created = await repo.create(
        Payment.create(user_id=user.id, plan_type=PlanType.ANNUAL, amount="499000")
    )
    await session.commit()

    fetched = await repo.get_by_order_code(created.order_code)
    assert fetched is not None
    assert fetched.id == created.id
    assert fetched.plan_type is PlanType.ANNUAL


async def test_update_persists_status_change(session):
    user = await _make_user(session)
    repo = SQLAlchemyPaymentRepository(session)
    payment = await repo.create(
        Payment.create(user_id=user.id, plan_type=PlanType.MONTHLY, amount="49000")
    )
    await session.commit()

    payment.mark_paid()
    await repo.update(payment)
    await session.commit()

    fetched = await repo.get_by_order_code(payment.order_code)
    assert fetched is not None
    assert fetched.status.value == "paid"
```

Create `tests/integration/test_subscription_repository.py`:

```python
"""Integration tests: SQLAlchemySubscriptionRepository against a real PostgreSQL.

Requires a reachable database. Override with TEST_DATABASE_URL; defaults to the
``foodfen`` database from docker-compose. The schema is (re)created per test.
"""

from __future__ import annotations

import os
from datetime import date
from decimal import Decimal

import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from src.domain.entities.subscription import Subscription
from src.domain.entities.user import User
from src.domain.enums import PlanType
from src.infrastructure.db.base import Base
from src.infrastructure.db.models.subscription_model import SubscriptionORM  # noqa: F401
from src.infrastructure.db.models.user_model import UserORM  # noqa: F401
from src.infrastructure.db.repositories.subscription_repository import (
    SQLAlchemySubscriptionRepository,
)
from src.infrastructure.db.repositories.user_repository import SQLAlchemyUserRepository

TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres@localhost:5433/foodfen",
)


@pytest_asyncio.fixture
async def session():
    engine = create_async_engine(TEST_DATABASE_URL)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as s:
        yield s

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


async def _make_user(session) -> User:
    user = await SQLAlchemyUserRepository(session).create(
        User.create(email="subscriber@example.com")
    )
    await session.commit()
    return user


async def test_save_inserts_when_none_exists(session):
    user = await _make_user(session)
    repo = SQLAlchemySubscriptionRepository(session)
    sub = Subscription.create(
        user_id=user.id,
        plan_type=PlanType.MONTHLY,
        start_date=date(2026, 1, 1),
        end_date=date(2026, 2, 1),
        price=Decimal("49000"),
    )

    saved = await repo.save(sub)
    await session.commit()

    fetched = await repo.get_by_user_id(user.id)
    assert fetched is not None
    assert fetched.id == saved.id


async def test_save_updates_the_single_row_per_user(session):
    user = await _make_user(session)
    repo = SQLAlchemySubscriptionRepository(session)
    first = Subscription.create(
        user_id=user.id,
        plan_type=PlanType.MONTHLY,
        start_date=date(2026, 1, 1),
        end_date=date(2026, 2, 1),
        price=Decimal("49000"),
    )
    await repo.save(first)
    await session.commit()

    renewed = Subscription.renew(first, user.id, PlanType.MONTHLY, Decimal("49000"), date(2026, 1, 20))
    await repo.save(renewed)
    await session.commit()

    fetched = await repo.get_by_user_id(user.id)
    assert fetched is not None
    assert fetched.id == first.id  # same row, not a second one
    assert fetched.start_date == date(2026, 2, 2)
```

- [ ] **Step 2: Run tests to verify they fail**

Run (needs `make docker-up` first): `uv run pytest tests/integration/test_payment_repository.py tests/integration/test_subscription_repository.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.infrastructure.db.repositories.payment_repository'`

- [ ] **Step 3: Write `src/infrastructure/db/repositories/payment_repository.py`**

```python
"""Concrete ``PaymentRepositoryProtocol`` implementation backed by async SQLAlchemy."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.entities.payment import Payment
from src.domain.exceptions import PaymentNotFoundException
from src.infrastructure.db.models.payment_model import PaymentORM


class SQLAlchemyPaymentRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, payment: Payment) -> Payment:
        row = PaymentORM.from_domain(payment)
        self._session.add(row)
        await self._session.flush()
        await self._session.refresh(row)
        return row.to_domain()

    async def get_by_order_code(self, order_code: int) -> Payment | None:
        row = (
            await self._session.execute(
                select(PaymentORM).where(PaymentORM.order_code == order_code)
            )
        ).scalar_one_or_none()
        return row.to_domain() if row is not None else None

    async def update(self, payment: Payment) -> Payment:
        row = await self._session.get(PaymentORM, payment.id)
        if row is None:
            raise PaymentNotFoundException(f"payment {payment.id} not found")
        fresh = PaymentORM.from_domain(payment)
        for column in PaymentORM.__table__.columns.keys():
            if column == "order_code":
                continue  # identity column: never overwritten after insert
            setattr(row, column, getattr(fresh, column))
        await self._session.flush()
        return row.to_domain()
```

- [ ] **Step 4: Write `src/infrastructure/db/repositories/subscription_repository.py`**

```python
"""Concrete ``SubscriptionRepositoryProtocol`` implementation backed by async SQLAlchemy."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.entities.subscription import Subscription
from src.infrastructure.db.models.subscription_model import SubscriptionORM


class SQLAlchemySubscriptionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_user_id(self, user_id: int) -> Subscription | None:
        row = (
            await self._session.execute(
                select(SubscriptionORM).where(SubscriptionORM.user_id == user_id)
            )
        ).scalar_one_or_none()
        return row.to_domain() if row is not None else None

    async def save(self, subscription: Subscription) -> Subscription:
        """Upsert keyed on ``user_id`` — at most one row per user (``uq_subscriptions_user``)."""
        row = (
            await self._session.execute(
                select(SubscriptionORM).where(SubscriptionORM.user_id == subscription.user_id)
            )
        ).scalar_one_or_none()
        if row is None:
            row = SubscriptionORM.from_domain(subscription)
            self._session.add(row)
        else:
            fresh = SubscriptionORM.from_domain(subscription)
            for column in SubscriptionORM.__table__.columns.keys():
                if column == "id":
                    continue
                setattr(row, column, getattr(fresh, column))
        await self._session.flush()
        await self._session.refresh(row)
        return row.to_domain()
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/integration/test_payment_repository.py tests/integration/test_subscription_repository.py -v`
Expected: PASS (5 tests)

- [ ] **Step 6: Commit**

```bash
git add src/infrastructure/db/repositories/payment_repository.py src/infrastructure/db/repositories/subscription_repository.py tests/integration/test_payment_repository.py tests/integration/test_subscription_repository.py
git commit -m "feat: add SQLAlchemy repositories for Payment and Subscription"
```

---

### Task 8: `payos` dependency, config, `PayOsPaymentProvider`

**Files:**
- Modify: `pyproject.toml`
- Modify: `src/infrastructure/config.py`
- Modify: `.env.example`
- Create: `src/infrastructure/payments/payos_provider.py`
- Test: `tests/unit/test_payos_provider.py`

**Interfaces:**
- Consumes: `CheckoutLinkResult`/`ProviderPaymentStatus`/`WebhookPayload`/`PaymentProviderProtocol` (Task 3), `PaymentStatus`, `InvalidWebhookSignatureException`
- Produces: `PayOsPaymentProvider(client, checksum_key)` implementing `PaymentProviderProtocol`; `settings.payos_client_id/api_key/checksum_key/return_url/cancel_url/monthly_price_vnd/annual_price_vnd`

**Important:** the `payos` SDK's exact method/exception names are taken from its public docs and may differ slightly from what's installed. Step 1 installs it and inspects the real API before finalizing the adapter — adjust the code in Step 4 to match what's actually there if it differs.

- [ ] **Step 1: Add the dependency and inspect its real API**

Run: `uv add payos`

Then run: `uv run python -c "import payos; from payos.types import CreatePaymentLinkRequest; print(payos.AsyncPayOS); print(CreatePaymentLinkRequest.__annotations__)"`

If this fails (module/class not found under these names), run `uv run python -c "import payos; print(dir(payos))"` and adjust the import paths used in Step 4 (`AsyncPayOS`, `CreatePaymentLinkRequest`, and the `payment_requests`/`webhooks` attribute names on the client) to match what's actually exposed, keeping `PaymentProviderProtocol`'s own signature (Task 3) unchanged — only this adapter file's internals may need to change.

- [ ] **Step 2: Write the failing test**

Create `tests/unit/test_payos_provider.py`:

```python
"""PayOsPaymentProvider unit tests: fake SDK client, no network."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

import pytest

from src.domain.enums import PaymentStatus
from src.domain.exceptions import InvalidWebhookSignatureException
from src.infrastructure.payments.payos_provider import PayOsPaymentProvider


@dataclass
class _CreateResponse:
    payment_link_id: str
    checkout_url: str
    qr_code: str


@dataclass
class _StatusResponse:
    status: str


class _FakePaymentRequests:
    def __init__(self) -> None:
        self.create_called_with = None
        self.cancel_called_with = None

    async def create(self, payment_data):
        self.create_called_with = payment_data
        return _CreateResponse(
            payment_link_id="link-1", checkout_url="https://pay.example/1", qr_code="qr"
        )

    async def get(self, order_code):
        return _StatusResponse(status="PAID")

    async def cancel(self, order_code, cancellation_reason):
        self.cancel_called_with = (order_code, cancellation_reason)


class _FakeWebhooks:
    def __init__(self, result=None, raises: bool = False):
        self._result = result
        self._raises = raises

    def verify(self, raw_body):
        if self._raises:
            raise ValueError("checksum mismatch")
        return self._result


class _FakeClient:
    def __init__(self, webhooks_result=None, webhooks_raises=False):
        self.payment_requests = _FakePaymentRequests()
        self.webhooks = _FakeWebhooks(webhooks_result, webhooks_raises)


async def test_create_checkout_link_translates_response():
    client = _FakeClient()
    provider = PayOsPaymentProvider(client=client, checksum_key="key")

    result = await provider.create_checkout_link(
        order_code=1,
        amount=Decimal("49000"),
        description="desc",
        cancel_url="https://a/cancel",
        return_url="https://a/return",
    )

    assert result.checkout_url == "https://pay.example/1"
    assert result.qr_code == "qr"


async def test_get_payment_status_maps_paid():
    client = _FakeClient()
    provider = PayOsPaymentProvider(client=client, checksum_key="key")

    result = await provider.get_payment_status(order_code=1)

    assert result.status is PaymentStatus.PAID
    assert result.succeeded is True


async def test_cancel_passes_order_code_and_reason():
    client = _FakeClient()
    provider = PayOsPaymentProvider(client=client, checksum_key="key")

    await provider.cancel(order_code=1, reason="changed mind")

    assert client.payment_requests.cancel_called_with == (1, "changed mind")


async def test_verify_webhook_translates_success_payload():
    client = _FakeClient(webhooks_result={"orderCode": 42, "code": "00"})
    provider = PayOsPaymentProvider(client=client, checksum_key="key")

    payload = provider.verify_webhook(b"raw")

    assert payload.order_code == 42
    assert payload.succeeded is True


async def test_verify_webhook_raises_on_bad_signature():
    client = _FakeClient(webhooks_raises=True)
    provider = PayOsPaymentProvider(client=client, checksum_key="key")

    with pytest.raises(InvalidWebhookSignatureException):
        provider.verify_webhook(b"raw")
```

- [ ] **Step 3: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_payos_provider.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.infrastructure.payments'`

- [ ] **Step 4: Write `src/infrastructure/payments/payos_provider.py`**

(Adjust the `payos.types.CreatePaymentLinkRequest` import and field names inside `create_checkout_link` if Step 1's inspection showed a different shape — everything else in this file is independent of that.)

```python
"""PayOS adapter: implements PaymentProviderProtocol by wrapping the official
`payos` SDK's async client.

The SDK's exact method names come from its published docs; if the installed
version differs, only this file's calls to ``self.client`` need to change —
callers depend on ``PaymentProviderProtocol``, not on payos directly.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Protocol

from src.application.ports.payment_provider import (
    CheckoutLinkResult,
    ProviderPaymentStatus,
    WebhookPayload,
)
from src.domain.enums import PaymentStatus
from src.domain.exceptions import InvalidWebhookSignatureException

_PAYOS_STATUS_MAP = {
    "PENDING": PaymentStatus.PENDING,
    "PROCESSING": PaymentStatus.PENDING,
    "PAID": PaymentStatus.PAID,
    "CANCELLED": PaymentStatus.CANCELLED,
    "EXPIRED": PaymentStatus.EXPIRED,
}


class PayOsClientProtocol(Protocol):
    """The slice of ``payos.AsyncPayOS`` this adapter calls — narrowed to a
    Protocol so tests substitute a fake without importing the real SDK."""

    payment_requests: Any
    webhooks: Any


@dataclass
class PayOsPaymentProvider:
    client: PayOsClientProtocol
    checksum_key: str

    async def create_checkout_link(
        self, order_code: int, amount: Decimal, description: str, cancel_url: str, return_url: str
    ) -> CheckoutLinkResult:
        from payos.types import CreatePaymentLinkRequest

        response = await self.client.payment_requests.create(
            payment_data=CreatePaymentLinkRequest(
                order_code=order_code,
                amount=int(amount),
                description=description,
                cancel_url=cancel_url,
                return_url=return_url,
            )
        )
        return CheckoutLinkResult(
            payment_link_id=response.payment_link_id,
            checkout_url=response.checkout_url,
            qr_code=response.qr_code,
        )

    async def get_payment_status(self, order_code: int) -> ProviderPaymentStatus:
        response = await self.client.payment_requests.get(order_code=order_code)
        status = _PAYOS_STATUS_MAP.get(response.status, PaymentStatus.PENDING)
        return ProviderPaymentStatus(
            order_code=order_code, status=status, succeeded=status is PaymentStatus.PAID
        )

    async def cancel(self, order_code: int, reason: str | None) -> None:
        await self.client.payment_requests.cancel(order_code=order_code, cancellation_reason=reason)

    def verify_webhook(self, raw_body: bytes) -> WebhookPayload:
        # Signature verification is a trust boundary (attacker-controlled input);
        # the SDK's exact exception class is unconfirmed (see Step 1), so any
        # failure here is treated as an invalid signature.
        try:
            data = self.client.webhooks.verify(raw_body)
        except Exception as exc:
            raise InvalidWebhookSignatureException(str(exc)) from exc
        order_code = data["orderCode"] if isinstance(data, dict) else data.order_code
        code = data["code"] if isinstance(data, dict) else data.code
        return WebhookPayload(order_code=order_code, succeeded=code == "00")
```

- [ ] **Step 5: Add PayOS settings to `src/infrastructure/config.py`**

Inside the `Settings` class, after `cloudinary_url`, append:

```python
    # PayOS (payos.vn) — VietQR / bank-transfer checkout for Premium purchases.
    # No default: empty must fail closed, same as the OAuth client ids.
    payos_client_id: str = ""
    payos_api_key: str = ""
    payos_checksum_key: str = ""
    # Frontend/deep-link URLs the user is redirected to after paying — not backend routes.
    payos_return_url: str = ""
    payos_cancel_url: str = ""
    payos_monthly_price_vnd: int = 49_000
    payos_annual_price_vnd: int = 499_000
```

- [ ] **Step 6: Add the new keys to `.env.example`**

Append:

```
PAYOS_CLIENT_ID=
PAYOS_API_KEY=
PAYOS_CHECKSUM_KEY=
PAYOS_RETURN_URL=
PAYOS_CANCEL_URL=
PAYOS_MONTHLY_PRICE_VND=49000
PAYOS_ANNUAL_PRICE_VND=499000
```

- [ ] **Step 7: Run test to verify it passes**

Run: `uv run pytest tests/unit/test_payos_provider.py -v`
Expected: PASS (5 tests)

- [ ] **Step 8: Commit**

```bash
git add pyproject.toml uv.lock src/infrastructure/config.py .env.example src/infrastructure/payments/payos_provider.py tests/unit/test_payos_provider.py
git commit -m "feat: add payos dependency, config, and PayOsPaymentProvider adapter"
```

---

### Task 9: DI wiring — repositories, `PaymentProviderDep`, `CurrentPremiumUserDep`, use-case providers

**Files:**
- Modify: `src/infrastructure/di/repositories.py`
- Modify: `src/infrastructure/di/security.py`
- Modify: `src/infrastructure/di/use_cases.py`
- Modify: `src/infrastructure/di/__init__.py`

**Interfaces:**
- Consumes: everything from Tasks 3–8
- Produces: `PaymentRepositoryDep`, `SubscriptionRepositoryDep`, `PaymentProviderDep`, `CurrentPremiumUserDep`, `CreateCheckoutUseCaseDep`, `HandlePaymentWebhookUseCaseDep`, `GetPaymentStatusUseCaseDep`, `CancelPaymentUseCaseDep`, `GetMySubscriptionUseCaseDep` — all importable from `src.infrastructure.di`

No isolated test for this task (pure wiring, no logic) — it's exercised end-to-end by Task 10's API tests. Verify each step by import instead.

- [ ] **Step 1: Add repository providers to `src/infrastructure/di/repositories.py`**

Add imports at the top (alongside the existing ones):

```python
from src.application.ports.payment_repository import PaymentRepositoryProtocol
from src.application.ports.subscription_repository import SubscriptionRepositoryProtocol
```

and:

```python
from src.infrastructure.db.repositories.payment_repository import SQLAlchemyPaymentRepository
from src.infrastructure.db.repositories.subscription_repository import (
    SQLAlchemySubscriptionRepository,
)
```

Then append at the end of the file:

```python


def get_payment_repository(session: SessionDep) -> PaymentRepositoryProtocol:
    return SQLAlchemyPaymentRepository(session)


PaymentRepositoryDep = Annotated[PaymentRepositoryProtocol, Depends(get_payment_repository)]


def get_subscription_repository(session: SessionDep) -> SubscriptionRepositoryProtocol:
    return SQLAlchemySubscriptionRepository(session)


SubscriptionRepositoryDep = Annotated[
    SubscriptionRepositoryProtocol, Depends(get_subscription_repository)
]
```

- [ ] **Step 2: Verify repositories.py imports cleanly**

Run: `uv run python -c "from src.infrastructure.di.repositories import PaymentRepositoryDep, SubscriptionRepositoryDep"`
Expected: no output, exit 0

- [ ] **Step 3: Add `PaymentProviderDep` and `CurrentPremiumUserDep` to `src/infrastructure/di/security.py`**

Change this existing import line:

```python
from src.infrastructure.di.repositories import UserRepositoryDep
```

to:

```python
from src.infrastructure.di.repositories import SubscriptionRepositoryDep, UserRepositoryDep
```

Add near the top, alongside the other stdlib imports:

```python
from datetime import date
```

Add alongside the other port imports:

```python
from src.application.ports.payment_provider import PaymentProviderProtocol
```

Add alongside the other domain imports:

```python
from src.domain.enums import SubscriptionStatus, SubscriptionTier
from src.domain.exceptions import PremiumRequiredException
```

(`InvalidTokenException` is already imported — leave that line as-is, just add the new one alongside it.)

Add alongside the other infrastructure adapter imports:

```python
from src.infrastructure.payments.payos_provider import PayOsPaymentProvider
```

Then, after the `_image_storage`/`get_image_storage`/`ImageStorageDep` block and before the `_oauth2_scheme` line, insert:

```python
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

```

Finally, at the very end of the file (after `CurrentUserDep = Annotated[User, Depends(get_current_user)]`), append:

```python


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
```

- [ ] **Step 4: Verify security.py imports cleanly**

Run: `uv run python -c "from src.infrastructure.di.security import PaymentProviderDep, CurrentPremiumUserDep"`
Expected: no output, exit 0

- [ ] **Step 5: Add use-case providers to `src/infrastructure/di/use_cases.py`**

Add imports alongside the existing use-case imports:

```python
from src.application.use_cases.cancel_payment import CancelPaymentUseCase
from src.application.use_cases.create_checkout import CreateCheckoutUseCase
from src.application.use_cases.get_my_subscription import GetMySubscriptionUseCase
from src.application.use_cases.get_payment_status import GetPaymentStatusUseCase
from src.application.use_cases.handle_payment_webhook import HandlePaymentWebhookUseCase
```

Change this existing import line:

```python
from src.infrastructure.di.repositories import (
    ChatMessageRepositoryDep,
    RefreshTokenRepositoryDep,
    SocialIdentityRepositoryDep,
    UserRepositoryDep,
)
```

to:

```python
from src.infrastructure.di.repositories import (
    ChatMessageRepositoryDep,
    PaymentRepositoryDep,
    RefreshTokenRepositoryDep,
    SocialIdentityRepositoryDep,
    SubscriptionRepositoryDep,
    UserRepositoryDep,
)
```

Change this existing import line:

```python
from src.infrastructure.di.security import (
    AiChatProviderDep,
    FoodVisionProviderDep,
    ImageStorageDep,
    PasswordHasherDep,
    SocialIdentityVerifierDep,
    TokenServiceDep,
)
```

to:

```python
from src.infrastructure.di.security import (
    AiChatProviderDep,
    FoodVisionProviderDep,
    ImageStorageDep,
    PasswordHasherDep,
    PaymentProviderDep,
    SocialIdentityVerifierDep,
    TokenServiceDep,
)
```

Then append at the end of the file:

```python


def get_create_checkout_use_case(
    payments: PaymentRepositoryDep, provider: PaymentProviderDep
) -> CreateCheckoutUseCase:
    return CreateCheckoutUseCase(
        payments=payments,
        provider=provider,
        monthly_price_vnd=settings.payos_monthly_price_vnd,
        annual_price_vnd=settings.payos_annual_price_vnd,
        return_url=settings.payos_return_url,
        cancel_url=settings.payos_cancel_url,
    )


def get_handle_payment_webhook_use_case(
    payments: PaymentRepositoryDep,
    provider: PaymentProviderDep,
    subscriptions: SubscriptionRepositoryDep,
    users: UserRepositoryDep,
) -> HandlePaymentWebhookUseCase:
    return HandlePaymentWebhookUseCase(
        payments=payments, provider=provider, subscriptions=subscriptions, users=users
    )


def get_get_payment_status_use_case(
    payments: PaymentRepositoryDep,
    provider: PaymentProviderDep,
    subscriptions: SubscriptionRepositoryDep,
    users: UserRepositoryDep,
) -> GetPaymentStatusUseCase:
    return GetPaymentStatusUseCase(
        payments=payments, provider=provider, subscriptions=subscriptions, users=users
    )


def get_cancel_payment_use_case(
    payments: PaymentRepositoryDep, provider: PaymentProviderDep
) -> CancelPaymentUseCase:
    return CancelPaymentUseCase(payments=payments, provider=provider)


def get_get_my_subscription_use_case(
    subscriptions: SubscriptionRepositoryDep,
) -> GetMySubscriptionUseCase:
    return GetMySubscriptionUseCase(subscriptions=subscriptions)


CreateCheckoutUseCaseDep = Annotated[CreateCheckoutUseCase, Depends(get_create_checkout_use_case)]
HandlePaymentWebhookUseCaseDep = Annotated[
    HandlePaymentWebhookUseCase, Depends(get_handle_payment_webhook_use_case)
]
GetPaymentStatusUseCaseDep = Annotated[
    GetPaymentStatusUseCase, Depends(get_get_payment_status_use_case)
]
CancelPaymentUseCaseDep = Annotated[CancelPaymentUseCase, Depends(get_cancel_payment_use_case)]
GetMySubscriptionUseCaseDep = Annotated[
    GetMySubscriptionUseCase, Depends(get_get_my_subscription_use_case)
]
```

- [ ] **Step 6: Re-export everything from `src/infrastructure/di/__init__.py`**

Add `PaymentRepositoryDep`, `SubscriptionRepositoryDep`, `get_payment_repository`, `get_subscription_repository` to the `from src.infrastructure.di.repositories import (...)` block; add `PaymentProviderDep`, `CurrentPremiumUserDep`, `get_payment_provider`, `get_current_premium_user` to the `from src.infrastructure.di.security import (...)` block; add `CreateCheckoutUseCaseDep`, `HandlePaymentWebhookUseCaseDep`, `GetPaymentStatusUseCaseDep`, `CancelPaymentUseCaseDep`, `GetMySubscriptionUseCaseDep`, `get_create_checkout_use_case`, `get_handle_payment_webhook_use_case`, `get_get_payment_status_use_case`, `get_cancel_payment_use_case`, `get_get_my_subscription_use_case` to the `from src.infrastructure.di.use_cases import (...)` block. Add all of the same names to `__all__`, keeping it alphabetically sorted as the existing list is.

- [ ] **Step 7: Verify the whole DI graph imports and resolves**

Run: `uv run python -c "from src.infrastructure.di import CreateCheckoutUseCaseDep, HandlePaymentWebhookUseCaseDep, GetPaymentStatusUseCaseDep, CancelPaymentUseCaseDep, GetMySubscriptionUseCaseDep, CurrentPremiumUserDep, PaymentProviderDep, PaymentRepositoryDep, SubscriptionRepositoryDep; print('ok')"`
Expected: prints `ok`

Run: `uv run lint-imports`
Expected: no violations

- [ ] **Step 8: Commit**

```bash
git add src/infrastructure/di/repositories.py src/infrastructure/di/security.py src/infrastructure/di/use_cases.py src/infrastructure/di/__init__.py
git commit -m "feat: wire payment/subscription repositories, provider, and use cases into DI"
```

---

### Task 10: Adapters — schemas, controllers, `main.py`, exception mapping, API tests

**Files:**
- Create: `src/adapters/schemas/payment_schemas.py`
- Create: `src/adapters/schemas/subscription_schemas.py`
- Create: `src/adapters/controllers/payment_controller.py`
- Create: `src/adapters/controllers/subscription_controller.py`
- Modify: `src/main.py`
- Modify: `src/adapters/exception_handlers.py`
- Modify: `tests/api/conftest.py`
- Test: `tests/api/test_payment_endpoints.py`

**Interfaces:**
- Consumes: everything from Tasks 1–9
- Produces: `POST /payments/checkout`, `GET /payments/{order_code}`, `POST /payments/{order_code}/cancel`, `POST /payments/webhook`, `GET /subscriptions/me` — all registered on `app`

- [ ] **Step 1: Write `src/adapters/schemas/payment_schemas.py`**

```python
"""HTTP wire models for the payment API."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from src.adapters.schemas.base import CamelModel
from src.application.dtos.payment import CheckoutOutputDTO, PaymentOutputDTO
from src.domain.enums import PaymentStatus, PlanType


class CreateCheckoutRequest(CamelModel):
    plan_type: PlanType


class CheckoutResponse(CamelModel):
    order_code: int
    checkout_url: str
    qr_code: str
    amount: Decimal
    plan_type: PlanType
    status: PaymentStatus

    @classmethod
    def from_dto(cls, dto: CheckoutOutputDTO) -> CheckoutResponse:
        return cls(
            order_code=dto.order_code,
            checkout_url=dto.checkout_url,
            qr_code=dto.qr_code,
            amount=dto.amount,
            plan_type=dto.plan_type,
            status=dto.status,
        )


class PaymentResponse(CamelModel):
    order_code: int
    status: PaymentStatus
    amount: Decimal
    plan_type: PlanType
    paid_at: datetime | None
    created_at: datetime

    @classmethod
    def from_dto(cls, dto: PaymentOutputDTO) -> PaymentResponse:
        return cls(
            order_code=dto.order_code,
            status=dto.status,
            amount=dto.amount,
            plan_type=dto.plan_type,
            paid_at=dto.paid_at,
            created_at=dto.created_at,
        )


class CancelPaymentRequest(CamelModel):
    cancellation_reason: str | None = None
```

- [ ] **Step 2: Write `src/adapters/schemas/subscription_schemas.py`**

```python
"""HTTP wire models for the subscription API."""

from __future__ import annotations

from datetime import date

from src.adapters.schemas.base import CamelModel
from src.application.dtos.subscription import SubscriptionOutputDTO
from src.domain.enums import PlanType, SubscriptionStatus


class SubscriptionResponse(CamelModel):
    plan_type: PlanType
    status: SubscriptionStatus
    start_date: date
    end_date: date | None

    @classmethod
    def from_dto(cls, dto: SubscriptionOutputDTO) -> SubscriptionResponse:
        return cls(
            plan_type=dto.plan_type,
            status=dto.status,
            start_date=dto.start_date,
            end_date=dto.end_date,
        )


class MySubscriptionResponse(CamelModel):
    has_active_subscription: bool
    subscription: SubscriptionResponse | None

    @classmethod
    def from_dto(cls, dto: SubscriptionOutputDTO | None) -> MySubscriptionResponse:
        if dto is None:
            return cls(has_active_subscription=False, subscription=None)
        return cls(
            has_active_subscription=dto.status.value == "active",
            subscription=SubscriptionResponse.from_dto(dto),
        )
```

- [ ] **Step 3: Write `src/adapters/controllers/payment_controller.py`**

```python
"""Payment endpoints (PayOS checkout). HTTP <-> application DTO translation only."""

from __future__ import annotations

from fastapi import APIRouter, Request

from src.adapters.schemas.payment_schemas import (
    CancelPaymentRequest,
    CheckoutResponse,
    CreateCheckoutRequest,
    PaymentResponse,
)
from src.application.dtos.payment import CreateCheckoutInputDTO
from src.infrastructure.di import (
    CancelPaymentUseCaseDep,
    CreateCheckoutUseCaseDep,
    CurrentUserDep,
    GetPaymentStatusUseCaseDep,
    HandlePaymentWebhookUseCaseDep,
)

router = APIRouter(prefix="/payments", tags=["payments"])


@router.post("/checkout", response_model=CheckoutResponse)
async def create_checkout(
    body: CreateCheckoutRequest, user: CurrentUserDep, use_case: CreateCheckoutUseCaseDep
) -> CheckoutResponse:
    result = await use_case.execute(CreateCheckoutInputDTO(user_id=user.id, plan_type=body.plan_type))
    return CheckoutResponse.from_dto(result)


@router.get("/{order_code}", response_model=PaymentResponse)
async def get_payment(
    order_code: int, user: CurrentUserDep, use_case: GetPaymentStatusUseCaseDep
) -> PaymentResponse:
    result = await use_case.execute(user_id=user.id, order_code=order_code)
    return PaymentResponse.from_dto(result)


@router.post("/{order_code}/cancel", response_model=PaymentResponse)
async def cancel_payment(
    order_code: int,
    body: CancelPaymentRequest,
    user: CurrentUserDep,
    use_case: CancelPaymentUseCaseDep,
) -> PaymentResponse:
    result = await use_case.execute(
        user_id=user.id, order_code=order_code, reason=body.cancellation_reason
    )
    return PaymentResponse.from_dto(result)


@router.post("/webhook", status_code=200)
async def payment_webhook(
    request: Request, use_case: HandlePaymentWebhookUseCaseDep
) -> dict[str, str]:
    raw_body = await request.body()
    await use_case.execute(raw_body)
    return {"code": "00"}
```

- [ ] **Step 4: Write `src/adapters/controllers/subscription_controller.py`**

```python
"""Subscription endpoints. HTTP <-> application DTO translation only."""

from __future__ import annotations

from fastapi import APIRouter

from src.adapters.schemas.subscription_schemas import MySubscriptionResponse
from src.infrastructure.di import CurrentUserDep, GetMySubscriptionUseCaseDep

router = APIRouter(prefix="/subscriptions", tags=["subscriptions"])


@router.get("/me", response_model=MySubscriptionResponse)
async def get_my_subscription(
    user: CurrentUserDep, use_case: GetMySubscriptionUseCaseDep
) -> MySubscriptionResponse:
    result = await use_case.execute(user.id)
    return MySubscriptionResponse.from_dto(result)
```

- [ ] **Step 5: Register both routers in `src/main.py`**

Add imports alongside the existing controller imports:

```python
from src.adapters.controllers.payment_controller import router as payment_router
from src.adapters.controllers.subscription_controller import router as subscription_router
```

In `create_app`, add after `app.include_router(food_analysis_router)`:

```python
    app.include_router(payment_router)
    app.include_router(subscription_router)
```

- [ ] **Step 6: Add exception mappings to `src/adapters/exception_handlers.py`**

Change the import block from:

```python
from src.domain.exceptions import (
    AuthenticationException,
    DomainException,
    EntityNotFoundException,
    InvalidAttributeException,
    UserAlreadyExistsException,
)
```

to:

```python
from src.domain.exceptions import (
    AuthenticationException,
    DomainException,
    EntityNotFoundException,
    InvalidAttributeException,
    InvalidWebhookSignatureException,
    PremiumRequiredException,
    UserAlreadyExistsException,
)
```

Change `EXCEPTION_STATUS` from:

```python
EXCEPTION_STATUS: list[tuple[type[DomainException], int]] = [
    (InvalidAttributeException, 400),  # + InvalidUserAttributeException, WeakPasswordException
    (AuthenticationException, 401),  # + InvalidCredentialsException, InvalidTokenException
    (EntityNotFoundException, 404),  # + UserNotFoundException
    (DomainException, 400),  # catch-all
]
```

to:

```python
EXCEPTION_STATUS: list[tuple[type[DomainException], int]] = [
    (InvalidWebhookSignatureException, 401),  # a more specific AuthenticationException
    (InvalidAttributeException, 400),  # + InvalidUserAttributeException, WeakPasswordException, InvalidPaymentStateException
    (AuthenticationException, 401),  # + InvalidCredentialsException, InvalidTokenException
    (PremiumRequiredException, 402),
    (EntityNotFoundException, 404),  # + UserNotFoundException, PaymentNotFoundException
    (DomainException, 400),  # catch-all
]
```

- [ ] **Step 7: Add a `payment_provider` fixture to `tests/api/conftest.py`**

Add these imports alongside the existing ones:

```python
from src.application.ports.payment_provider import (
    CheckoutLinkResult,
    ProviderPaymentStatus,
    WebhookPayload,
)
from src.domain.enums import PaymentStatus
from src.domain.exceptions import InvalidWebhookSignatureException
```

and add `get_payment_provider` to the `from src.infrastructure.di import (...)` block.

Add this class and fixture (near the other `Fake*Provider` classes/fixtures):

```python
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
```

Then change the `client` fixture from:

```python
@pytest_asyncio.fixture
async def client(
    notifier, social_verifier, ai_chat_provider, food_vision_provider, image_storage
):  # overrides before requests
```

to:

```python
@pytest_asyncio.fixture
async def client(
    notifier, social_verifier, ai_chat_provider, food_vision_provider, image_storage, payment_provider
):  # overrides before requests
```

- [ ] **Step 8: Write the failing API test**

Create `tests/api/test_payment_endpoints.py`:

```python
"""POST /payments/*, GET /subscriptions/me — end-to-end against the real app.

PayOS itself is faked (see `payment_provider` in conftest.py) — a test suite
should never depend on it.
"""

from __future__ import annotations

from decimal import Decimal

from src.application.ports.payment_provider import WebhookPayload


async def test_checkout_returns_a_checkout_link(client, signed_up):
    headers = {"Authorization": f"Bearer {signed_up['accessToken']}"}

    resp = await client.post("/payments/checkout", json={"planType": "monthly"}, headers=headers)

    assert resp.status_code == 200
    body = resp.json()
    assert body["checkoutUrl"].startswith("https://pay.example/")
    assert body["status"] == "pending"
    assert Decimal(str(body["amount"])) == Decimal("49000")


async def test_checkout_requires_auth(client):
    resp = await client.post("/payments/checkout", json={"planType": "monthly"})
    assert resp.status_code == 401


async def test_webhook_with_valid_signature_marks_payment_paid(client, signed_up, payment_provider):
    headers = {"Authorization": f"Bearer {signed_up['accessToken']}"}
    checkout = (
        await client.post("/payments/checkout", json={"planType": "monthly"}, headers=headers)
    ).json()

    payment_provider.next_webhook = WebhookPayload(order_code=checkout["orderCode"], succeeded=True)
    resp = await client.post("/payments/webhook", content=b"raw-webhook-body")
    assert resp.status_code == 200

    status_resp = await client.get(f"/payments/{checkout['orderCode']}", headers=headers)
    assert status_resp.json()["status"] == "paid"


async def test_webhook_with_invalid_signature_is_rejected(client, payment_provider):
    payment_provider.webhook_should_fail_signature = True
    resp = await client.post("/payments/webhook", content=b"raw-webhook-body")
    assert resp.status_code == 401


async def test_subscription_me_before_and_after_payment(client, signed_up, payment_provider):
    headers = {"Authorization": f"Bearer {signed_up['accessToken']}"}

    before = await client.get("/subscriptions/me", headers=headers)
    assert before.json()["hasActiveSubscription"] is False

    checkout = (
        await client.post("/payments/checkout", json={"planType": "monthly"}, headers=headers)
    ).json()
    payment_provider.next_webhook = WebhookPayload(order_code=checkout["orderCode"], succeeded=True)
    await client.post("/payments/webhook", content=b"raw-webhook-body")

    after = await client.get("/subscriptions/me", headers=headers)
    assert after.json()["hasActiveSubscription"] is True
    assert after.json()["subscription"]["planType"] == "monthly"


async def test_cancel_rejects_an_already_paid_payment(client, signed_up, payment_provider):
    headers = {"Authorization": f"Bearer {signed_up['accessToken']}"}
    checkout = (
        await client.post("/payments/checkout", json={"planType": "monthly"}, headers=headers)
    ).json()
    payment_provider.next_webhook = WebhookPayload(order_code=checkout["orderCode"], succeeded=True)
    await client.post("/payments/webhook", content=b"raw-webhook-body")

    resp = await client.post(f"/payments/{checkout['orderCode']}/cancel", json={}, headers=headers)
    assert resp.status_code == 400


async def test_premium_gate_blocks_free_user_then_passes_after_payment(
    client, signed_up, payment_provider
):
    from src.infrastructure.di import CurrentPremiumUserDep
    from src.main import app

    @app.get("/__test/premium-only")
    async def _premium_only(user: CurrentPremiumUserDep) -> dict[str, str]:
        return {"email": user.email}

    headers = {"Authorization": f"Bearer {signed_up['accessToken']}"}

    blocked = await client.get("/__test/premium-only", headers=headers)
    assert blocked.status_code == 402

    checkout = (
        await client.post("/payments/checkout", json={"planType": "monthly"}, headers=headers)
    ).json()
    payment_provider.next_webhook = WebhookPayload(order_code=checkout["orderCode"], succeeded=True)
    await client.post("/payments/webhook", content=b"raw-webhook-body")

    allowed = await client.get("/__test/premium-only", headers=headers)
    assert allowed.status_code == 200
```

- [ ] **Step 9: Run the full test suite**

Run (needs `make docker-up` first): `uv run pytest -v`
Expected: PASS — every test in `tests/unit/`, `tests/integration/`, `tests/api/`, including all 7 new/changed files from this plan, with no regressions in existing auth/chat/food tests.

Also run: `uv run lint-imports`
Expected: no violations

- [ ] **Step 10: Commit**

```bash
git add src/adapters/schemas/payment_schemas.py src/adapters/schemas/subscription_schemas.py src/adapters/controllers/payment_controller.py src/adapters/controllers/subscription_controller.py src/main.py src/adapters/exception_handlers.py tests/api/conftest.py tests/api/test_payment_endpoints.py
git commit -m "feat: add payment/subscription controllers, wire them into the app, and add API tests"
```

---

## Self-Review Notes

- **Spec coverage:** every spec section has a task — domain (Tasks 1–2), application ports/use-cases (Tasks 3–5), infrastructure ORM/migration/repos/SDK adapter/DI (Tasks 6–9), adapters/controllers/exception-mapping/API tests (Task 10). The spec's "Open items" (exact SDK surface, webhook ack body) are handled explicitly in Task 8 Step 1 (inspect before finalizing) and Task 10 Step 3 (`{"code": "00"}` ack).
- **Placeholder scan:** no TBD/TODO; the one deliberately open item (payos SDK exact API) has a concrete inspection+adjustment step rather than being left vague.
- **Type consistency:** `PaymentRepositoryProtocol.create/get_by_order_code/update`, `SubscriptionRepositoryProtocol.get_by_user_id/save`, and `PaymentProviderProtocol.create_checkout_link/get_payment_status/cancel/verify_webhook` are defined once in Task 3/4 and used with the same names/signatures in every later task (5, 7, 8, 9). `apply_payment_result(payment, succeeded, payments, subscriptions, users)` keeps the same parameter order everywhere it's called (Tasks 4, 5).
