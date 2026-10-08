# Restaurants, Dishes & Admin Role Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restaurant owners register a restaurant and a menu with per-serving nutrition; an `admin` role moderates them and sees a cash-flow/growth dashboard.

**Architecture:** One new aggregate (restaurant + dishes) through the existing Clean Architecture layers, moderation as status columns plus entity methods, one admin guard dependency, and a dashboard that buckets raw rows into Vietnam days in the application layer.

**Tech Stack:** Python 3.11+, FastAPI, async SQLAlchemy 2.0, Alembic, Pydantic v2, pytest + pytest-asyncio, `uv`.

**Spec:** `docs/superpowers/specs/2026-10-08-restaurants-admin-design.md`. Business rules: `docs/marketplace.md` (living doc; read both).

## Global Constraints

- `src/domain/` imports stdlib only; `src/application/` never imports fastapi/sqlalchemy/pydantic/adapters/infrastructure. Run `uv run lint-imports` after every task.
- Ports are `typing.Protocol`; use cases take and return dataclass DTOs (partial updates use `updates: dict[str, Any]`, like `UpdateUserProfileInputDTO`).
- Never raise `HTTPException`; raise a `DomainException` subclass mapped in `src/adapters/exception_handlers.py`.
- Wire format is camelCase (`CamelModel`). Money in responses uses `MoneyField`; dashboard money is `int` VND.
- New tables use `UUIDPrimaryKey`; fixed string sets are `StrEnum` + `enum_column()`; money is `Numeric`/`Decimal`.
- Migration CHECK names are bare (`"moderation_status"`, `"user_role"`); PK/FK/UQ/IX names are given in full.
- Nutrition column names and types match `food_entries`: `kcal INTEGER`, `protein_g`/`carbs_g`/`fat_g FLOAT`, `fiber_g FLOAT NULL`.
- Vietnam day = UTC+7. Dashboard range defaults to the last 30 days, max 366 days, inclusive, zero-filled.
- Images: `image/jpeg`, `image/png`, `image/webp`; max 5 MB; violations → `UnreadableImageException` (400). 20 uploads/min/user.
- DI wiring only in `src/infrastructure/di/`; controllers import only `from src.infrastructure.di import ...`.
- Commit messages end with `Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>` (or the executing model's line).

## Review Focus

1. **A restaurant whose owner adds a dish after approval.** The restaurant stays public, and the new dish shows in the admin queue → test `test_queue_includes_approved_restaurant_with_pending_dish` (Task 6).
2. **Two concurrent `POST /restaurants` from one user.** The second must be a 409, not a 500 from the UNIQUE violation → `test_add_duplicate_owner_raises_already_exists` (Task 2).
3. **An owner sends `null` for a required field on PATCH** (`{"name": null}`, `{"kcal": null}`). Expect a 422 with `errors.<field>`, not a 500 from the entity → `test_patch_null_required_field_is_422` (Task 4), `test_patch_null_kcal_is_422` (Task 5).
4. **A payment paid at 23:30 Vietnam time.** It belongs to that Vietnam day, not the next UTC day → `test_bucketing_uses_vietnam_day_boundary` (Task 7).
5. **A demoted admin with a still-valid access token.** Expect 403 immediately, since the role is read from the DB → `test_demoted_admin_is_forbidden_immediately` (Task 3).

---

## File map

| Layer | Create | Modify |
|---|---|---|
| domain | `src/domain/moderation.py`, `src/domain/entities/restaurant.py`, `src/domain/entities/dish.py` | `src/domain/enums.py`, `src/domain/exceptions.py`, `src/domain/entities/user.py` |
| application | `ports/restaurant_repository.py`, `ports/admin_stats_repository.py`, `dtos/restaurant.py`, `dtos/admin.py`, use cases (listed per task), `use_cases/restaurant_support.py` | `dtos/user.py` |
| infrastructure | `db/models/restaurant_model.py`, `db/models/dish_model.py`, `db/repositories/restaurant_repository.py`, `db/repositories/admin_stats_repository.py`, `alembic/versions/0021_restaurants_and_roles.py` | `db/models/user_model.py`, `db/models/__init__.py`, `di/repositories.py`, `di/use_cases.py`, `di/security.py`, `di/__init__.py` |
| adapters | `schemas/restaurant_schemas.py`, `schemas/admin_schemas.py`, `controllers/restaurant_controller.py`, `controllers/admin_controller.py` | `schemas/user_schemas.py`, `controllers/auth_controller.py`, `exception_handlers.py`, `src/main.py` |
| tests | `tests/unit/test_restaurant_entities.py`, `tests/unit/test_admin_dashboard.py`, `tests/integration/test_restaurant_repository.py`, `tests/api/test_restaurant_endpoints.py`, `tests/api/test_admin_endpoints.py` | `tests/api/conftest.py` |
| docs | | `docs/marketplace.md`, `CLAUDE.md` |

---

### Task 1: Domain (enums, exceptions, moderation rules, entities, user role)

**Files:**
- Modify: `src/domain/enums.py`, `src/domain/exceptions.py`, `src/domain/entities/user.py`, `src/adapters/exception_handlers.py`
- Create: `src/domain/moderation.py`, `src/domain/entities/restaurant.py`, `src/domain/entities/dish.py`
- Test: `tests/unit/test_restaurant_entities.py`

**Interfaces:**
- Produces:
  - `UserRole`, `ModerationStatus`, `ReviewDecision` enums.
  - `User.role: UserRole` and `User.is_admin`.
  - `Restaurant` and `Dish` dataclasses: `.create(...)`, `.review(decision, reason, now)`, `.mark_edited(now)`.
  - Exceptions: `InvalidRestaurantAttributeException`, `RestaurantNotFoundException`, `DishNotFoundException`, `RestaurantAlreadyExistsException` (409), `AdminRequiredException` (403).

- [ ] **Step 1: Write the failing tests**

`tests/unit/test_restaurant_entities.py`:

```python
"""Restaurant / Dish invariants and moderation transitions. No I/O."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest

from src.domain.entities.dish import Dish
from src.domain.entities.restaurant import Restaurant
from src.domain.entities.user import User
from src.domain.enums import ModerationStatus, ReviewDecision, UserRole
from src.domain.exceptions import InvalidRestaurantAttributeException

NOW = datetime(2026, 10, 8, 12, tzinfo=UTC)


def _restaurant(**overrides) -> Restaurant:
    fields = dict(
        user_id=1, name=" Quán Ngon ", address="1 Lê Lợi", phone="0901234567",
        opening_hours="7:00-21:00", latitude=10.7769, longitude=106.7009,
    )
    return Restaurant.create(**{**fields, **overrides})


def _dish(**overrides) -> Dish:
    fields = dict(
        restaurant_id=uuid4(), name="Phở bò", price=Decimal("55000"), serving_g=500,
        kcal=450, protein_g=30.0, carbs_g=55.0, fat_g=12.0,
    )
    return Dish.create(**{**fields, **overrides})


def test_new_restaurant_is_pending_and_stripped():
    r = _restaurant(description="  ")
    assert r.status == ModerationStatus.PENDING
    assert r.name == "Quán Ngon"
    assert r.description is None
    assert r.rejection_reason is None


@pytest.mark.parametrize("field,value", [
    ("latitude", 90.1), ("latitude", -90.1), ("longitude", 180.1), ("longitude", -180.1),
    ("name", "  "), ("address", ""), ("phone", " "), ("opening_hours", ""),
])
def test_restaurant_rejects_bad_fields(field, value):
    with pytest.raises(InvalidRestaurantAttributeException):
        _restaurant(**{field: value})


@pytest.mark.parametrize("field,value", [
    ("price", Decimal("-1")), ("serving_g", 0), ("kcal", -1), ("protein_g", -0.1),
    ("carbs_g", -1.0), ("fat_g", -1.0), ("fiber_g", -1.0), ("name", " "),
])
def test_dish_rejects_bad_fields(field, value):
    with pytest.raises(InvalidRestaurantAttributeException):
        _dish(**{field: value})


def test_reject_requires_reason_and_leaves_entity_unchanged():
    r = _restaurant()
    with pytest.raises(InvalidRestaurantAttributeException):
        r.review(ReviewDecision.REJECTED, "  ", NOW)
    assert r.status == ModerationStatus.PENDING
    assert r.reviewed_at is None


def test_review_sets_and_clears_reason_and_is_idempotent():
    d = _dish()
    d.review(ReviewDecision.REJECTED, " kcal too low ", NOW)
    assert (d.status, d.rejection_reason, d.reviewed_at) == (ModerationStatus.REJECTED, "kcal too low", NOW)
    d.review(ReviewDecision.APPROVED, "ignored", NOW)
    d.review(ReviewDecision.APPROVED, None, NOW)
    assert (d.status, d.rejection_reason) == (ModerationStatus.APPROVED, None)


def test_editing_any_dish_returns_it_to_pending():
    d = _dish()
    d.review(ReviewDecision.APPROVED, None, NOW)
    d.mark_edited(NOW)
    assert d.status == ModerationStatus.PENDING
    assert d.updated_at == NOW


def test_editing_approved_restaurant_keeps_it_approved():
    r = _restaurant()
    r.review(ReviewDecision.APPROVED, None, NOW)
    r.mark_edited(NOW)
    assert r.status == ModerationStatus.APPROVED


def test_editing_rejected_restaurant_resubmits_it():
    r = _restaurant()
    r.review(ReviewDecision.REJECTED, "no address proof", NOW)
    r.mark_edited(NOW)
    assert (r.status, r.rejection_reason) == (ModerationStatus.PENDING, None)


def test_rejected_without_reason_cannot_be_constructed():
    with pytest.raises(InvalidRestaurantAttributeException):
        Restaurant(
            id=uuid4(), user_id=1, name="x", address="x", phone="x", opening_hours="x",
            latitude=0, longitude=0, status=ModerationStatus.REJECTED,
        )


def test_user_defaults_to_user_role():
    user = User.create(email="a@b.co")
    assert user.role == UserRole.USER and not user.is_admin
    assert User(email="a@b.co", role=UserRole.ADMIN).is_admin
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/test_restaurant_entities.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.domain.entities.dish'`

- [ ] **Step 3: Implement**

Append to `src/domain/enums.py`:

```python
class UserRole(StrEnum):
    """Only `admin` grants anything. Restaurant ownership is data (`restaurants.user_id`), not a role."""

    USER = "user"
    ADMIN = "admin"


class ModerationStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class ReviewDecision(StrEnum):
    APPROVED = "approved"
    REJECTED = "rejected"
```

Append to `src/domain/exceptions.py`:

```python
class InvalidRestaurantAttributeException(InvalidAttributeException):
    """A restaurant or dish attribute violates a domain invariant."""


class RestaurantNotFoundException(EntityNotFoundException):
    """No such restaurant, or the caller owns none."""


class DishNotFoundException(EntityNotFoundException):
    """No such dish, or it belongs to another restaurant."""


class RestaurantAlreadyExistsException(DomainException):
    """The user already owns a restaurant (one per user). Maps to HTTP 409."""


class AdminRequiredException(DomainException):
    """The caller is not an admin. Maps to HTTP 403."""
```

In `src/adapters/exception_handlers.py`, import the two new types and add to `EXCEPTION_STATUS` (before the `DomainException` catch-all):

```python
    (RestaurantAlreadyExistsException, 409),
    (AdminRequiredException, 403),
```

Create `src/domain/moderation.py`:

```python
"""Moderation rules shared by Restaurant and Dish. Standard library only."""

from __future__ import annotations

from src.domain.enums import ModerationStatus
from src.domain.exceptions import InvalidRestaurantAttributeException


def checked_reason(status: ModerationStatus, reason: str | None) -> str | None:
    """The rejection reason to store for ``status``: required when rejected, dropped otherwise."""
    if status != ModerationStatus.REJECTED:
        return None
    text = (reason or "").strip()
    if not text:
        raise InvalidRestaurantAttributeException("a rejection reason is required")
    return text
```

Create `src/domain/entities/restaurant.py`:

```python
"""Restaurant entity: one per owner, moderated before it is public. See docs/marketplace.md."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import UUID, uuid4

from src.domain.enums import ModerationStatus, ReviewDecision
from src.domain.exceptions import InvalidRestaurantAttributeException
from src.domain.moderation import checked_reason
from src.domain.validation import require_non_empty


def _now() -> datetime:
    return datetime.now(UTC)


@dataclass
class Restaurant:
    id: UUID
    user_id: int  # the owner
    name: str
    address: str
    phone: str
    opening_hours: str  # free text, e.g. "7:00-21:00"
    latitude: float
    longitude: float
    description: str | None = None
    image_url: str | None = None
    status: ModerationStatus = ModerationStatus.PENDING
    rejection_reason: str | None = None
    created_at: datetime = field(default_factory=_now)
    updated_at: datetime = field(default_factory=_now)
    reviewed_at: datetime | None = None

    def __post_init__(self) -> None:
        exc = InvalidRestaurantAttributeException
        self.name = require_non_empty(self.name, "name", exc)
        self.address = require_non_empty(self.address, "address", exc)
        self.phone = require_non_empty(self.phone, "phone", exc)
        self.opening_hours = require_non_empty(self.opening_hours, "opening_hours", exc)
        self.description = (self.description or "").strip() or None
        if not -90 <= self.latitude <= 90:
            raise exc(f"latitude must be between -90 and 90, got {self.latitude!r}")
        if not -180 <= self.longitude <= 180:
            raise exc(f"longitude must be between -180 and 180, got {self.longitude!r}")
        self.rejection_reason = checked_reason(self.status, self.rejection_reason)

    @classmethod
    def create(
        cls,
        *,
        user_id: int,
        name: str,
        address: str,
        phone: str,
        opening_hours: str,
        latitude: float,
        longitude: float,
        description: str | None = None,
        image_url: str | None = None,
    ) -> Restaurant:
        now = _now()
        return cls(
            id=uuid4(), user_id=user_id, name=name, address=address, phone=phone,
            opening_hours=opening_hours, latitude=latitude, longitude=longitude,
            description=description, image_url=image_url, created_at=now, updated_at=now,
        )

    def review(self, decision: ReviewDecision, reason: str | None, now: datetime) -> None:
        """Approve, reject, or take down (reject an approved one). Idempotent."""
        status = ModerationStatus(decision.value)
        self.rejection_reason = checked_reason(status, reason)  # raises before any change
        self.status = status
        self.reviewed_at = now

    def mark_edited(self, now: datetime) -> None:
        """Profile edits go live without re-review; editing a rejected restaurant resubmits it."""
        self.updated_at = now
        if self.status == ModerationStatus.REJECTED:
            self.status = ModerationStatus.PENDING
            self.rejection_reason = None
```

Create `src/domain/entities/dish.py`:

```python
"""Dish entity: a menu item with per-serving nutrition, moderated on its own."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from src.domain.enums import ModerationStatus, ReviewDecision
from src.domain.exceptions import InvalidRestaurantAttributeException
from src.domain.moderation import checked_reason
from src.domain.validation import require_non_empty, require_non_negative, require_positive


def _now() -> datetime:
    return datetime.now(UTC)


@dataclass
class Dish:
    id: UUID
    restaurant_id: UUID
    name: str
    price: Decimal  # VND
    serving_g: int
    # Per serving. Names/types match food_entries so a dish can be logged as-is.
    kcal: int
    protein_g: float
    carbs_g: float
    fat_g: float
    fiber_g: float | None = None
    description: str | None = None
    image_url: str | None = None
    status: ModerationStatus = ModerationStatus.PENDING
    rejection_reason: str | None = None
    created_at: datetime = field(default_factory=_now)
    updated_at: datetime = field(default_factory=_now)
    reviewed_at: datetime | None = None

    def __post_init__(self) -> None:
        exc = InvalidRestaurantAttributeException
        self.name = require_non_empty(self.name, "name", exc)
        self.description = (self.description or "").strip() or None
        require_non_negative(self.price, "price", exc)
        require_positive(self.serving_g, "serving_g", exc)
        for value, label in (
            (self.kcal, "kcal"), (self.protein_g, "protein_g"),
            (self.carbs_g, "carbs_g"), (self.fat_g, "fat_g"),
        ):
            require_non_negative(value, label, exc)
        if self.fiber_g is not None:
            require_non_negative(self.fiber_g, "fiber_g", exc)
        self.rejection_reason = checked_reason(self.status, self.rejection_reason)

    @classmethod
    def create(
        cls,
        *,
        restaurant_id: UUID,
        name: str,
        price: Decimal,
        serving_g: int,
        kcal: int,
        protein_g: float,
        carbs_g: float,
        fat_g: float,
        fiber_g: float | None = None,
        description: str | None = None,
        image_url: str | None = None,
    ) -> Dish:
        now = _now()
        return cls(
            id=uuid4(), restaurant_id=restaurant_id, name=name, price=price, serving_g=serving_g,
            kcal=kcal, protein_g=protein_g, carbs_g=carbs_g, fat_g=fat_g, fiber_g=fiber_g,
            description=description, image_url=image_url, created_at=now, updated_at=now,
        )

    def review(self, decision: ReviewDecision, reason: str | None, now: datetime) -> None:
        status = ModerationStatus(decision.value)
        self.rejection_reason = checked_reason(status, reason)
        self.status = status
        self.reviewed_at = now

    def mark_edited(self, now: datetime) -> None:
        """Any edit sends the dish back to review; it is hidden until re-approved."""
        self.updated_at = now
        self.status = ModerationStatus.PENDING
        self.rejection_reason = None
```

In `src/domain/entities/user.py`: import `UserRole`, add the field after `weekly_rate_kg`, and add the property next to `is_premium`:

```python
    role: UserRole = UserRole.USER
```

```python
    @property
    def is_admin(self) -> bool:
        return self.role == UserRole.ADMIN
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/unit/test_restaurant_entities.py -q && uv run lint-imports`
Expected: all PASS; `Contracts: 2 kept, 0 broken.`

- [ ] **Step 5: Commit**

```bash
git add src/domain src/adapters/exception_handlers.py tests/unit/test_restaurant_entities.py
git commit -m "feat(restaurants): domain entities, moderation rules and admin role"
```

---

### Task 2: Persistence (ORM, migration 0021, repositories)

**Files:**
- Create: `src/infrastructure/db/models/restaurant_model.py`, `src/infrastructure/db/models/dish_model.py`, `src/application/ports/restaurant_repository.py`, `src/application/ports/admin_stats_repository.py`, `src/application/dtos/restaurant.py`, `src/application/dtos/admin.py`, `src/infrastructure/db/repositories/restaurant_repository.py`, `src/infrastructure/db/repositories/admin_stats_repository.py`, `alembic/versions/0021_restaurants_and_roles.py`
- Modify: `src/infrastructure/db/models/user_model.py`, `src/infrastructure/db/models/__init__.py`, `src/infrastructure/di/repositories.py`, `src/infrastructure/di/__init__.py`
- Test: `tests/integration/test_restaurant_repository.py`

**Interfaces:**
- Consumes: Task 1 entities/enums/exceptions.
- Produces:
  - `RestaurantRepositoryProtocol` (methods below) and `AdminStatsRepositoryProtocol`.
  - DTOs: `RestaurantOutputDTO`, `DishOutputDTO`, `CreateRestaurantInputDTO`, `UpdateRestaurantInputDTO`, `CreateDishInputDTO`, `UpdateDishInputDTO`, `AdminRestaurantRowDTO`, `AdminRestaurantDetailDTO`, `DashboardDayDTO`, `DashboardDTO`.
  - DI aliases `RestaurantRepositoryDep`, `AdminStatsRepositoryDep`.

- [ ] **Step 1: Write the failing integration test**

`tests/integration/test_restaurant_repository.py`, using the same fixture pattern as `test_streak_repository.py`. `tests/conftest.py` forces `TEST_DATABASE_URL` to in-memory SQLite, so it runs without Docker:

```python
"""SQLAlchemyRestaurantRepository against the test database."""

from __future__ import annotations

import os
from decimal import Decimal

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import src.infrastructure.db.models  # noqa: F401 — registers every table
from src.domain.entities.dish import Dish
from src.domain.entities.restaurant import Restaurant
from src.domain.entities.user import User
from src.domain.enums import ModerationStatus, ReviewDecision
from src.domain.exceptions import RestaurantAlreadyExistsException
from src.infrastructure.db.base import Base
from src.infrastructure.db.repositories.restaurant_repository import SQLAlchemyRestaurantRepository
from src.infrastructure.db.repositories.user_repository import SQLAlchemyUserRepository

TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL",
    os.getenv("DATABASE_URL", "postgresql+asyncpg://postgres:postgres@localhost:5433/foodfen_test"),
)


@pytest_asyncio.fixture
async def session():
    engine = create_async_engine(TEST_DATABASE_URL)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    async with async_sessionmaker(engine, expire_on_commit=False)() as s:
        yield s
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


async def _owner(session, email="owner@example.com") -> int:
    user = await SQLAlchemyUserRepository(session).create(User.create(email=email, name="Owner"))
    return user.id


def _restaurant(user_id: int, name: str = "Quán Ngon") -> Restaurant:
    return Restaurant.create(
        user_id=user_id, name=name, address="1 Lê Lợi", phone="0901",
        opening_hours="7-21", latitude=10.7, longitude=106.7,
    )


def _dish(restaurant_id) -> Dish:
    return Dish.create(
        restaurant_id=restaurant_id, name="Phở", price=Decimal("55000"), serving_g=500,
        kcal=450, protein_g=30, carbs_g=55, fat_g=12,
    )


async def test_round_trip_restaurant_and_dish(session):
    repo = SQLAlchemyRestaurantRepository(session)
    restaurant = _restaurant(await _owner(session))
    await repo.add(restaurant)
    dish = _dish(restaurant.id)
    await repo.add_dish(dish)

    loaded = await repo.get_by_owner(restaurant.user_id)
    assert loaded is not None and loaded.id == restaurant.id
    assert [d.id for d in await repo.list_dishes(restaurant.id)] == [dish.id]
    assert (await repo.get_dish(dish.id)).price == Decimal("55000")

    loaded.review(ReviewDecision.APPROVED, None, loaded.updated_at)
    await repo.update(loaded)
    assert (await repo.get_by_id(restaurant.id)).status == ModerationStatus.APPROVED

    await repo.delete_dish(dish.id)
    assert await repo.list_dishes(restaurant.id) == []


async def test_add_duplicate_owner_raises_already_exists(session):
    repo = SQLAlchemyRestaurantRepository(session)
    owner = await _owner(session)
    await repo.add(_restaurant(owner))
    with pytest.raises(RestaurantAlreadyExistsException):
        await repo.add(_restaurant(owner, name="Second"))
```

- [ ] **Step 2: Run it to verify it fails**

Run: `uv run pytest tests/integration/test_restaurant_repository.py -q`
Expected: FAIL with `ModuleNotFoundError: ...restaurant_repository`

- [ ] **Step 3: Implement DTOs and ports**

`src/application/dtos/restaurant.py`:

```python
"""Restaurant / dish DTOs: frozen dataclasses, never Pydantic or ORM."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from src.domain.entities.dish import Dish
from src.domain.entities.restaurant import Restaurant
from src.domain.enums import ModerationStatus


@dataclass(frozen=True)
class RestaurantOutputDTO:
    id: UUID
    name: str
    description: str | None
    address: str
    phone: str
    opening_hours: str
    latitude: float
    longitude: float
    image_url: str | None
    status: ModerationStatus
    rejection_reason: str | None
    created_at: datetime
    updated_at: datetime
    reviewed_at: datetime | None

    @classmethod
    def from_entity(cls, r: Restaurant) -> RestaurantOutputDTO:
        return cls(
            id=r.id, name=r.name, description=r.description, address=r.address, phone=r.phone,
            opening_hours=r.opening_hours, latitude=r.latitude, longitude=r.longitude,
            image_url=r.image_url, status=r.status, rejection_reason=r.rejection_reason,
            created_at=r.created_at, updated_at=r.updated_at, reviewed_at=r.reviewed_at,
        )


@dataclass(frozen=True)
class DishOutputDTO:
    id: UUID
    restaurant_id: UUID
    name: str
    description: str | None
    image_url: str | None
    price: Decimal
    serving_g: int
    kcal: int
    protein_g: float
    carbs_g: float
    fat_g: float
    fiber_g: float | None
    status: ModerationStatus
    rejection_reason: str | None
    created_at: datetime
    updated_at: datetime
    reviewed_at: datetime | None

    @classmethod
    def from_entity(cls, d: Dish) -> DishOutputDTO:
        return cls(
            id=d.id, restaurant_id=d.restaurant_id, name=d.name, description=d.description,
            image_url=d.image_url, price=d.price, serving_g=d.serving_g, kcal=d.kcal,
            protein_g=d.protein_g, carbs_g=d.carbs_g, fat_g=d.fat_g, fiber_g=d.fiber_g,
            status=d.status, rejection_reason=d.rejection_reason, created_at=d.created_at,
            updated_at=d.updated_at, reviewed_at=d.reviewed_at,
        )


@dataclass(frozen=True)
class CreateRestaurantInputDTO:
    user_id: int
    name: str
    address: str
    phone: str
    opening_hours: str
    latitude: float
    longitude: float
    description: str | None = None
    image_url: str | None = None


@dataclass(frozen=True)
class UpdateRestaurantInputDTO:
    user_id: int
    updates: dict[str, Any]  # only the fields the client sent (exclude_unset)


@dataclass(frozen=True)
class CreateDishInputDTO:
    user_id: int
    name: str
    price: Decimal
    serving_g: int
    kcal: int
    protein_g: float
    carbs_g: float
    fat_g: float
    fiber_g: float | None = None
    description: str | None = None
    image_url: str | None = None


@dataclass(frozen=True)
class UpdateDishInputDTO:
    user_id: int
    dish_id: UUID
    updates: dict[str, Any]
```

`src/application/dtos/admin.py`:

```python
"""Admin read models. Frozen dataclasses."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from uuid import UUID

from src.application.dtos.restaurant import DishOutputDTO, RestaurantOutputDTO
from src.domain.enums import ModerationStatus


@dataclass(frozen=True)
class AdminRestaurantRowDTO:
    id: UUID
    name: str
    status: ModerationStatus
    owner_name: str | None
    owner_email: str
    dish_count: int
    pending_dish_count: int
    updated_at: datetime
    rejection_reason: str | None


@dataclass(frozen=True)
class AdminRestaurantDetailDTO:
    restaurant: RestaurantOutputDTO
    dishes: list[DishOutputDTO]


@dataclass(frozen=True)
class DashboardDayDTO:
    date: date
    premium_revenue: int
    ad_revenue: int
    new_users: int
    new_restaurants: int


@dataclass(frozen=True)
class DashboardDTO:
    from_date: date
    to_date: date
    premium_revenue: int
    ad_revenue: int
    new_users: int
    new_restaurants: int
    daily: list[DashboardDayDTO]
```

`src/application/ports/restaurant_repository.py`:

```python
"""Persistence port for restaurants and their dishes (one aggregate)."""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from src.application.dtos.admin import AdminRestaurantRowDTO
from src.domain.entities.dish import Dish
from src.domain.entities.restaurant import Restaurant
from src.domain.enums import ModerationStatus


class RestaurantRepositoryProtocol(Protocol):
    async def add(self, restaurant: Restaurant) -> None:
        """Raise ``RestaurantAlreadyExistsException`` if the owner already has one."""
        ...

    async def get_by_id(self, restaurant_id: UUID) -> Restaurant | None: ...

    async def get_by_owner(self, user_id: int) -> Restaurant | None: ...

    async def update(self, restaurant: Restaurant) -> None: ...

    async def list_for_admin(
        self, needs_review: bool, status: ModerationStatus | None
    ) -> list[AdminRestaurantRowDTO]:
        """Oldest ``updated_at`` first. ``needs_review``: pending restaurants, or approved ones
        with at least one pending dish."""
        ...

    async def add_dish(self, dish: Dish) -> None: ...

    async def get_dish(self, dish_id: UUID) -> Dish | None: ...

    async def update_dish(self, dish: Dish) -> None: ...

    async def delete_dish(self, dish_id: UUID) -> None: ...

    async def list_dishes(self, restaurant_id: UUID) -> list[Dish]:
        """Every status, oldest first."""
        ...
```

`src/application/ports/admin_stats_repository.py`:

```python
"""Raw rows for the admin dashboard; bucketing into days is the use case's job."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Protocol


class AdminStatsRepositoryProtocol(Protocol):
    """All ranges are ``[start, end)`` in aware UTC instants; returned instants are aware."""

    async def paid_payments(self, start: datetime, end: datetime) -> list[tuple[datetime, Decimal]]:
        """``(paid_at, amount)`` of payments with status ``paid``, by ``paid_at``."""
        ...

    async def user_signups(self, start: datetime, end: datetime) -> list[datetime]: ...

    async def restaurant_signups(self, start: datetime, end: datetime) -> list[datetime]: ...
```

- [ ] **Step 4: Implement ORM models**

`src/infrastructure/db/models/restaurant_model.py`:

```python
"""ORM model for restaurants. Separate from the domain entity; explicit mapping."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from src.domain.entities.restaurant import Restaurant
from src.domain.enums import ModerationStatus
from src.infrastructure.db.base import Base
from src.infrastructure.db.mixins import UserOwned, UUIDPrimaryKey
from src.infrastructure.db.types import enum_column


class RestaurantORM(UUIDPrimaryKey, UserOwned, Base):
    __tablename__ = "restaurants"
    # One restaurant per owner: also what turns a concurrent second create into a 409.
    __table_args__ = (UniqueConstraint("user_id", name="uq_restaurants_user_id"),)

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    address: Mapped[str] = mapped_column(String(500), nullable=False)
    phone: Mapped[str] = mapped_column(String(32), nullable=False)
    opening_hours: Mapped[str] = mapped_column(String(255), nullable=False)
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    image_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    status: Mapped[ModerationStatus] = mapped_column(
        enum_column(ModerationStatus, "moderation_status"), nullable=False, index=True
    )
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    def to_domain(self) -> Restaurant:
        return Restaurant(
            id=self.id, user_id=self.user_id, name=self.name, description=self.description,
            address=self.address, phone=self.phone, opening_hours=self.opening_hours,
            latitude=self.latitude, longitude=self.longitude, image_url=self.image_url,
            status=self.status, rejection_reason=self.rejection_reason,
            created_at=self.created_at, updated_at=self.updated_at, reviewed_at=self.reviewed_at,
        )

    @staticmethod
    def from_domain(r: Restaurant) -> RestaurantORM:
        return RestaurantORM(
            id=r.id, user_id=r.user_id, name=r.name, description=r.description,
            address=r.address, phone=r.phone, opening_hours=r.opening_hours,
            latitude=r.latitude, longitude=r.longitude, image_url=r.image_url,
            status=r.status, rejection_reason=r.rejection_reason,
            created_at=r.created_at, updated_at=r.updated_at, reviewed_at=r.reviewed_at,
        )
```

`src/infrastructure/db/models/dish_model.py`:

```python
"""ORM model for dishes. Nutrition columns are typed exactly like food_entries."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import DateTime, Float, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from src.domain.entities.dish import Dish
from src.domain.enums import ModerationStatus
from src.infrastructure.db.base import Base
from src.infrastructure.db.mixins import UUIDPrimaryKey
from src.infrastructure.db.types import enum_column


class DishORM(UUIDPrimaryKey, Base):
    __tablename__ = "dishes"

    restaurant_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("restaurants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    image_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    price: Mapped[Decimal] = mapped_column(Numeric(12, 0), nullable=False)  # VND
    serving_g: Mapped[int] = mapped_column(Integer, nullable=False)
    kcal: Mapped[int] = mapped_column(Integer, nullable=False)
    protein_g: Mapped[float] = mapped_column(Float, nullable=False)
    carbs_g: Mapped[float] = mapped_column(Float, nullable=False)
    fat_g: Mapped[float] = mapped_column(Float, nullable=False)
    fiber_g: Mapped[float | None] = mapped_column(Float, nullable=True)
    status: Mapped[ModerationStatus] = mapped_column(
        enum_column(ModerationStatus, "moderation_status"), nullable=False, index=True
    )
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    def to_domain(self) -> Dish:
        return Dish(
            id=self.id, restaurant_id=self.restaurant_id, name=self.name,
            description=self.description, image_url=self.image_url, price=self.price,
            serving_g=self.serving_g, kcal=self.kcal, protein_g=self.protein_g,
            carbs_g=self.carbs_g, fat_g=self.fat_g, fiber_g=self.fiber_g, status=self.status,
            rejection_reason=self.rejection_reason, created_at=self.created_at,
            updated_at=self.updated_at, reviewed_at=self.reviewed_at,
        )

    @staticmethod
    def from_domain(d: Dish) -> DishORM:
        return DishORM(
            id=d.id, restaurant_id=d.restaurant_id, name=d.name, description=d.description,
            image_url=d.image_url, price=d.price, serving_g=d.serving_g, kcal=d.kcal,
            protein_g=d.protein_g, carbs_g=d.carbs_g, fat_g=d.fat_g, fiber_g=d.fiber_g,
            status=d.status, rejection_reason=d.rejection_reason, created_at=d.created_at,
            updated_at=d.updated_at, reviewed_at=d.reviewed_at,
        )
```

In `src/infrastructure/db/models/user_model.py`: import `UserRole`, add the column after `weekly_rate_kg`, and map it in both directions (`role=self.role` in `to_domain`, `role=user.role` in `from_domain`):

```python
    role: Mapped[UserRole] = mapped_column(
        enum_column(UserRole, "user_role"), nullable=False, server_default=UserRole.USER.value
    )
```

In `src/infrastructure/db/models/__init__.py` add `DishORM` and `RestaurantORM` to the imports and to `__all__` (alphabetical).

- [ ] **Step 5: Implement repositories**

`src/infrastructure/db/repositories/restaurant_repository.py`:

```python
"""Concrete ``RestaurantRepositoryProtocol`` backed by async SQLAlchemy."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import and_, case, delete, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.application.dtos.admin import AdminRestaurantRowDTO
from src.domain.entities.dish import Dish
from src.domain.entities.restaurant import Restaurant
from src.domain.enums import ModerationStatus
from src.domain.exceptions import RestaurantAlreadyExistsException
from src.infrastructure.db.models.dish_model import DishORM
from src.infrastructure.db.models.restaurant_model import RestaurantORM
from src.infrastructure.db.models.user_model import UserORM


class SQLAlchemyRestaurantRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, restaurant: Restaurant) -> None:
        try:
            # Savepoint, as in idempotency.py: keeps the request's transaction usable on failure.
            async with self._session.begin_nested():
                self._session.add(RestaurantORM.from_domain(restaurant))
                await self._session.flush()
        except IntegrityError as exc:  # uq_restaurants_user_id: a concurrent second create
            raise RestaurantAlreadyExistsException("you already have a restaurant") from exc

    async def get_by_id(self, restaurant_id: UUID) -> Restaurant | None:
        row = await self._session.get(RestaurantORM, restaurant_id)
        return row.to_domain() if row else None

    async def get_by_owner(self, user_id: int) -> Restaurant | None:
        row = (
            await self._session.execute(select(RestaurantORM).where(RestaurantORM.user_id == user_id))
        ).scalar_one_or_none()
        return row.to_domain() if row else None

    async def update(self, restaurant: Restaurant) -> None:
        await self._session.merge(RestaurantORM.from_domain(restaurant))
        await self._session.flush()

    async def list_for_admin(
        self, needs_review: bool, status: ModerationStatus | None
    ) -> list[AdminRestaurantRowDTO]:
        dish_count = func.count(DishORM.id)
        pending_count = func.coalesce(
            func.sum(case((DishORM.status == ModerationStatus.PENDING, 1), else_=0)), 0
        )
        stmt = (
            select(
                RestaurantORM,
                UserORM.name,
                UserORM.email,
                dish_count.label("dish_count"),
                pending_count.label("pending_dish_count"),
            )
            .join(UserORM, UserORM.id == RestaurantORM.user_id)
            .outerjoin(DishORM, DishORM.restaurant_id == RestaurantORM.id)
            .group_by(RestaurantORM.id, UserORM.id)
            .order_by(RestaurantORM.updated_at)
        )
        if status is not None:
            stmt = stmt.where(RestaurantORM.status == status)
        if needs_review:
            stmt = stmt.having(
                or_(
                    RestaurantORM.status == ModerationStatus.PENDING,
                    and_(RestaurantORM.status == ModerationStatus.APPROVED, pending_count > 0),
                )
            )
        rows = (await self._session.execute(stmt)).all()
        return [
            AdminRestaurantRowDTO(
                id=r.id, name=r.name, status=r.status, owner_name=owner_name,
                owner_email=owner_email, dish_count=int(dishes), pending_dish_count=int(pending),
                updated_at=r.updated_at, rejection_reason=r.rejection_reason,
            )
            for r, owner_name, owner_email, dishes, pending in rows
        ]

    async def add_dish(self, dish: Dish) -> None:
        self._session.add(DishORM.from_domain(dish))
        await self._session.flush()

    async def get_dish(self, dish_id: UUID) -> Dish | None:
        row = await self._session.get(DishORM, dish_id)
        return row.to_domain() if row else None

    async def update_dish(self, dish: Dish) -> None:
        await self._session.merge(DishORM.from_domain(dish))
        await self._session.flush()

    async def delete_dish(self, dish_id: UUID) -> None:
        await self._session.execute(delete(DishORM).where(DishORM.id == dish_id))

    async def list_dishes(self, restaurant_id: UUID) -> list[Dish]:
        rows = (
            await self._session.execute(
                select(DishORM)
                .where(DishORM.restaurant_id == restaurant_id)
                .order_by(DishORM.created_at, DishORM.id)
            )
        ).scalars().all()
        return [row.to_domain() for row in rows]
```

`src/infrastructure/db/repositories/admin_stats_repository.py`:

```python
"""Concrete ``AdminStatsRepositoryProtocol``: three plain range selects."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.enums import PaymentStatus
from src.infrastructure.db.models.payment_model import PaymentORM
from src.infrastructure.db.models.restaurant_model import RestaurantORM
from src.infrastructure.db.models.user_model import UserORM


class SQLAlchemyAdminStatsRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def paid_payments(self, start: datetime, end: datetime) -> list[tuple[datetime, Decimal]]:
        rows = await self._session.execute(
            select(PaymentORM.paid_at, PaymentORM.amount).where(
                PaymentORM.status == PaymentStatus.PAID,
                PaymentORM.paid_at >= start,
                PaymentORM.paid_at < end,
            )
        )
        return [(paid_at, amount) for paid_at, amount in rows.all()]

    async def user_signups(self, start: datetime, end: datetime) -> list[datetime]:
        return list(
            (await self._session.execute(
                select(UserORM.created_at).where(UserORM.created_at >= start, UserORM.created_at < end)
            )).scalars()
        )

    async def restaurant_signups(self, start: datetime, end: datetime) -> list[datetime]:
        return list(
            (await self._session.execute(
                select(RestaurantORM.created_at).where(
                    RestaurantORM.created_at >= start, RestaurantORM.created_at < end
                )
            )).scalars()
        )
```

In `src/infrastructure/di/repositories.py` add (imports + providers), and re-export the four names from `src/infrastructure/di/__init__.py` (imports and `__all__`):

```python
def get_restaurant_repository(session: SessionDep) -> RestaurantRepositoryProtocol:
    return SQLAlchemyRestaurantRepository(session)


RestaurantRepositoryDep = Annotated[
    RestaurantRepositoryProtocol, Depends(get_restaurant_repository)
]


def get_admin_stats_repository(session: SessionDep) -> AdminStatsRepositoryProtocol:
    return SQLAlchemyAdminStatsRepository(session)


AdminStatsRepositoryDep = Annotated[
    AdminStatsRepositoryProtocol, Depends(get_admin_stats_repository)
]
```

- [ ] **Step 6: Write migration 0021**

`alembic/versions/0021_restaurants_and_roles.py`:

```python
"""users.role, restaurants, dishes

Revision ID: 0021
Revises: 0020
Create Date: 2026-10-08
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0021"
down_revision: str | None = "0020"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_MODERATION = "status IN ('pending', 'approved', 'rejected')"


def _moderation_columns() -> list[sa.Column]:
    return [
        sa.Column("status", sa.String(length=8), nullable=False),
        sa.Column("rejection_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
    ]


def upgrade() -> None:
    op.add_column(
        "users", sa.Column("role", sa.String(length=5), server_default="user", nullable=False)
    )
    op.create_check_constraint("user_role", "users", "role IN ('user', 'admin')")

    op.create_table(
        "restaurants",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("address", sa.String(length=500), nullable=False),
        sa.Column("phone", sa.String(length=32), nullable=False),
        sa.Column("opening_hours", sa.String(length=255), nullable=False),
        sa.Column("latitude", sa.Float(), nullable=False),
        sa.Column("longitude", sa.Float(), nullable=False),
        sa.Column("image_url", sa.String(length=2048), nullable=True),
        *_moderation_columns(),
        sa.PrimaryKeyConstraint("id", name="pk_restaurants"),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_restaurants_user_id_users", ondelete="CASCADE"
        ),
        sa.UniqueConstraint("user_id", name="uq_restaurants_user_id"),
        sa.CheckConstraint(_MODERATION, name="moderation_status"),
    )
    op.create_index("ix_restaurants_status", "restaurants", ["status"])

    op.create_table(
        "dishes",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("restaurant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("image_url", sa.String(length=2048), nullable=True),
        sa.Column("price", sa.Numeric(precision=12, scale=0), nullable=False),
        sa.Column("serving_g", sa.Integer(), nullable=False),
        sa.Column("kcal", sa.Integer(), nullable=False),
        sa.Column("protein_g", sa.Float(), nullable=False),
        sa.Column("carbs_g", sa.Float(), nullable=False),
        sa.Column("fat_g", sa.Float(), nullable=False),
        sa.Column("fiber_g", sa.Float(), nullable=True),
        *_moderation_columns(),
        sa.PrimaryKeyConstraint("id", name="pk_dishes"),
        sa.ForeignKeyConstraint(
            ["restaurant_id"],
            ["restaurants.id"],
            name="fk_dishes_restaurant_id_restaurants",
            ondelete="CASCADE",
        ),
        sa.CheckConstraint(_MODERATION, name="moderation_status"),
    )
    op.create_index("ix_dishes_restaurant_id", "dishes", ["restaurant_id"])
    op.create_index("ix_dishes_status", "dishes", ["status"])


def downgrade() -> None:
    op.drop_index("ix_dishes_status", table_name="dishes")
    op.drop_index("ix_dishes_restaurant_id", table_name="dishes")
    op.drop_table("dishes")
    op.drop_index("ix_restaurants_status", table_name="restaurants")
    op.drop_table("restaurants")
    op.drop_constraint("user_role", "users", type_="check")
    op.drop_column("users", "role")
```

- [ ] **Step 7: Verify the migration matches the models** (CLAUDE.md rule)

Run:

```bash
uv run alembic upgrade 0020:0021 --sql > "$TMPDIR/0021.sql"
uv run python -c "import src.infrastructure.db.models; from sqlalchemy.schema import CreateTable, CreateIndex; from sqlalchemy.dialects import postgresql; from src.infrastructure.db.base import Base; d=postgresql.dialect(); [print(CreateTable(Base.metadata.tables[t]).compile(dialect=d)) or [print(CreateIndex(i).compile(dialect=d)) for i in Base.metadata.tables[t].indexes] for t in ('restaurants','dishes')]; print([c.name for c in Base.metadata.tables['users'].constraints])"
uv run alembic downgrade 0021:0020 --sql > /dev/null
```

Expected: column names, types, nullability, `ck_restaurants_moderation_status` / `ck_dishes_moderation_status`, `ck_users_user_role`, `uq_restaurants_user_id`, FK and index names match between the two outputs (column *order* may differ only where mixins sort first). Fix the migration on any mismatch.

- [ ] **Step 8: Run tests**

Run: `uv run pytest tests/integration/test_restaurant_repository.py -q && make test && uv run lint-imports`
Expected: all PASS (existing suites unaffected; `users.role` defaults to `user`).

- [ ] **Step 9: Commit**

```bash
git add src alembic/versions/0021_restaurants_and_roles.py tests/integration/test_restaurant_repository.py
git commit -m "feat(restaurants): tables, migration 0021 and repositories"
```

---

### Task 3: Role on the wire, admin guard, `/auth/me` restaurantId

**Files:**
- Create: `src/application/use_cases/get_me.py`, `tests/api/test_admin_endpoints.py` (first tests only)
- Modify: `src/application/dtos/user.py`, `src/adapters/schemas/user_schemas.py`, `src/adapters/controllers/auth_controller.py`, `src/infrastructure/di/security.py`, `src/infrastructure/di/use_cases.py`, `src/infrastructure/di/__init__.py`, `tests/api/conftest.py`

**Interfaces:**
- Consumes: `RestaurantRepositoryDep`, `User.is_admin`, `AdminRequiredException`.
- Produces:
  - DTOs: `UserOutputDTO.role`, `MeOutputDTO(user: UserOutputDTO, restaurant_id: UUID | None)`.
  - Use case: `GetMeUseCase.execute(user: User) -> MeOutputDTO` with `GetMeUseCaseDep`.
  - Guards: `get_current_admin`, `CurrentAdminDep`, `limit_upload_by_user`.
  - Schema: `MeResponse`.
  - Test fixtures: `make_user`, `set_role`, `restaurant_body`, `dish_body`.

- [ ] **Step 1: Add test fixtures to `tests/api/conftest.py`**

Add the imports `from sqlalchemy import update`, `from src.domain.enums import UserRole`, `from src.infrastructure.db.models.user_model import UserORM`, `from src.infrastructure.db.session import SessionLocal`, then:

```python
async def _set_role(user_id: int, role: UserRole) -> None:
    async with SessionLocal() as session:
        await session.execute(update(UserORM).where(UserORM.id == user_id).values(role=role))
        await session.commit()


@pytest_asyncio.fixture
def set_role():
    return _set_role


@pytest_asyncio.fixture
def make_user(client):
    """Sign up a fresh user; returns ``(auth headers, user id)``. ``admin=True`` promotes it with SQL,
    exactly as production does."""

    async def _make(email: str, *, admin: bool = False) -> tuple[dict[str, str], int]:
        resp = await client.post(
            "/auth/sign-up", json={"email": email, "password": "s3cret-pass", "displayName": "U"}
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        if admin:
            await _set_role(body["user"]["id"], UserRole.ADMIN)
        return {"Authorization": f"Bearer {body['accessToken']}"}, body["user"]["id"]

    return _make


@pytest_asyncio.fixture
def restaurant_body() -> dict:
    return {
        "name": "Quán Ngon", "address": "1 Lê Lợi, Q1", "phone": "0901234567",
        "openingHours": "7:00-21:00", "latitude": 10.7769, "longitude": 106.7009,
    }


@pytest_asyncio.fixture
def dish_body() -> dict:
    return {
        "name": "Phở bò", "price": 55000, "servingG": 500,
        "kcal": 450, "proteinG": 30, "carbsG": 55, "fatG": 12,
    }
```

- [ ] **Step 2: Write the failing tests**

`tests/api/test_admin_endpoints.py`:

```python
"""Admin guard, moderation and dashboard. End-to-end against the real app + SQLite."""

from __future__ import annotations

from src.domain.enums import UserRole


async def test_me_carries_role_and_null_restaurant(client, make_user):
    headers, _ = await make_user("plain@example.com")
    me = (await client.get("/auth/me", headers=headers)).json()
    assert me["role"] == "user"
    assert me["restaurantId"] is None


async def test_sign_in_session_carries_role(client, make_user):
    await make_user("boss@example.com", admin=True)
    resp = await client.post("/auth/sign-in", json={"email": "boss@example.com", "password": "s3cret-pass"})
    assert resp.json()["user"]["role"] == "admin"


async def test_non_admin_is_forbidden(client, make_user):
    headers, _ = await make_user("plain@example.com")
    resp = await client.get("/admin/restaurants", headers=headers)
    assert resp.status_code == 403
    assert "message" in resp.json()


async def test_admin_routes_need_a_token(client):
    assert (await client.get("/admin/restaurants")).status_code == 401


async def test_demoted_admin_is_forbidden_immediately(client, make_user, set_role):
    headers, user_id = await make_user("boss@example.com", admin=True)
    assert (await client.get("/admin/restaurants", headers=headers)).status_code == 200
    await set_role(user_id, UserRole.USER)
    assert (await client.get("/admin/restaurants", headers=headers)).status_code == 403
```

- [ ] **Step 3: Run to verify failure**

Run: `uv run pytest tests/api/test_admin_endpoints.py -q`
Expected: FAIL (`KeyError: 'role'`, and 404 on `/admin/restaurants`). Step 4 registers a stub admin router so the guard is testable now; Task 6 replaces the stub.

- [ ] **Step 4: Implement**

`src/application/dtos/user.py`: import `UserRole` and `UUID`; add `role: UserRole` to `UserOutputDTO` (after `subscription_tier`), set `role=user.role` in `from_entity`, and add:

```python
@dataclass(frozen=True)
class MeOutputDTO:
    user: UserOutputDTO
    restaurant_id: UUID | None
```

`src/application/use_cases/get_me.py`:

```python
"""Use case: the signed-in user plus the id of the restaurant they own, if any."""

from __future__ import annotations

from dataclasses import dataclass

from src.application.dtos.user import MeOutputDTO, UserOutputDTO
from src.application.ports.restaurant_repository import RestaurantRepositoryProtocol
from src.domain.entities.user import User


@dataclass
class GetMeUseCase:
    restaurants: RestaurantRepositoryProtocol

    async def execute(self, user: User) -> MeOutputDTO:
        restaurant = await self.restaurants.get_by_owner(user.id)
        return MeOutputDTO(
            user=UserOutputDTO.from_entity(user),
            restaurant_id=restaurant.id if restaurant else None,
        )
```

`src/adapters/schemas/user_schemas.py`: import `UserRole`, `UUID`, `MeOutputDTO`; add `role: UserRole` to `UserResponse` (after `subscription_tier`) and `role=dto.role` in `from_dto`; add:

```python
class MeResponse(UserResponse):
    """``GET /auth/me`` only: ``restaurantId`` costs a lookup the session payloads don't need."""

    restaurant_id: UUID | None

    @classmethod
    def from_me(cls, dto: MeOutputDTO) -> MeResponse:
        return cls(**UserResponse.from_dto(dto.user).model_dump(), restaurant_id=dto.restaurant_id)
```

`src/adapters/controllers/auth_controller.py`, replace the `me` handler (keep its existing decorator path, change `response_model`):

```python
@router.get("/me", response_model=MeResponse)
async def me(current_user: CurrentUserDep, use_case: GetMeUseCaseDep) -> MeResponse:
    return MeResponse.from_me(await use_case.execute(current_user))
```

`src/infrastructure/di/security.py`: import `AdminRequiredException`; after `CurrentUserDep` add:

```python
async def get_current_admin(user: CurrentUserDep) -> User:
    """Role is read from the user row loaded per request, never from the JWT: promoting or
    demoting an admin with SQL takes effect on the next request."""
    if not user.is_admin:
        raise AdminRequiredException("admin access required")
    return user


CurrentAdminDep = Annotated[User, Depends(get_current_admin)]
```

and next to the other limiters:

```python
_upload_user_limiter = SlidingWindowLimiter(limit=20, window_seconds=60)  # Cloudinary costs money


async def limit_upload_by_user(user: CurrentUserDep) -> None:
    _enforce(_upload_user_limiter, str(user.id))
```

`src/infrastructure/di/use_cases.py`:

```python
def get_get_me_use_case(restaurants: RestaurantRepositoryDep) -> GetMeUseCase:
    return GetMeUseCase(restaurants=restaurants)


GetMeUseCaseDep = Annotated[GetMeUseCase, Depends(get_get_me_use_case)]
```

Re-export `GetMeUseCaseDep`, `get_get_me_use_case`, `CurrentAdminDep`, `get_current_admin`, `limit_upload_by_user` from `src/infrastructure/di/__init__.py`.

Create `src/adapters/controllers/admin_controller.py` with the router only (Task 6 fills it) and register it in `src/main.py` (`app.include_router(admin_router)`):

```python
"""Admin endpoints: moderation and dashboard. HTTP <-> DTO translation only.

Every route is admin-only via the router-level dependency.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from src.infrastructure.di import get_current_admin

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(get_current_admin)])


@router.get("/restaurants")
async def list_restaurants() -> list:
    return []  # replaced in Task 6
```

- [ ] **Step 5: Run tests**

Run: `uv run pytest tests/api/test_admin_endpoints.py tests/api/test_auth_endpoints.py tests/api/test_social_sign_in_endpoint.py -q && uv run lint-imports`
Expected: PASS. If an existing auth test compares the full `user` dict exactly, add `"role": "user"` to its expected value (that is the contract change, not a regression).

- [ ] **Step 6: Commit**

```bash
git add src tests/api
git commit -m "feat(auth): user role on the wire, admin guard, restaurantId on /auth/me"
```

---

### Task 4: Owner restaurant endpoints + image upload

**Files:**
- Create: `src/application/use_cases/restaurant_support.py`, `create_restaurant.py`, `get_my_restaurant.py`, `update_my_restaurant.py`, `upload_restaurant_image.py` (all in `src/application/use_cases/`), `src/adapters/schemas/restaurant_schemas.py`, `src/adapters/controllers/restaurant_controller.py`, `tests/api/test_restaurant_endpoints.py`
- Modify: `src/infrastructure/di/use_cases.py`, `src/infrastructure/di/__init__.py`, `src/main.py`

**Interfaces:**
- Consumes: Task 2 DTOs/port, Task 3 `make_user`, `restaurant_body`, `limit_upload_by_user`, `ImageStorageDep`.
- Produces:
  - Helpers: `owned_restaurant(restaurants, user_id) -> Restaurant`, `owned_dish(restaurants, user_id, dish_id) -> Dish`.
  - Schemas: `RestaurantResponse.from_dto`, `DishResponse.from_dto` (used by Task 5/6).
  - Routes: `POST /restaurants`, `GET|PATCH /restaurants/mine`, `POST /restaurants/mine/images`.

- [ ] **Step 1: Write the failing tests**

`tests/api/test_restaurant_endpoints.py`:

```python
"""Owner endpoints: restaurant profile, dishes, image upload."""

from __future__ import annotations


async def _admin(make_user):
    headers, _ = await make_user("admin@example.com", admin=True)
    return headers


async def _create(client, make_user, restaurant_body, email="owner@example.com"):
    headers, _ = await make_user(email)
    resp = await client.post("/restaurants", json=restaurant_body, headers=headers)
    assert resp.status_code == 201, resp.text
    return headers, resp.json()


async def test_create_returns_pending_restaurant_and_me_links_it(client, make_user, restaurant_body):
    headers, body = await _create(client, make_user, restaurant_body)
    assert body["status"] == "pending" and body["rejectionReason"] is None
    assert body["openingHours"] == "7:00-21:00" and body["latitude"] == 10.7769
    me = (await client.get("/auth/me", headers=headers)).json()
    assert me["restaurantId"] == body["id"]


async def test_second_restaurant_is_409(client, make_user, restaurant_body):
    headers, _ = await _create(client, make_user, restaurant_body)
    assert (await client.post("/restaurants", json=restaurant_body, headers=headers)).status_code == 409


async def test_get_mine_without_restaurant_is_404(client, make_user):
    headers, _ = await make_user("nobody@example.com")
    assert (await client.get("/restaurants/mine", headers=headers)).status_code == 404


async def test_latitude_out_of_range_is_a_field_error(client, make_user, restaurant_body):
    headers, _ = await make_user("owner@example.com")
    resp = await client.post("/restaurants", json={**restaurant_body, "latitude": 91}, headers=headers)
    assert resp.status_code == 422
    assert "latitude" in resp.json()["errors"]


async def test_patch_null_required_field_is_422(client, make_user, restaurant_body):
    headers, _ = await _create(client, make_user, restaurant_body)
    resp = await client.patch("/restaurants/mine", json={"name": None, "latitude": None}, headers=headers)
    assert resp.status_code == 422
    assert {"name", "latitude"} <= set(resp.json()["errors"])
    assert (await client.get("/restaurants/mine", headers=headers)).json()["name"] == "Quán Ngon"


async def test_editing_approved_restaurant_stays_live(client, make_user, restaurant_body):
    headers, body = await _create(client, make_user, restaurant_body)
    admin = await _admin(make_user)
    await client.post(f"/admin/restaurants/{body['id']}/review", json={"decision": "approved"}, headers=admin)
    resp = await client.patch("/restaurants/mine", json={"phone": "0911111111"}, headers=headers)
    assert resp.status_code == 200
    assert (resp.json()["phone"], resp.json()["status"]) == ("0911111111", "approved")


async def test_editing_rejected_restaurant_resubmits_it(client, make_user, restaurant_body):
    headers, body = await _create(client, make_user, restaurant_body)
    admin = await _admin(make_user)
    await client.post(
        f"/admin/restaurants/{body['id']}/review",
        json={"decision": "rejected", "reason": "need a real address"}, headers=admin,
    )
    mine = (await client.get("/restaurants/mine", headers=headers)).json()
    assert (mine["status"], mine["rejectionReason"]) == ("rejected", "need a real address")
    resp = await client.patch("/restaurants/mine", json={"address": "2 Lê Lợi"}, headers=headers)
    assert (resp.json()["status"], resp.json()["rejectionReason"]) == ("pending", None)


async def test_image_upload(client, make_user, image_storage):
    headers, _ = await make_user("owner@example.com")
    ok = await client.post(
        "/restaurants/mine/images", files={"image": ("a.webp", b"x" * 10, "image/webp")}, headers=headers
    )
    assert ok.status_code == 200 and ok.json() == {"url": image_storage.url}
    heic = await client.post(
        "/restaurants/mine/images", files={"image": ("a.heic", b"x", "image/heic")}, headers=headers
    )
    assert heic.status_code == 400 and "message" in heic.json()
    big = await client.post(
        "/restaurants/mine/images",
        files={"image": ("a.jpg", b"x" * (5 * 1024 * 1024 + 1), "image/jpeg")}, headers=headers,
    )
    assert big.status_code == 400
```

(The two tests that call `/admin/.../review` stay red until Task 6. Mark them with `@pytest.mark.skip(reason="needs Task 6")` now and remove the marks in Task 6 Step 4.)

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/api/test_restaurant_endpoints.py -q`
Expected: FAIL with 404 on `POST /restaurants`.

- [ ] **Step 3: Implement use cases**

`src/application/use_cases/restaurant_support.py`:

```python
"""Ownership resolution shared by the owner use cases. A user owns at most one restaurant,
so "mine" needs no id: ownership is implied, and someone else's dish is simply not found."""

from __future__ import annotations

from uuid import UUID

from src.application.ports.restaurant_repository import RestaurantRepositoryProtocol
from src.domain.entities.dish import Dish
from src.domain.entities.restaurant import Restaurant
from src.domain.exceptions import DishNotFoundException, RestaurantNotFoundException


async def owned_restaurant(restaurants: RestaurantRepositoryProtocol, user_id: int) -> Restaurant:
    restaurant = await restaurants.get_by_owner(user_id)
    if restaurant is None:
        raise RestaurantNotFoundException("you have no restaurant yet")
    return restaurant


async def owned_dish(
    restaurants: RestaurantRepositoryProtocol, user_id: int, dish_id: UUID
) -> Dish:
    restaurant = await owned_restaurant(restaurants, user_id)
    dish = await restaurants.get_dish(dish_id)
    if dish is None or dish.restaurant_id != restaurant.id:
        raise DishNotFoundException(f"dish {dish_id} not found")  # 404, never 403: no existence leak
    return dish
```

`src/application/use_cases/create_restaurant.py`:

```python
"""Use case: a user registers their (single) restaurant. It starts pending."""

from __future__ import annotations

from dataclasses import asdict, dataclass

from src.application.dtos.restaurant import CreateRestaurantInputDTO, RestaurantOutputDTO
from src.application.ports.restaurant_repository import RestaurantRepositoryProtocol
from src.domain.entities.restaurant import Restaurant
from src.domain.exceptions import RestaurantAlreadyExistsException


@dataclass
class CreateRestaurantUseCase:
    restaurants: RestaurantRepositoryProtocol

    async def execute(self, data: CreateRestaurantInputDTO) -> RestaurantOutputDTO:
        if await self.restaurants.get_by_owner(data.user_id) is not None:
            raise RestaurantAlreadyExistsException("you already have a restaurant")
        restaurant = Restaurant.create(**asdict(data))
        await self.restaurants.add(restaurant)  # also raises on a concurrent duplicate
        return RestaurantOutputDTO.from_entity(restaurant)
```

`src/application/use_cases/get_my_restaurant.py`:

```python
"""Use case: the caller's restaurant, with its moderation status."""

from __future__ import annotations

from dataclasses import dataclass

from src.application.dtos.restaurant import RestaurantOutputDTO
from src.application.ports.restaurant_repository import RestaurantRepositoryProtocol
from src.application.use_cases.restaurant_support import owned_restaurant


@dataclass
class GetMyRestaurantUseCase:
    restaurants: RestaurantRepositoryProtocol

    async def execute(self, user_id: int) -> RestaurantOutputDTO:
        return RestaurantOutputDTO.from_entity(await owned_restaurant(self.restaurants, user_id))
```

`src/application/use_cases/update_my_restaurant.py`:

```python
"""Use case: partial profile edit. Approved stays live; rejected is resubmitted (see entity)."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import UTC, datetime

from src.application.dtos.restaurant import RestaurantOutputDTO, UpdateRestaurantInputDTO
from src.application.ports.restaurant_repository import RestaurantRepositoryProtocol
from src.application.use_cases.restaurant_support import owned_restaurant


@dataclass
class UpdateMyRestaurantUseCase:
    restaurants: RestaurantRepositoryProtocol

    async def execute(self, data: UpdateRestaurantInputDTO) -> RestaurantOutputDTO:
        current = await owned_restaurant(self.restaurants, data.user_id)
        restaurant = replace(current, **data.updates)  # re-runs __post_init__: invariants re-checked
        restaurant.mark_edited(datetime.now(UTC))
        await self.restaurants.update(restaurant)
        return RestaurantOutputDTO.from_entity(restaurant)
```

`src/application/use_cases/upload_restaurant_image.py`:

```python
"""Use case: store a restaurant or dish photo; returns its absolute URL."""

from __future__ import annotations

from dataclasses import dataclass

from src.application.ports.image_storage import ImageStorageProtocol


@dataclass
class UploadRestaurantImageUseCase:
    images: ImageStorageProtocol

    async def execute(self, data: bytes, content_type: str) -> str:
        return await self.images.upload(data, content_type)
```

DI (`src/infrastructure/di/use_cases.py`) plus re-exports in `di/__init__.py`:

```python
def get_create_restaurant_use_case(restaurants: RestaurantRepositoryDep) -> CreateRestaurantUseCase:
    return CreateRestaurantUseCase(restaurants=restaurants)


CreateRestaurantUseCaseDep = Annotated[CreateRestaurantUseCase, Depends(get_create_restaurant_use_case)]


def get_get_my_restaurant_use_case(restaurants: RestaurantRepositoryDep) -> GetMyRestaurantUseCase:
    return GetMyRestaurantUseCase(restaurants=restaurants)


GetMyRestaurantUseCaseDep = Annotated[GetMyRestaurantUseCase, Depends(get_get_my_restaurant_use_case)]


def get_update_my_restaurant_use_case(
    restaurants: RestaurantRepositoryDep,
) -> UpdateMyRestaurantUseCase:
    return UpdateMyRestaurantUseCase(restaurants=restaurants)


UpdateMyRestaurantUseCaseDep = Annotated[
    UpdateMyRestaurantUseCase, Depends(get_update_my_restaurant_use_case)
]


def get_upload_restaurant_image_use_case(images: ImageStorageDep) -> UploadRestaurantImageUseCase:
    return UploadRestaurantImageUseCase(images=images)


UploadRestaurantImageUseCaseDep = Annotated[
    UploadRestaurantImageUseCase, Depends(get_upload_restaurant_image_use_case)
]
```

- [ ] **Step 4: Implement schemas**

`src/adapters/schemas/restaurant_schemas.py`:

```python
"""HTTP wire models for owner restaurant / dish endpoints (camelCase)."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import Field, field_validator

from src.adapters.schemas.base import CamelModel, MoneyField
from src.application.dtos.restaurant import DishOutputDTO, RestaurantOutputDTO
from src.domain.enums import ModerationStatus

_HTTPS = r"^https://"


def _not_null(value):
    """PATCH fields are optional but a *sent* ``null`` on a required one is a field error (422),
    never a 500 from the entity. Field validators only run for fields the client sent."""
    if value is None:
        raise ValueError("cannot be null")
    return value


class RestaurantResponse(CamelModel):
    id: UUID
    name: str
    description: str | None
    address: str
    phone: str
    opening_hours: str
    latitude: float
    longitude: float
    image_url: str | None
    status: ModerationStatus
    rejection_reason: str | None
    created_at: datetime
    updated_at: datetime
    reviewed_at: datetime | None

    @classmethod
    def from_dto(cls, dto: RestaurantOutputDTO) -> RestaurantResponse:
        return cls(**vars(dto))


class DishResponse(CamelModel):
    id: UUID
    restaurant_id: UUID
    name: str
    description: str | None
    image_url: str | None
    price: MoneyField
    serving_g: int
    kcal: int
    protein_g: float
    carbs_g: float
    fat_g: float
    fiber_g: float | None
    status: ModerationStatus
    rejection_reason: str | None
    created_at: datetime
    updated_at: datetime
    reviewed_at: datetime | None

    @classmethod
    def from_dto(cls, dto: DishOutputDTO) -> DishResponse:
        return cls(**vars(dto))


class CreateRestaurantRequest(CamelModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=2000)
    address: str = Field(min_length=1, max_length=500)
    phone: str = Field(min_length=1, max_length=32)
    opening_hours: str = Field(min_length=1, max_length=255)
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    image_url: str | None = Field(default=None, max_length=2048, pattern=_HTTPS)


class UpdateRestaurantRequest(CamelModel):
    """Partial: only sent fields apply (controller uses ``exclude_unset``). ``description`` and
    ``imageUrl`` may be cleared with ``null``; the rest may not."""

    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=2000)
    address: str | None = Field(default=None, min_length=1, max_length=500)
    phone: str | None = Field(default=None, min_length=1, max_length=32)
    opening_hours: str | None = Field(default=None, min_length=1, max_length=255)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    image_url: str | None = Field(default=None, max_length=2048, pattern=_HTTPS)

    _required = field_validator(
        "name", "address", "phone", "opening_hours", "latitude", "longitude"
    )(_not_null)


class CreateDishRequest(CamelModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=2000)
    image_url: str | None = Field(default=None, max_length=2048, pattern=_HTTPS)
    price: Decimal = Field(ge=0, max_digits=12, decimal_places=0)
    serving_g: int = Field(gt=0, le=10_000)
    kcal: int = Field(ge=0, le=20_000)
    protein_g: float = Field(ge=0, le=2_000)
    carbs_g: float = Field(ge=0, le=2_000)
    fat_g: float = Field(ge=0, le=2_000)
    fiber_g: float | None = Field(default=None, ge=0, le=2_000)


class UpdateDishRequest(CamelModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=2000)
    image_url: str | None = Field(default=None, max_length=2048, pattern=_HTTPS)
    price: Decimal | None = Field(default=None, ge=0, max_digits=12, decimal_places=0)
    serving_g: int | None = Field(default=None, gt=0, le=10_000)
    kcal: int | None = Field(default=None, ge=0, le=20_000)
    protein_g: float | None = Field(default=None, ge=0, le=2_000)
    carbs_g: float | None = Field(default=None, ge=0, le=2_000)
    fat_g: float | None = Field(default=None, ge=0, le=2_000)
    fiber_g: float | None = Field(default=None, ge=0, le=2_000)  # null clears it (not tracked)

    _required = field_validator(
        "name", "price", "serving_g", "kcal", "protein_g", "carbs_g", "fat_g"
    )(_not_null)


class ImageUploadResponse(CamelModel):
    url: str  # absolute (Cloudinary secure_url)
```

> Check once in a REPL that `field_validator(...)(fn)` assigned to a class attribute registers on this
> Pydantic version (`UpdateDishRequest(kcal=None)` must raise). If not, write it as a decorated
> `@field_validator(...) @classmethod def _required(cls, v): return _not_null(v)` in each class.

- [ ] **Step 5: Implement the controller**

`src/adapters/controllers/restaurant_controller.py`:

```python
"""Owner endpoints under /restaurants. HTTP <-> application DTO translation only.

"/mine" carries no id: one user owns at most one restaurant, so ownership is implied by the token.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, File, UploadFile, status

from src.adapters.schemas.restaurant_schemas import (
    CreateRestaurantRequest,
    ImageUploadResponse,
    RestaurantResponse,
    UpdateRestaurantRequest,
)
from src.application.dtos.restaurant import CreateRestaurantInputDTO, UpdateRestaurantInputDTO
from src.domain.exceptions import UnreadableImageException
from src.infrastructure.di import (
    CreateRestaurantUseCaseDep,
    CurrentUserDep,
    GetMyRestaurantUseCaseDep,
    UpdateMyRestaurantUseCaseDep,
    UploadRestaurantImageUseCaseDep,
    limit_upload_by_user,
)

router = APIRouter(prefix="/restaurants", tags=["restaurants"])

# Browser-renderable only (no HEIC): these images are shown on the web and in the app.
_ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}
_MAX_IMAGE_BYTES = 5 * 1024 * 1024


@router.post("", response_model=RestaurantResponse, status_code=status.HTTP_201_CREATED)
async def create_restaurant(
    body: CreateRestaurantRequest, user: CurrentUserDep, use_case: CreateRestaurantUseCaseDep
) -> RestaurantResponse:
    result = await use_case.execute(CreateRestaurantInputDTO(user_id=user.id, **body.model_dump()))
    return RestaurantResponse.from_dto(result)


@router.get("/mine", response_model=RestaurantResponse)
async def get_my_restaurant(
    user: CurrentUserDep, use_case: GetMyRestaurantUseCaseDep
) -> RestaurantResponse:
    return RestaurantResponse.from_dto(await use_case.execute(user.id))


@router.patch("/mine", response_model=RestaurantResponse)
async def update_my_restaurant(
    body: UpdateRestaurantRequest, user: CurrentUserDep, use_case: UpdateMyRestaurantUseCaseDep
) -> RestaurantResponse:
    result = await use_case.execute(
        UpdateRestaurantInputDTO(user_id=user.id, updates=body.model_dump(exclude_unset=True))
    )
    return RestaurantResponse.from_dto(result)


@router.post(
    "/mine/images",
    response_model=ImageUploadResponse,
    dependencies=[Depends(limit_upload_by_user)],
)
async def upload_image(
    user: CurrentUserDep,
    use_case: UploadRestaurantImageUseCaseDep,
    image: Annotated[UploadFile, File()],
) -> ImageUploadResponse:
    """Any signed-in user, so the create form can attach a photo before the restaurant exists."""
    if image.content_type not in _ALLOWED_IMAGE_TYPES:
        raise UnreadableImageException(f"unsupported image type: {image.content_type!r}")
    data = await image.read(_MAX_IMAGE_BYTES + 1)
    if len(data) > _MAX_IMAGE_BYTES:
        raise UnreadableImageException("image is larger than 5 MB")
    return ImageUploadResponse(url=await use_case.execute(data, image.content_type))
```

Register in `src/main.py`: `from src.adapters.controllers.restaurant_controller import router as restaurant_router` and `app.include_router(restaurant_router)`.

- [ ] **Step 6: Run tests**

Run: `uv run pytest tests/api/test_restaurant_endpoints.py -q && uv run lint-imports`
Expected: PASS (the two Task 6-dependent tests are skipped).

- [ ] **Step 7: Commit**

```bash
git add src tests/api/test_restaurant_endpoints.py
git commit -m "feat(restaurants): owner profile endpoints and image upload"
```

---

### Task 5: Owner dish endpoints

**Files:**
- Create: `src/application/use_cases/list_my_dishes.py`, `create_dish.py`, `update_dish.py`, `delete_dish.py`
- Modify: `src/adapters/schemas/restaurant_schemas.py` (already has dish schemas), `src/adapters/controllers/restaurant_controller.py`, `src/infrastructure/di/use_cases.py`, `src/infrastructure/di/__init__.py`, `tests/api/test_restaurant_endpoints.py`

**Interfaces:**
- Consumes: `owned_restaurant`, `owned_dish`, `DishResponse`, `CreateDishRequest`, `UpdateDishRequest`, `CreateDishInputDTO`, `UpdateDishInputDTO`.
- Produces: `GET|POST /restaurants/mine/dishes`, `PATCH|DELETE /restaurants/mine/dishes/{dish_id}`.

- [ ] **Step 1: Write the failing tests** (append to `tests/api/test_restaurant_endpoints.py`)

```python
async def test_dish_lifecycle(client, make_user, restaurant_body, dish_body):
    headers, _ = await _create(client, make_user, restaurant_body)
    created = await client.post("/restaurants/mine/dishes", json=dish_body, headers=headers)
    assert created.status_code == 201
    dish = created.json()
    assert (dish["status"], dish["servingG"], dish["proteinG"], dish["price"]) == ("pending", 500, 30, 55000)
    assert dish["fiberG"] is None

    patched = await client.patch(
        f"/restaurants/mine/dishes/{dish['id']}", json={"kcal": 480, "fiberG": 3.5}, headers=headers
    )
    assert patched.status_code == 200
    assert (patched.json()["kcal"], patched.json()["fiberG"], patched.json()["status"]) == (480, 3.5, "pending")

    listed = (await client.get("/restaurants/mine/dishes", headers=headers)).json()
    assert [d["id"] for d in listed] == [dish["id"]]

    assert (await client.delete(f"/restaurants/mine/dishes/{dish['id']}", headers=headers)).status_code == 204
    assert (await client.get("/restaurants/mine/dishes", headers=headers)).json() == []


async def test_dish_without_restaurant_is_404(client, make_user, dish_body):
    headers, _ = await make_user("nobody@example.com")
    assert (await client.post("/restaurants/mine/dishes", json=dish_body, headers=headers)).status_code == 404


async def test_other_owners_dish_is_404(client, make_user, restaurant_body, dish_body):
    alice, _ = await _create(client, make_user, restaurant_body, "alice@example.com")
    bob, _ = await _create(client, make_user, restaurant_body, "bob@example.com")
    dish = (await client.post("/restaurants/mine/dishes", json=dish_body, headers=alice)).json()
    url = f"/restaurants/mine/dishes/{dish['id']}"
    assert (await client.patch(url, json={"kcal": 1}, headers=bob)).status_code == 404
    assert (await client.delete(url, headers=bob)).status_code == 404


async def test_patch_null_kcal_is_422(client, make_user, restaurant_body, dish_body):
    headers, _ = await _create(client, make_user, restaurant_body)
    dish = (await client.post("/restaurants/mine/dishes", json=dish_body, headers=headers)).json()
    resp = await client.patch(f"/restaurants/mine/dishes/{dish['id']}", json={"kcal": None}, headers=headers)
    assert resp.status_code == 422 and "kcal" in resp.json()["errors"]
    cleared = await client.patch(
        f"/restaurants/mine/dishes/{dish['id']}", json={"fiberG": None}, headers=headers
    )
    assert cleared.status_code == 200 and cleared.json()["fiberG"] is None


async def test_negative_kcal_is_a_field_error(client, make_user, restaurant_body, dish_body):
    headers, _ = await _create(client, make_user, restaurant_body)
    resp = await client.post("/restaurants/mine/dishes", json={**dish_body, "kcal": -1}, headers=headers)
    assert resp.status_code == 422 and "kcal" in resp.json()["errors"]


async def test_editing_approved_dish_returns_it_to_pending(client, make_user, restaurant_body, dish_body):
    headers, _ = await _create(client, make_user, restaurant_body)
    dish = (await client.post("/restaurants/mine/dishes", json=dish_body, headers=headers)).json()
    admin = await _admin(make_user)
    await client.post(f"/admin/dishes/{dish['id']}/review", json={"decision": "approved"}, headers=admin)
    resp = await client.patch(f"/restaurants/mine/dishes/{dish['id']}", json={"price": 60000}, headers=headers)
    assert resp.json()["status"] == "pending"
```

(Skip-mark `test_editing_approved_dish_returns_it_to_pending` with `reason="needs Task 6"`.)

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/api/test_restaurant_endpoints.py -q`
Expected: FAIL with 404/405 on `/restaurants/mine/dishes`.

- [ ] **Step 3: Implement use cases**

`src/application/use_cases/list_my_dishes.py`:

```python
"""Use case: every dish of the caller's restaurant, any status, with rejection reasons."""

from __future__ import annotations

from dataclasses import dataclass

from src.application.dtos.restaurant import DishOutputDTO
from src.application.ports.restaurant_repository import RestaurantRepositoryProtocol
from src.application.use_cases.restaurant_support import owned_restaurant


@dataclass
class ListMyDishesUseCase:
    restaurants: RestaurantRepositoryProtocol

    async def execute(self, user_id: int) -> list[DishOutputDTO]:
        restaurant = await owned_restaurant(self.restaurants, user_id)
        return [DishOutputDTO.from_entity(d) for d in await self.restaurants.list_dishes(restaurant.id)]
```

`src/application/use_cases/create_dish.py`:

```python
"""Use case: add a dish (pending) to the caller's restaurant."""

from __future__ import annotations

from dataclasses import asdict, dataclass

from src.application.dtos.restaurant import CreateDishInputDTO, DishOutputDTO
from src.application.ports.restaurant_repository import RestaurantRepositoryProtocol
from src.application.use_cases.restaurant_support import owned_restaurant
from src.domain.entities.dish import Dish


@dataclass
class CreateDishUseCase:
    restaurants: RestaurantRepositoryProtocol

    async def execute(self, data: CreateDishInputDTO) -> DishOutputDTO:
        restaurant = await owned_restaurant(self.restaurants, data.user_id)
        fields = asdict(data)
        del fields["user_id"]
        dish = Dish.create(restaurant_id=restaurant.id, **fields)
        await self.restaurants.add_dish(dish)
        return DishOutputDTO.from_entity(dish)
```

`src/application/use_cases/update_dish.py`:

```python
"""Use case: partial dish edit. Any edit sends the dish back to pending (hidden until re-approved)."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import UTC, datetime

from src.application.dtos.restaurant import DishOutputDTO, UpdateDishInputDTO
from src.application.ports.restaurant_repository import RestaurantRepositoryProtocol
from src.application.use_cases.restaurant_support import owned_dish


@dataclass
class UpdateDishUseCase:
    restaurants: RestaurantRepositoryProtocol

    async def execute(self, data: UpdateDishInputDTO) -> DishOutputDTO:
        current = await owned_dish(self.restaurants, data.user_id, data.dish_id)
        dish = replace(current, **data.updates)
        dish.mark_edited(datetime.now(UTC))
        await self.restaurants.update_dish(dish)
        return DishOutputDTO.from_entity(dish)
```

`src/application/use_cases/delete_dish.py`:

```python
"""Use case: delete one of the caller's dishes outright (nothing references a dish yet)."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from src.application.ports.restaurant_repository import RestaurantRepositoryProtocol
from src.application.use_cases.restaurant_support import owned_dish


@dataclass
class DeleteDishUseCase:
    restaurants: RestaurantRepositoryProtocol

    async def execute(self, user_id: int, dish_id: UUID) -> None:
        dish = await owned_dish(self.restaurants, user_id, dish_id)
        await self.restaurants.delete_dish(dish.id)
```

DI: for each of `ListMyDishesUseCase`, `CreateDishUseCase`, `UpdateDishUseCase`, `DeleteDishUseCase`, add a provider taking `restaurants: RestaurantRepositoryDep` and an alias (`ListMyDishesUseCaseDep`, `CreateDishUseCaseDep`, `UpdateDishUseCaseDep`, `DeleteDishUseCaseDep`), exactly like `get_create_restaurant_use_case` in Task 4; re-export from `di/__init__.py`.

- [ ] **Step 4: Add routes** to `restaurant_controller.py` (extend the imports accordingly: `UUID`, `DishResponse`, `CreateDishRequest`, `UpdateDishRequest`, `CreateDishInputDTO`, `UpdateDishInputDTO`, the four new deps):

```python
@router.get("/mine/dishes", response_model=list[DishResponse])
async def list_my_dishes(user: CurrentUserDep, use_case: ListMyDishesUseCaseDep) -> list[DishResponse]:
    return [DishResponse.from_dto(d) for d in await use_case.execute(user.id)]


@router.post("/mine/dishes", response_model=DishResponse, status_code=status.HTTP_201_CREATED)
async def create_dish(
    body: CreateDishRequest, user: CurrentUserDep, use_case: CreateDishUseCaseDep
) -> DishResponse:
    return DishResponse.from_dto(
        await use_case.execute(CreateDishInputDTO(user_id=user.id, **body.model_dump()))
    )


@router.patch("/mine/dishes/{dish_id}", response_model=DishResponse)
async def update_dish(
    dish_id: UUID, body: UpdateDishRequest, user: CurrentUserDep, use_case: UpdateDishUseCaseDep
) -> DishResponse:
    result = await use_case.execute(
        UpdateDishInputDTO(user_id=user.id, dish_id=dish_id, updates=body.model_dump(exclude_unset=True))
    )
    return DishResponse.from_dto(result)


@router.delete("/mine/dishes/{dish_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_dish(dish_id: UUID, user: CurrentUserDep, use_case: DeleteDishUseCaseDep) -> None:
    await use_case.execute(user.id, dish_id)
```

- [ ] **Step 5: Run tests**

Run: `uv run pytest tests/api/test_restaurant_endpoints.py -q && uv run lint-imports`
Expected: PASS (Task 6-dependent tests skipped).

- [ ] **Step 6: Commit**

```bash
git add src tests/api/test_restaurant_endpoints.py
git commit -m "feat(restaurants): owner dish endpoints"
```

---

### Task 6: Admin moderation endpoints

**Files:**
- Create: `src/application/use_cases/list_admin_restaurants.py`, `get_admin_restaurant.py`, `review_restaurant.py`, `review_dish.py`, `src/adapters/schemas/admin_schemas.py`
- Modify: `src/adapters/controllers/admin_controller.py`, `src/infrastructure/di/use_cases.py`, `src/infrastructure/di/__init__.py`, `tests/api/test_admin_endpoints.py`, `tests/api/test_restaurant_endpoints.py` (remove skip marks)

**Interfaces:**
- Consumes: `RestaurantRepositoryProtocol.list_for_admin/get_by_id/get_dish/update/update_dish/list_dishes`, `RestaurantResponse`, `DishResponse`.
- Produces: `GET /admin/restaurants`, `GET /admin/restaurants/{id}`, `POST /admin/restaurants/{id}/review`, `POST /admin/dishes/{id}/review`; schema `ReviewRequest`.

- [ ] **Step 1: Write the failing tests** (append to `tests/api/test_admin_endpoints.py`)

```python
async def _restaurant_with(client, make_user, restaurant_body, dish_body, email, name, dishes=0):
    headers, _ = await make_user(email)
    r = (await client.post("/restaurants", json={**restaurant_body, "name": name}, headers=headers)).json()
    ids = []
    for _ in range(dishes):
        ids.append((await client.post("/restaurants/mine/dishes", json=dish_body, headers=headers)).json()["id"])
    return headers, r["id"], ids


async def _review(client, admin, kind, id_, decision, reason=None):
    body = {"decision": decision} | ({"reason": reason} if reason else {})
    return await client.post(f"/admin/{kind}/{id_}/review", json=body, headers=admin)


async def test_queue_includes_approved_restaurant_with_pending_dish(
    client, make_user, restaurant_body, dish_body
):
    admin, _ = await make_user("admin@example.com", admin=True)
    _, a, _ = await _restaurant_with(client, make_user, restaurant_body, dish_body, "a@x.co", "A pending")
    _, b, b_dishes = await _restaurant_with(client, make_user, restaurant_body, dish_body, "b@x.co", "B done", 1)
    _, c, c_dishes = await _restaurant_with(client, make_user, restaurant_body, dish_body, "c@x.co", "C new dish", 2)
    _, d, _ = await _restaurant_with(client, make_user, restaurant_body, dish_body, "d@x.co", "D rejected", 1)
    for rid in (b, c):
        await _review(client, admin, "restaurants", rid, "approved")
    await _review(client, admin, "dishes", b_dishes[0], "approved")
    await _review(client, admin, "dishes", c_dishes[0], "approved")
    await _review(client, admin, "restaurants", d, "rejected", "fake")

    queue = (await client.get("/admin/restaurants?needsReview=true", headers=admin)).json()
    by_name = {row["name"]: row for row in queue}
    assert set(by_name) == {"A pending", "C new dish"}
    assert (by_name["C new dish"]["dishCount"], by_name["C new dish"]["pendingDishCount"]) == (2, 1)
    assert by_name["A pending"]["ownerEmail"] == "a@x.co"

    everything = (await client.get("/admin/restaurants", headers=admin)).json()
    assert len(everything) == 4
    rejected = (await client.get("/admin/restaurants?status=rejected", headers=admin)).json()
    assert [(r["name"], r["rejectionReason"]) for r in rejected] == [("D rejected", "fake")]


async def test_detail_includes_full_menu(client, make_user, restaurant_body, dish_body):
    admin, _ = await make_user("admin@example.com", admin=True)
    _, rid, dish_ids = await _restaurant_with(client, make_user, restaurant_body, dish_body, "o@x.co", "R", 2)
    detail = (await client.get(f"/admin/restaurants/{rid}", headers=admin)).json()
    assert detail["restaurant"]["id"] == rid
    assert [d["id"] for d in detail["dishes"]] == dish_ids
    assert detail["dishes"][0]["kcal"] == 450


async def test_unknown_restaurant_is_404(client, make_user):
    admin, _ = await make_user("admin@example.com", admin=True)
    missing = "00000000-0000-0000-0000-000000000000"
    assert (await client.get(f"/admin/restaurants/{missing}", headers=admin)).status_code == 404
    assert (await _review(client, admin, "dishes", missing, "approved")).status_code == 404


async def test_reject_requires_reason_field_error(client, make_user, restaurant_body, dish_body):
    admin, _ = await make_user("admin@example.com", admin=True)
    _, rid, _ = await _restaurant_with(client, make_user, restaurant_body, dish_body, "o@x.co", "R")
    resp = await _review(client, admin, "restaurants", rid, "rejected")
    assert resp.status_code == 422 and "reason" in resp.json()["errors"]


async def test_repeat_review_is_idempotent_and_takedown_works(client, make_user, restaurant_body, dish_body):
    admin, _ = await make_user("admin@example.com", admin=True)
    _, rid, _ = await _restaurant_with(client, make_user, restaurant_body, dish_body, "o@x.co", "R")
    first = await _review(client, admin, "restaurants", rid, "approved")
    again = await _review(client, admin, "restaurants", rid, "approved")
    assert first.status_code == again.status_code == 200
    assert again.json()["status"] == "approved"
    down = await _review(client, admin, "restaurants", rid, "rejected", "food safety report")
    assert (down.json()["status"], down.json()["rejectionReason"]) == ("rejected", "food safety report")
```

Remove the `@pytest.mark.skip(reason="needs Task 6")` marks in `tests/api/test_restaurant_endpoints.py`.

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/api/test_admin_endpoints.py tests/api/test_restaurant_endpoints.py -q`
Expected: FAIL (`/admin/restaurants` returns the Task 3 stub `[]`; review routes 404/405).

- [ ] **Step 3: Implement use cases**

`src/application/use_cases/list_admin_restaurants.py`:

```python
"""Use case: the admin's restaurant list / review queue."""

from __future__ import annotations

from dataclasses import dataclass

from src.application.dtos.admin import AdminRestaurantRowDTO
from src.application.ports.restaurant_repository import RestaurantRepositoryProtocol
from src.domain.enums import ModerationStatus


@dataclass
class ListAdminRestaurantsUseCase:
    restaurants: RestaurantRepositoryProtocol

    async def execute(
        self, needs_review: bool, status: ModerationStatus | None
    ) -> list[AdminRestaurantRowDTO]:
        # ponytail: unpaginated; add a cursor once the queue routinely holds hundreds of rows.
        return await self.restaurants.list_for_admin(needs_review, status)
```

`src/application/use_cases/get_admin_restaurant.py`:

```python
"""Use case: one restaurant with its full menu and nutrition, for review."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from src.application.dtos.admin import AdminRestaurantDetailDTO
from src.application.dtos.restaurant import DishOutputDTO, RestaurantOutputDTO
from src.application.ports.restaurant_repository import RestaurantRepositoryProtocol
from src.domain.exceptions import RestaurantNotFoundException


@dataclass
class GetAdminRestaurantUseCase:
    restaurants: RestaurantRepositoryProtocol

    async def execute(self, restaurant_id: UUID) -> AdminRestaurantDetailDTO:
        restaurant = await self.restaurants.get_by_id(restaurant_id)
        if restaurant is None:
            raise RestaurantNotFoundException(f"restaurant {restaurant_id} not found")
        dishes = await self.restaurants.list_dishes(restaurant_id)
        return AdminRestaurantDetailDTO(
            restaurant=RestaurantOutputDTO.from_entity(restaurant),
            dishes=[DishOutputDTO.from_entity(d) for d in dishes],
        )
```

`src/application/use_cases/review_restaurant.py`:

```python
"""Use case: approve, reject, or take down a restaurant. Idempotent."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from src.application.dtos.restaurant import RestaurantOutputDTO
from src.application.ports.restaurant_repository import RestaurantRepositoryProtocol
from src.domain.enums import ReviewDecision
from src.domain.exceptions import RestaurantNotFoundException


@dataclass
class ReviewRestaurantUseCase:
    restaurants: RestaurantRepositoryProtocol

    async def execute(
        self, restaurant_id: UUID, decision: ReviewDecision, reason: str | None
    ) -> RestaurantOutputDTO:
        restaurant = await self.restaurants.get_by_id(restaurant_id)
        if restaurant is None:
            raise RestaurantNotFoundException(f"restaurant {restaurant_id} not found")
        restaurant.review(decision, reason, datetime.now(UTC))
        await self.restaurants.update(restaurant)
        return RestaurantOutputDTO.from_entity(restaurant)
```

`src/application/use_cases/review_dish.py`:

```python
"""Use case: approve or reject one dish. Idempotent."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from src.application.dtos.restaurant import DishOutputDTO
from src.application.ports.restaurant_repository import RestaurantRepositoryProtocol
from src.domain.enums import ReviewDecision
from src.domain.exceptions import DishNotFoundException


@dataclass
class ReviewDishUseCase:
    restaurants: RestaurantRepositoryProtocol

    async def execute(
        self, dish_id: UUID, decision: ReviewDecision, reason: str | None
    ) -> DishOutputDTO:
        dish = await self.restaurants.get_dish(dish_id)
        if dish is None:
            raise DishNotFoundException(f"dish {dish_id} not found")
        dish.review(decision, reason, datetime.now(UTC))
        await self.restaurants.update_dish(dish)
        return DishOutputDTO.from_entity(dish)
```

DI: providers + aliases `ListAdminRestaurantsUseCaseDep`, `GetAdminRestaurantUseCaseDep`, `ReviewRestaurantUseCaseDep`, `ReviewDishUseCaseDep` (each takes `restaurants: RestaurantRepositoryDep`, same shape as Task 4); re-export.

- [ ] **Step 4: Implement schemas** (`src/adapters/schemas/admin_schemas.py`; Task 7 appends dashboard schemas)

```python
"""HTTP wire models for /admin."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import Field, ValidationInfo, field_validator

from src.adapters.schemas.base import CamelModel
from src.adapters.schemas.restaurant_schemas import DishResponse, RestaurantResponse
from src.application.dtos.admin import AdminRestaurantDetailDTO, AdminRestaurantRowDTO
from src.domain.enums import ModerationStatus, ReviewDecision


class ReviewRequest(CamelModel):
    decision: ReviewDecision
    # validate_default so an omitted reason is still checked; the error lands on errors.reason.
    reason: str | None = Field(default=None, max_length=1000, validate_default=True)

    @field_validator("reason")
    @classmethod
    def _required_to_reject(cls, value: str | None, info: ValidationInfo) -> str | None:
        if info.data.get("decision") == ReviewDecision.REJECTED and not (value or "").strip():
            raise ValueError("a reason is required to reject")
        return value


class AdminRestaurantRowResponse(CamelModel):
    id: UUID
    name: str
    status: ModerationStatus
    owner_name: str | None
    owner_email: str
    dish_count: int
    pending_dish_count: int
    updated_at: datetime
    rejection_reason: str | None

    @classmethod
    def from_dto(cls, dto: AdminRestaurantRowDTO) -> AdminRestaurantRowResponse:
        return cls(**vars(dto))


class AdminRestaurantDetailResponse(CamelModel):
    restaurant: RestaurantResponse
    dishes: list[DishResponse]

    @classmethod
    def from_dto(cls, dto: AdminRestaurantDetailDTO) -> AdminRestaurantDetailResponse:
        return cls(
            restaurant=RestaurantResponse.from_dto(dto.restaurant),
            dishes=[DishResponse.from_dto(d) for d in dto.dishes],
        )
```

- [ ] **Step 5: Replace the stub controller** `src/adapters/controllers/admin_controller.py`:

```python
"""Admin endpoints: moderation and dashboard. HTTP <-> DTO translation only.

Every route is admin-only via the router-level dependency.
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from src.adapters.schemas.admin_schemas import (
    AdminRestaurantDetailResponse,
    AdminRestaurantRowResponse,
    ReviewRequest,
)
from src.adapters.schemas.restaurant_schemas import DishResponse, RestaurantResponse
from src.domain.enums import ModerationStatus
from src.infrastructure.di import (
    GetAdminRestaurantUseCaseDep,
    ListAdminRestaurantsUseCaseDep,
    ReviewDishUseCaseDep,
    ReviewRestaurantUseCaseDep,
    get_current_admin,
)

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(get_current_admin)])


@router.get("/restaurants", response_model=list[AdminRestaurantRowResponse])
async def list_restaurants(
    use_case: ListAdminRestaurantsUseCaseDep,
    needs_review: Annotated[bool, Query(alias="needsReview")] = False,
    status: ModerationStatus | None = None,
) -> list[AdminRestaurantRowResponse]:
    return [AdminRestaurantRowResponse.from_dto(r) for r in await use_case.execute(needs_review, status)]


@router.get("/restaurants/{restaurant_id}", response_model=AdminRestaurantDetailResponse)
async def get_restaurant(
    restaurant_id: UUID, use_case: GetAdminRestaurantUseCaseDep
) -> AdminRestaurantDetailResponse:
    return AdminRestaurantDetailResponse.from_dto(await use_case.execute(restaurant_id))


@router.post("/restaurants/{restaurant_id}/review", response_model=RestaurantResponse)
async def review_restaurant(
    restaurant_id: UUID, body: ReviewRequest, use_case: ReviewRestaurantUseCaseDep
) -> RestaurantResponse:
    return RestaurantResponse.from_dto(await use_case.execute(restaurant_id, body.decision, body.reason))


@router.post("/dishes/{dish_id}/review", response_model=DishResponse)
async def review_dish(dish_id: UUID, body: ReviewRequest, use_case: ReviewDishUseCaseDep) -> DishResponse:
    return DishResponse.from_dto(await use_case.execute(dish_id, body.decision, body.reason))
```

- [ ] **Step 6: Run tests**

Run: `uv run pytest tests/api/test_admin_endpoints.py tests/api/test_restaurant_endpoints.py -q && uv run lint-imports`
Expected: all PASS, nothing skipped.

- [ ] **Step 7: Commit**

```bash
git add src tests/api
git commit -m "feat(admin): restaurant and dish moderation endpoints"
```

---

### Task 7: Admin dashboard

**Files:**
- Create: `src/application/use_cases/get_admin_dashboard.py`, `tests/unit/test_admin_dashboard.py`
- Modify: `src/adapters/schemas/admin_schemas.py`, `src/adapters/controllers/admin_controller.py`, `src/infrastructure/di/use_cases.py`, `src/infrastructure/di/__init__.py`, `tests/api/test_admin_endpoints.py`

**Interfaces:**
- Consumes: `AdminStatsRepositoryProtocol`, `AdminStatsRepositoryDep`, `DashboardDTO`, `DashboardDayDTO`.
- Produces: `GetAdminDashboardUseCase.execute(from_date: date | None, to_date: date | None, today: date | None = None) -> DashboardDTO`; `GET /admin/dashboard?from=&to=`.

- [ ] **Step 1: Write the failing unit tests**

`tests/unit/test_admin_dashboard.py`:

```python
"""GetAdminDashboardUseCase: Vietnam-day bucketing, zero-fill, range rules. No I/O."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from src.application.use_cases.get_admin_dashboard import GetAdminDashboardUseCase
from src.domain.exceptions import InvalidAttributeException

TODAY = date(2026, 10, 8)


class FakeStats:
    def __init__(self, payments=(), users=(), restaurants=()):
        self.payments, self.users, self.restaurants = list(payments), list(users), list(restaurants)
        self.ranges: list[tuple[datetime, datetime]] = []

    async def paid_payments(self, start, end):
        self.ranges.append((start, end))
        return [(t, a) for t, a in self.payments if start <= t < end]

    async def user_signups(self, start, end):
        return [t for t in self.users if start <= t < end]

    async def restaurant_signups(self, start, end):
        return [t for t in self.restaurants if start <= t < end]


async def test_bucketing_uses_vietnam_day_boundary():
    stats = FakeStats(payments=[
        (datetime(2026, 10, 7, 16, 59, tzinfo=UTC), Decimal("99000")),   # 23:59 VN on Oct 7
        (datetime(2026, 10, 7, 17, 0, tzinfo=UTC), Decimal("990000")),   # 00:00 VN on Oct 8
    ])
    result = await GetAdminDashboardUseCase(stats).execute(date(2026, 10, 7), date(2026, 10, 8), TODAY)
    assert [(d.date, d.premium_revenue) for d in result.daily] == [
        (date(2026, 10, 7), 99000), (date(2026, 10, 8), 990000),
    ]
    assert result.premium_revenue == 1089000 and isinstance(result.premium_revenue, int)


async def test_series_is_zero_filled_and_counts_signups():
    stats = FakeStats(
        users=[datetime(2026, 10, 2, 3, tzinfo=UTC)] * 2,
        restaurants=[datetime(2026, 10, 3, 3, tzinfo=UTC)],
    )
    result = await GetAdminDashboardUseCase(stats).execute(date(2026, 10, 1), date(2026, 10, 3), TODAY)
    assert [(d.date.day, d.new_users, d.new_restaurants, d.ad_revenue) for d in result.daily] == [
        (1, 0, 0, 0), (2, 2, 0, 0), (3, 0, 1, 0),
    ]
    assert (result.new_users, result.new_restaurants, result.ad_revenue) == (2, 1, 0)


async def test_default_range_is_last_30_vietnam_days():
    stats = FakeStats()
    result = await GetAdminDashboardUseCase(stats).execute(None, None, TODAY)
    assert (result.from_date, result.to_date, len(result.daily)) == (date(2026, 9, 9), TODAY, 30)
    assert stats.ranges == [(
        datetime(2026, 9, 8, 17, tzinfo=UTC), datetime(2026, 10, 8, 17, tzinfo=UTC),
    )]


async def test_range_rules():
    use_case = GetAdminDashboardUseCase(FakeStats())
    with pytest.raises(InvalidAttributeException):
        await use_case.execute(date(2026, 10, 9), date(2026, 10, 8), TODAY)
    with pytest.raises(InvalidAttributeException):
        await use_case.execute(date(2025, 10, 7), date(2026, 10, 8), TODAY)  # 367 days
    assert len((await use_case.execute(date(2025, 10, 8), date(2026, 10, 8), TODAY)).daily) == 366
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/unit/test_admin_dashboard.py -q`
Expected: FAIL with `ModuleNotFoundError: ...get_admin_dashboard`

- [ ] **Step 3: Implement the use case**

`src/application/use_cases/get_admin_dashboard.py`:

```python
"""Use case: cash flow (Premium + ads) and growth (users, restaurants) per Vietnam day.

Days are Vietnam days (UTC+7), inclusive on both ends, zero-filled so the chart has no gaps.
Ad revenue is 0 until ads exist; the field is there so the wire contract won't change.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta, timezone
from decimal import Decimal

from src.application.dtos.admin import DashboardDayDTO, DashboardDTO
from src.application.ports.admin_stats_repository import AdminStatsRepositoryProtocol
from src.domain.exceptions import InvalidAttributeException

VIETNAM = timezone(timedelta(hours=7))
_DEFAULT_DAYS = 30
_MAX_DAYS = 366


def _vn_day(instant: datetime) -> date:
    return instant.astimezone(VIETNAM).date()


def _vn_midnight_utc(day: date) -> datetime:
    return datetime.combine(day, time(), VIETNAM).astimezone(UTC)


@dataclass
class GetAdminDashboardUseCase:
    stats: AdminStatsRepositoryProtocol

    async def execute(
        self, from_date: date | None, to_date: date | None, today: date | None = None
    ) -> DashboardDTO:
        to_date = to_date or today or datetime.now(VIETNAM).date()
        from_date = from_date or to_date - timedelta(days=_DEFAULT_DAYS - 1)
        if from_date > to_date:
            raise InvalidAttributeException("'from' must not be after 'to'")
        span = (to_date - from_date).days + 1
        if span > _MAX_DAYS:
            raise InvalidAttributeException(f"the range must not exceed {_MAX_DAYS} days")

        start, end = _vn_midnight_utc(from_date), _vn_midnight_utc(to_date + timedelta(days=1))
        # ponytail: rows are fetched and bucketed in Python, O(rows in range) and dialect-portable.
        # Move to SQL GROUP BY when a 30-day window holds more than ~100k payments or signups.
        revenue: dict[date, Decimal] = {}
        for paid_at, amount in await self.stats.paid_payments(start, end):
            revenue[_vn_day(paid_at)] = revenue.get(_vn_day(paid_at), Decimal(0)) + amount
        users = Counter(_vn_day(t) for t in await self.stats.user_signups(start, end))
        restaurants = Counter(_vn_day(t) for t in await self.stats.restaurant_signups(start, end))

        daily = [
            DashboardDayDTO(
                date=day,
                premium_revenue=int(revenue.get(day, 0)),
                ad_revenue=0,
                new_users=users[day],
                new_restaurants=restaurants[day],
            )
            for day in (from_date + timedelta(days=i) for i in range(span))
        ]
        return DashboardDTO(
            from_date=from_date,
            to_date=to_date,
            premium_revenue=sum(d.premium_revenue for d in daily),
            ad_revenue=0,
            new_users=sum(d.new_users for d in daily),
            new_restaurants=sum(d.new_restaurants for d in daily),
            daily=daily,
        )
```

DI:

```python
def get_get_admin_dashboard_use_case(stats: AdminStatsRepositoryDep) -> GetAdminDashboardUseCase:
    return GetAdminDashboardUseCase(stats=stats)


GetAdminDashboardUseCaseDep = Annotated[
    GetAdminDashboardUseCase, Depends(get_get_admin_dashboard_use_case)
]
```

Re-export `GetAdminDashboardUseCaseDep` and `get_get_admin_dashboard_use_case`.

- [ ] **Step 4: Run unit tests**

Run: `uv run pytest tests/unit/test_admin_dashboard.py -q`
Expected: PASS

- [ ] **Step 5: Write the failing API test** (append to `tests/api/test_admin_endpoints.py`)

```python
async def test_dashboard_sums_only_paid_payments(client, make_user, restaurant_body):
    from datetime import UTC, datetime, timedelta, timezone
    from decimal import Decimal
    from uuid import uuid4

    from src.domain.enums import PaymentStatus, PlanType
    from src.infrastructure.db.models.payment_model import PaymentORM
    from src.infrastructure.db.session import SessionLocal

    admin, admin_id = await make_user("admin@example.com", admin=True)
    owner, _ = await make_user("owner@example.com")
    await client.post("/restaurants", json=restaurant_body, headers=owner)
    now = datetime.now(UTC)
    async with SessionLocal() as session:
        session.add_all([
            PaymentORM(id=uuid4(), user_id=admin_id, plan_type=PlanType.MONTHLY, amount=Decimal("99000"),
                       status=PaymentStatus.PAID, created_at=now, paid_at=now),
            PaymentORM(id=uuid4(), user_id=admin_id, plan_type=PlanType.ANNUAL, amount=Decimal("990000"),
                       status=PaymentStatus.PENDING, created_at=now, paid_at=None),
        ])
        await session.commit()

    today = datetime.now(timezone(timedelta(hours=7))).date().isoformat()
    resp = await client.get(f"/admin/dashboard?from={today}&to={today}", headers=admin)
    assert resp.status_code == 200
    body = resp.json()
    assert body["totals"] == {"premiumRevenue": 99000, "adRevenue": 0, "newUsers": 2, "newRestaurants": 1}
    assert body["daily"] == [{
        "date": today, "premiumRevenue": 99000, "adRevenue": 0, "newUsers": 2, "newRestaurants": 1,
    }]
    assert (body["from"], body["to"]) == (today, today)


async def test_dashboard_bad_range_is_400(client, make_user):
    admin, _ = await make_user("admin@example.com", admin=True)
    resp = await client.get("/admin/dashboard?from=2026-10-09&to=2026-10-08", headers=admin)
    assert resp.status_code == 400
```

- [ ] **Step 6: Implement schemas and route**

Append to `src/adapters/schemas/admin_schemas.py` (add `from datetime import date` and `from pydantic import ConfigDict`, plus `DashboardDTO` to the imports):

```python
class DashboardTotalsResponse(CamelModel):
    premium_revenue: int
    ad_revenue: int
    new_users: int
    new_restaurants: int


class DashboardDayResponse(DashboardTotalsResponse):
    date: date


class DashboardResponse(CamelModel):
    # "from" is a Python keyword: declare it as from_date with an explicit alias.
    from_date: date = Field(alias="from")
    to_date: date = Field(alias="to")
    totals: DashboardTotalsResponse
    daily: list[DashboardDayResponse]

    @classmethod
    def from_dto(cls, dto: DashboardDTO) -> DashboardResponse:
        return cls(
            from_date=dto.from_date,
            to_date=dto.to_date,
            totals=DashboardTotalsResponse(
                premium_revenue=dto.premium_revenue, ad_revenue=dto.ad_revenue,
                new_users=dto.new_users, new_restaurants=dto.new_restaurants,
            ),
            daily=[DashboardDayResponse(**vars(d)) for d in dto.daily],
        )
```

Append to `admin_controller.py` (add `from datetime import date`, `DashboardResponse`, `GetAdminDashboardUseCaseDep`):

```python
@router.get("/dashboard", response_model=DashboardResponse)
async def dashboard(
    use_case: GetAdminDashboardUseCaseDep,
    from_: Annotated[date | None, Query(alias="from")] = None,
    to: Annotated[date | None, Query()] = None,
) -> DashboardResponse:
    """Vietnam days (UTC+7), inclusive, zero-filled. Default: the last 30 days."""
    return DashboardResponse.from_dto(await use_case.execute(from_, to))
```

> `response_model` serializes by alias (FastAPI default), so the wire keys are `from`/`to`/`premiumRevenue`.
> Dates serialize as `YYYY-MM-DD`.

- [ ] **Step 7: Run tests**

Run: `uv run pytest tests/unit/test_admin_dashboard.py tests/api/test_admin_endpoints.py -q && uv run lint-imports`
Expected: PASS

- [ ] **Step 8: Commit**

```bash
git add src tests
git commit -m "feat(admin): cash-flow and growth dashboard"
```

---

### Task 8: Docs, full verification, hand-off to FoodFenWeb

**Files:**
- Modify: `docs/marketplace.md`, `CLAUDE.md`

- [ ] **Step 1: Full verification**

Run: `make test && uv run lint-imports`
Expected: everything passes; `Contracts: 2 kept, 0 broken.`

Then check the OpenAPI enums FoodFenWeb generates from:

Run: `uv run python -c "import json; from src.main import app; s=app.openapi()['components']['schemas']; print(s['UserRole'], s['ModerationStatus'], s['ReviewDecision'])"`
Expected: three enum schemas with the values from Task 1.

- [ ] **Step 2: Update `docs/marketplace.md`**

- Status line: `Status: **pieces 1–2 implemented** (branch feat/restaurants-admin).`
- Vision table: rows 1 and 2 → `implemented`.
- Rename the heading `## API (planned)` → `## API`.
- Contract details are already final (updated during planning); only fix them if the implementation had to deviate.

- [ ] **Step 3: Update `CLAUDE.md`** section "Restaurants & admin". Keep the pointer line and add:

```markdown
- **Admin** = `users.role = 'admin'`, set with SQL. `CurrentAdminDep` / router-level
  `Depends(get_current_admin)` (403); the role is read from the DB per request, never from the JWT.
- **Owner** is not a role: `restaurants.user_id` (unique). Owner routes are `/restaurants/mine/...`;
  ownership is implied, and another owner's dish is a 404 (`use_cases/restaurant_support.py`).
- Moderation transitions live only in `Restaurant`/`Dish` `.review()` / `.mark_edited()`; a use case
  never assigns `status`. Public = approved dish of an approved restaurant (no public endpoint yet).
- Dashboard buckets rows into Vietnam days in `get_admin_dashboard.py` (Python, not SQL; see its
  `ponytail:` note).
```

- [ ] **Step 4: Commit**

```bash
git add docs/marketplace.md CLAUDE.md
git commit -m "docs: restaurants and admin implemented"
```

- [ ] **Step 5: Tell FoodFenWeb** (the controller session does this, not a subagent): send `foodfenweb-b9` a message saying the endpoints have landed on `feat/restaurants-admin`, and it can regenerate the client with `OPENAPI_URL=spec.json npm run api:gen`.
