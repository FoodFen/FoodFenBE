# Diary Sync Push (Phase 2) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add push endpoints (`POST`/`PATCH`/`DELETE`) for the five diary
resources that already support pull (`daily-goals`, `food-entries`,
`activity-logs`, `weight-logs`, `water-logs`) plus a new `PATCH /users/me`
for offline profile edits, per `docs/backend-contracts/sync.md` (FoodFenFE
repo).

**Architecture:** Every create endpoint takes a client-generated `clientId`
string; the repository layer makes creation idempotent via a DB unique
constraint on `(user_id, client_id)` plus a catch-and-requery on conflict —
no batch/upsert SQL, same plain SQLAlchemy style as the rest of the
codebase. `food_entries` and `water_logs` (the only two resources with
`DELETE`) get a `deleted_at` column; every existing read path for them
filters it out. `PATCH` on `food-entries`/`activity-logs` is a full replace
(matches the contract's "same body as POST"); `PATCH /users/me` is a true
partial patch via Pydantic's `exclude_unset`.

**Tech Stack:** Python 3.11+, FastAPI, async SQLAlchemy 2.0 (asyncpg),
Pydantic v2, Alembic, PostgreSQL, pytest.

**Spec:** `docs/superpowers/specs/2026-09-24-diary-sync-push-design.md`

## Global Constraints

- Domain layer (`src/domain/`): standard library only. No `sqlalchemy`,
  `fastapi`, `pydantic` imports there.
- Application layer (`src/application/`): no `fastapi`, `sqlalchemy`,
  `pydantic`, `src.adapters`, or `src.infrastructure` imports. Use cases
  take/return dataclass DTOs only — never a Pydantic schema or ORM object.
- Ports are `typing.Protocol`, never `abc.ABC`.
- Never raise `HTTPException` from application/domain — raise a
  `DomainException` subclass; `src/adapters/exception_handlers.py` maps it.
- `userId`/ownership is inferred from `CurrentUserDep`, never a request
  field, on every endpoint in this plan.
- `404` for "doesn't exist" and "exists but belongs to another user" are
  identical responses (existence isn't leaked) — matches
  `GetFoodEntryUseCase`'s existing pattern.
- Every new/changed ORM model change ships with an Alembic migration in the
  same task; verify `alembic upgrade head --sql` against
  `Base.metadata`-rendered DDL, and a real upgrade/downgrade round trip.
- Run `uv run lint-imports` before considering any task done.
- `client_id` is a required, keyword-only parameter on every affected
  entity's `.create()` factory (`*, client_id: str`) — keyword-only so
  inserting it can never silently shift an existing positional argument
  into the wrong parameter at an untouched call site.

## Review Focus

- **Idempotent retry after a dropped response.** POSTing the same `clientId`
  twice must return the same row, not create a duplicate — this is the
  entire point of the feature. Covered in Task 1 (food-entries, proving the
  shared mechanism) and re-verified in Tasks 3–6 for each resource.
- **A soft-deleted row must vanish from every read path**, not just stop
  responding to its own `DELETE` — `GET` by id, the list endpoint, and a
  second `PATCH`/`DELETE` attempt against it all need to 404/omit it.
  Covered in Task 2 (food-entries) and Task 6 (water-logs).
- **`PATCH`/`DELETE` on another user's row returns 404, not a silent
  success or a 403** — easy to regress by forgetting the ownership check
  when writing a *new* use case, unlike `GetFoodEntryUseCase` which already
  has it. Covered in Task 2 and Task 3.
- **`PATCH /users/me` omitting a field leaves it unchanged** — this is the
  one endpoint in the whole plan with different semantics (true partial
  patch) from every other `PATCH` here (full replace); easy to get wrong by
  reusing the food-entries/activity-logs pattern. Covered in Task 7.
- **`subscriptionTier` in the `PATCH /users/me` body is rejected with
  `422`, not silently dropped** — Pydantic's default `extra="ignore"` would
  otherwise swallow a client's attempt to self-grant Premium instead of
  rejecting it. Covered in Task 7.

---

## Task 1: Idempotency + soft-delete foundation, proven on food-entries

This task builds the shared mechanism (migration, exceptions, idempotency
helper) and every entity's `client_id` field, then proves the whole thing
end-to-end by wiring it into the one push endpoint that already exists
(`POST /food-entries`) plus its soft-delete groundwork. Tasks 2–6 repeat
this proven pattern for the remaining resources without re-deriving it.

**Files:**
- Create: `alembic/versions/0011_diary_sync_push_fields.py`
- Create: `src/infrastructure/db/repositories/idempotency.py`
- Modify: `src/domain/exceptions.py`
- Modify: `src/domain/entities/food_entry.py`, `daily_goal.py`,
  `activity_log.py`, `weight_log.py`, `water_log.py`
- Modify: `src/infrastructure/db/models/food_entry_model.py`,
  `daily_goal_model.py`, `activity_log_model.py`, `weight_log_model.py`,
  `water_log_model.py`
- Modify: `src/infrastructure/db/repositories/food_entry_repository.py`
- Modify: `src/application/dtos/food_entry.py`
- Modify: `src/adapters/schemas/food_entry_schemas.py`
- Modify: `src/adapters/controllers/food_entry_controller.py`
- Modify (call-site fixes, see Step 8):
  `tests/unit/test_entities.py`,
  `tests/unit/test_list_daily_goals_use_case.py`,
  `tests/unit/test_list_diary_log_use_cases.py`,
  `tests/api/test_daily_goal_endpoints.py`,
  `tests/api/test_activity_log_endpoints.py`,
  `tests/api/test_weight_log_endpoints.py`,
  `tests/api/test_water_log_endpoints.py`,
  `tests/api/test_food_entry_endpoints.py`,
  `tests/integration/test_food_entry_repository.py`,
  `tests/integration/test_diary_sync_repositories.py`

**Interfaces:**
- Produces: `create_idempotent(session: AsyncSession, row: _Row, model: type[_Row]) -> _Row`
  (`src/infrastructure/db/repositories/idempotency.py`) — every later
  task's `create()` repo method calls this instead of a plain
  `session.add()`/`flush()`.
- Produces: `ActivityLogNotFoundException`, `WaterLogNotFoundException`
  (`src/domain/exceptions.py`), both `EntityNotFoundException` subclasses
  (auto-map to 404 via the existing handler registration).
- Produces: every entity's `.create()` gains a required keyword-only
  `client_id: str` parameter; every entity gains a `client_id: str` field.
- Produces: `FoodEntryRepositoryProtocol.create()` is now idempotent by
  `client_id`; `get_by_id`/`list_by_date_range` filter out soft-deleted rows.

- [ ] **Step 1: Write the migration**

Create `alembic/versions/0011_diary_sync_push_fields.py`:

```python
"""add client_id idempotency + soft delete for diary sync push

Revision ID: 0011
Revises: 0010
Create Date: 2026-09-24
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0011"
down_revision: str | None = "0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_CLIENT_ID_TABLES = ("food_entries", "daily_goals", "activity_logs", "weight_logs", "water_logs")
_SOFT_DELETE_TABLES = ("food_entries", "water_logs")


def upgrade() -> None:
    # client_id is NOT NULL with no default. Existing rows (local dev/demo
    # data — no real users yet, confirmed this session) have no
    # client-generated id to backfill honestly, so this clears them rather
    # than invent a synthetic value. CASCADE also clears `ingredients`
    # (FK to food_entries).
    for table in _CLIENT_ID_TABLES:
        op.execute(f"TRUNCATE TABLE {table} CASCADE")

    for table in _CLIENT_ID_TABLES:
        op.add_column(table, sa.Column("client_id", sa.String(length=64), nullable=False))
        op.create_unique_constraint(f"uq_{table}_client_id", table, ["user_id", "client_id"])

    for table in _SOFT_DELETE_TABLES:
        op.add_column(table, sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    for table in _SOFT_DELETE_TABLES:
        op.drop_column(table, "deleted_at")

    for table in _CLIENT_ID_TABLES:
        op.drop_constraint(f"uq_{table}_client_id", table, type_="unique")
        op.drop_column(table, "client_id")
```

- [ ] **Step 2: Verify the migration against the real dev DB**

Run (requires `make docker-up` first):
```bash
uv run alembic upgrade head --sql > /tmp/up.sql
uv run alembic downgrade 0010:0011 --sql > /tmp/down.sql
```
Read both files: `up.sql` should `TRUNCATE`, `ADD COLUMN client_id ... NOT
NULL`, and `ADD CONSTRAINT uq_<table>_client_id UNIQUE (user_id,
client_id)` for all 5 tables, then `ADD COLUMN deleted_at` for
`food_entries`/`water_logs`. `down.sql` should drop them in reverse. Then
do a real round trip:
```bash
uv run alembic upgrade head
uv run alembic downgrade 0010
uv run alembic upgrade head
```
Expected: all three commands succeed with no errors.

- [ ] **Step 3: Add the two new domain exceptions**

Edit `src/domain/exceptions.py`, append after `FoodEntryNotFoundException`:

```python


class ActivityLogNotFoundException(EntityNotFoundException):
    """A requested activity log does not exist."""


class WaterLogNotFoundException(EntityNotFoundException):
    """A requested water log does not exist."""
```

- [ ] **Step 4: Add `client_id` to every entity**

Edit `src/domain/entities/food_entry.py` — add `client_id: str` as a
dataclass field right after `meal_type: MealType` (before the fields with
defaults), validate it in `__post_init__`, and add it as a required
keyword-only parameter to `.create()`:

```python
    meal_type: MealType
    client_id: str
    image_url: str | None = None
```
(rest of the field list unchanged)

```python
    def __post_init__(self) -> None:
        self.name = require_non_empty(self.name, "name")
        for value, label in (
            (self.total_kcal, "total_kcal"),
            (self.carbs_g, "carbs_g"),
            (self.protein_g, "protein_g"),
            (self.fat_g, "fat_g"),
        ):
            require_non_negative(value, label)
        if self.fiber_g is not None:
            require_non_negative(self.fiber_g, "fiber_g")
        self.client_id = require_non_empty(self.client_id, "client_id")

    @classmethod
    def create(
        cls,
        user_id: int,
        name: str,
        input_method: InputMethod,
        total_kcal: int,
        carbs_g: float,
        protein_g: float,
        fat_g: float,
        meal_type: MealType,
        *,
        client_id: str,
        image_url: str | None = None,
        fiber_g: float | None = None,
        ingredients: list[Ingredient] | None = None,
        logged_on: date | None = None,
    ) -> FoodEntry:
        logged_at = datetime.now(UTC)
        return cls(
            id=uuid4(),
            user_id=user_id,
            name=name,
            input_method=input_method,
            total_kcal=total_kcal,
            carbs_g=carbs_g,
            protein_g=protein_g,
            fat_g=fat_g,
            meal_type=meal_type,
            client_id=client_id,
            image_url=image_url,
            fiber_g=fiber_g,
            logged_at=logged_at,
            logged_on=logged_on or logged_at.date(),
            ingredients=ingredients or [],
        )
```

Edit `src/domain/entities/daily_goal.py` — add `require_non_empty` to the
import, `client_id: str` as the last dataclass field, validate it, add
`*, client_id: str` to `.create()`:

```python
from src.domain.validation import require_non_empty, require_positive
```
```python
    target_water_ml: int
    effective_date: date
    client_id: str

    def __post_init__(self) -> None:
        for value, label in (
            (self.target_kcal, "target_kcal"),
            (self.target_carbs_g, "target_carbs_g"),
            (self.target_protein_g, "target_protein_g"),
            (self.target_fat_g, "target_fat_g"),
            (self.target_water_ml, "target_water_ml"),
        ):
            require_positive(value, label)
        self.client_id = require_non_empty(self.client_id, "client_id")

    @classmethod
    def create(
        cls,
        user_id: int,
        target_kcal: int,
        target_carbs_g: float,
        target_protein_g: float,
        target_fat_g: float,
        target_water_ml: int,
        effective_date: date | None = None,
        *,
        client_id: str,
    ) -> DailyGoal:
        return cls(
            id=uuid4(),
            user_id=user_id,
            target_kcal=target_kcal,
            target_carbs_g=target_carbs_g,
            target_protein_g=target_protein_g,
            target_fat_g=target_fat_g,
            target_water_ml=target_water_ml,
            effective_date=effective_date or datetime.now(UTC).date(),
            client_id=client_id,
        )
```

Edit `src/domain/entities/activity_log.py` — add `require_non_empty`
import, `client_id: str` field before `source` (which has a default),
validate, `.create()` gets keyword-only `client_id`:

```python
from src.domain.validation import require_non_empty, require_non_negative
```
```python
    calories_burned: int
    client_id: str
    source: ActivitySource = ActivitySource.MANUAL
    logged_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    logged_on: date = field(default_factory=lambda: datetime.now(UTC).date())

    def __post_init__(self) -> None:
        self.activity_type = require_non_empty(self.activity_type, "activity_type")
        require_non_negative(self.calories_burned, "calories_burned")
        self.client_id = require_non_empty(self.client_id, "client_id")

    @classmethod
    def create(
        cls,
        user_id: int,
        activity_type: str,
        calories_burned: int,
        *,
        client_id: str,
        source: ActivitySource = ActivitySource.MANUAL,
        logged_on: date | None = None,
    ) -> ActivityLog:
        logged_at = datetime.now(UTC)
        return cls(
            id=uuid4(),
            user_id=user_id,
            activity_type=activity_type,
            calories_burned=calories_burned,
            client_id=client_id,
            source=source,
            logged_at=logged_at,
            logged_on=logged_on or logged_at.date(),
        )
```

Edit `src/domain/entities/weight_log.py` — add `require_non_empty` import,
`client_id: str` field, validate, `.create()` gets keyword-only `client_id`:

```python
from src.domain.validation import require_non_empty, require_positive
```
```python
    weight: float
    recorded_at: date
    client_id: str

    def __post_init__(self) -> None:
        require_positive(self.weight, "weight")
        self.client_id = require_non_empty(self.client_id, "client_id")

    @classmethod
    def create(
        cls, user_id: int, weight: float, recorded_at: date | None = None, *, client_id: str
    ) -> WeightLog:
        return cls(
            id=uuid4(),
            user_id=user_id,
            weight=weight,
            recorded_at=recorded_at or datetime.now(UTC).date(),
            client_id=client_id,
        )
```

Edit `src/domain/entities/water_log.py` — add `require_non_empty` import,
`client_id: str` field before `logged_at` (which has a default), validate,
`.create()` gets keyword-only `client_id`:

```python
from src.domain.validation import require_non_empty, require_positive
```
```python
    amount_ml: int
    client_id: str
    logged_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    logged_on: date = field(default_factory=lambda: datetime.now(UTC).date())

    def __post_init__(self) -> None:
        require_positive(self.amount_ml, "amount_ml")
        self.client_id = require_non_empty(self.client_id, "client_id")

    @classmethod
    def create(
        cls, user_id: int, amount_ml: int, *, client_id: str, logged_on: date | None = None
    ) -> WaterLog:
        logged_at = datetime.now(UTC)
        return cls(
            id=uuid4(),
            user_id=user_id,
            amount_ml=amount_ml,
            client_id=client_id,
            logged_at=logged_at,
            logged_on=logged_on or logged_at.date(),
        )
```

- [ ] **Step 5: Add `client_id` (+ `deleted_at` for food-entries) to the ORM models**

Edit `src/infrastructure/db/models/food_entry_model.py` — import
`UniqueConstraint`, add the column + constraint + `to_domain`/`from_domain`
mapping:

```python
from sqlalchemy import Date, DateTime, Float, ForeignKey, Index, Integer, String, UniqueConstraint
```
```python
class FoodEntryORM(UUIDPrimaryKey, UserOwned, Base):
    __tablename__ = "food_entries"
    __table_args__ = (
        Index("ix_food_entries_user_logged_at", "user_id", "logged_at"),
        Index("ix_food_entries_user_logged_on", "user_id", "logged_on"),
        UniqueConstraint("user_id", "client_id", name="uq_food_entries_client_id"),
    )

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    input_method: Mapped[InputMethod] = mapped_column(
        enum_column(InputMethod, "input_method"), nullable=False
    )
    meal_type: Mapped[MealType] = mapped_column(enum_column(MealType, "meal_type"), nullable=False)
    client_id: Mapped[str] = mapped_column(String(64), nullable=False)
    image_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    total_kcal: Mapped[int] = mapped_column(Integer, nullable=False)
    carbs_g: Mapped[float] = mapped_column(Float, nullable=False)
    protein_g: Mapped[float] = mapped_column(Float, nullable=False)
    fat_g: Mapped[float] = mapped_column(Float, nullable=False)
    # Premium-only. NULL means "not tracked", which is not the same as 0.0 g.
    fiber_g: Mapped[float | None] = mapped_column(Float, nullable=True)
    ai_feedback: Mapped[AiFeedback | None] = mapped_column(
        enum_column(AiFeedback, "ai_feedback"), nullable=True
    )
    logged_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    logged_on: Mapped[date] = mapped_column(Date, nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
```

`to_domain()` gains `client_id=self.client_id,` (not `deleted_at` — the
domain entity doesn't carry it; a soft-deleted row is filtered out at the
query layer before `to_domain()` is ever called on it). `from_domain()`
gains `client_id=entry.client_id,`.

Edit `src/infrastructure/db/models/daily_goal_model.py`:
```python
    __table_args__ = (
        UniqueConstraint("user_id", "effective_date", name="uq_daily_goals_user_date"),
        UniqueConstraint("user_id", "client_id", name="uq_daily_goals_client_id"),
    )

    target_kcal: Mapped[int] = mapped_column(Integer, nullable=False)
    target_carbs_g: Mapped[float] = mapped_column(Float, nullable=False)
    target_protein_g: Mapped[float] = mapped_column(Float, nullable=False)
    target_fat_g: Mapped[float] = mapped_column(Float, nullable=False)
    target_water_ml: Mapped[int] = mapped_column(Integer, nullable=False)
    effective_date: Mapped[date] = mapped_column(Date, nullable=False)
    client_id: Mapped[str] = mapped_column(String(64), nullable=False)
```
(add `String` to the `sqlalchemy` import line). `to_domain()`/`from_domain()`
each gain `client_id=self.client_id,` / `client_id=goal.client_id,`.

Edit `src/infrastructure/db/models/activity_log_model.py`:
```python
from sqlalchemy import Date, DateTime, Index, Integer, String, UniqueConstraint
```
```python
    __table_args__ = (
        Index("ix_activity_logs_user_logged_at", "user_id", "logged_at"),
        Index("ix_activity_logs_user_logged_on", "user_id", "logged_on"),
        UniqueConstraint("user_id", "client_id", name="uq_activity_logs_client_id"),
    )

    activity_type: Mapped[str] = mapped_column(String(120), nullable=False)
    calories_burned: Mapped[int] = mapped_column(Integer, nullable=False)
    client_id: Mapped[str] = mapped_column(String(64), nullable=False)
    source: Mapped[ActivitySource] = mapped_column(
        enum_column(ActivitySource, "activity_source"),
        nullable=False,
        server_default=ActivitySource.MANUAL.value,
    )
```
`to_domain()`/`from_domain()` each gain `client_id=self.client_id,` /
`client_id=log.client_id,`.

Edit `src/infrastructure/db/models/weight_log_model.py`:
```python
from sqlalchemy import Date, Float, Index, String, UniqueConstraint
```
```python
    __table_args__ = (
        Index("ix_weight_logs_user_recorded_at", "user_id", "recorded_at"),
        UniqueConstraint("user_id", "client_id", name="uq_weight_logs_client_id"),
    )

    weight: Mapped[float] = mapped_column(Float, nullable=False)
    recorded_at: Mapped[date] = mapped_column(Date, nullable=False)
    client_id: Mapped[str] = mapped_column(String(64), nullable=False)
```
`to_domain()`/`from_domain()` each gain the `client_id=...,` line.

Edit `src/infrastructure/db/models/water_log_model.py`:
```python
from sqlalchemy import Date, DateTime, Index, Integer, String, UniqueConstraint
```
```python
    __table_args__ = (
        Index("ix_water_logs_user_logged_at", "user_id", "logged_at"),
        Index("ix_water_logs_user_logged_on", "user_id", "logged_on"),
        UniqueConstraint("user_id", "client_id", name="uq_water_logs_client_id"),
    )

    amount_ml: Mapped[int] = mapped_column(Integer, nullable=False)
    client_id: Mapped[str] = mapped_column(String(64), nullable=False)
    logged_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    logged_on: Mapped[date] = mapped_column(Date, nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
```
`to_domain()`/`from_domain()` each gain `client_id=...,` (not `deleted_at`,
same reasoning as food_entries).

- [ ] **Step 6: Write the shared idempotency helper**

Create `src/infrastructure/db/repositories/idempotency.py`:

```python
"""Shared idempotent-create helper for tables with a ``(user_id, client_id)``
unique constraint — see
docs/superpowers/specs/2026-09-24-diary-sync-push-design.md.
"""

from __future__ import annotations

from typing import TypeVar

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

_Row = TypeVar("_Row")


async def create_idempotent(session: AsyncSession, row: _Row, model: type[_Row]) -> _Row:
    """Insert ``row``. If its ``(user_id, client_id)`` was already used by an
    earlier request, return that existing row instead of raising — a retried
    request after a dropped response must not create a duplicate. Relies on
    the DB's own unique constraint (race-safe against a concurrent retry),
    not a check-then-insert.

    If the conflict wasn't actually a ``client_id`` repeat (e.g. a different
    unique constraint on the same table fired), the re-query finds nothing
    and the original error is re-raised rather than masked.
    """
    session.add(row)
    try:
        await session.flush()
    except IntegrityError:
        await session.rollback()
        existing = await session.execute(
            select(model).where(model.user_id == row.user_id, model.client_id == row.client_id)
        )
        found = existing.scalar_one_or_none()
        if found is None:
            raise
        return found
    await session.refresh(row)
    return row
```

- [ ] **Step 7: Wire idempotency + soft delete into the food-entry repository**

Edit `src/infrastructure/db/repositories/food_entry_repository.py`:

```python
"""Concrete ``FoodEntryRepositoryProtocol`` implementation backed by async SQLAlchemy."""

from __future__ import annotations

from datetime import date
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.entities.food_entry import FoodEntry
from src.infrastructure.db.models.food_entry_model import FoodEntryORM
from src.infrastructure.db.repositories.idempotency import create_idempotent


class SQLAlchemyFoodEntryRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, entry: FoodEntry) -> FoodEntry:
        row = await create_idempotent(self._session, FoodEntryORM.from_domain(entry), FoodEntryORM)
        return row.to_domain()

    async def get_by_id(self, entry_id: UUID) -> FoodEntry | None:
        row = await self._session.get(FoodEntryORM, entry_id)
        if row is None or row.deleted_at is not None:
            return None
        return row.to_domain()

    async def list_by_date_range(
        self, user_id: int, from_date: date, to_date: date
    ) -> list[FoodEntry]:
        rows = (
            await self._session.execute(
                select(FoodEntryORM).where(
                    FoodEntryORM.user_id == user_id,
                    FoodEntryORM.logged_on >= from_date,
                    FoodEntryORM.logged_on <= to_date,
                    FoodEntryORM.deleted_at.is_(None),
                )
            )
        ).scalars().all()
        return [row.to_domain() for row in rows]
```

- [ ] **Step 8: Thread `client_id` through the food-entry create path**

Edit `src/application/dtos/food_entry.py` — add `client_id: str` to
`CreateFoodEntryInputDTO`, right after `meal_type`:

```python
@dataclass(frozen=True)
class CreateFoodEntryInputDTO:
    user_id: int
    name: str
    input_method: InputMethod
    total_kcal: int
    carbs_g: float
    protein_g: float
    fat_g: float
    meal_type: MealType
    client_id: str
    image_url: str | None = None
    fiber_g: float | None = None
    ingredients: list[CreateIngredientInputDTO] | None = None
    logged_on: date | None = None
```

Edit `src/adapters/schemas/food_entry_schemas.py` — add `client_id` to
`CreateFoodEntryRequest`, same position:

```python
class CreateFoodEntryRequest(CamelModel):
    name: str = Field(min_length=1)
    input_method: InputMethod
    total_kcal: int
    carbs_g: float
    protein_g: float
    fat_g: float
    meal_type: MealType
    client_id: str = Field(min_length=1)
    image_url: str | None = None
    fiber_g: float | None = None
    ingredients: list[CreateIngredientRequest] = Field(default_factory=list)
    logged_on: date | None = None
```

Edit `src/application/use_cases/create_food_entry.py` — pass `client_id`
through to `FoodEntry.create()`:

```python
        entry = FoodEntry.create(
            user_id=input_dto.user_id,
            name=input_dto.name,
            input_method=input_dto.input_method,
            total_kcal=input_dto.total_kcal,
            carbs_g=input_dto.carbs_g,
            protein_g=input_dto.protein_g,
            fat_g=input_dto.fat_g,
            meal_type=input_dto.meal_type,
            client_id=input_dto.client_id,
            image_url=input_dto.image_url,
            fiber_g=input_dto.fiber_g,
            logged_on=input_dto.logged_on,
        )
```

Edit `src/adapters/controllers/food_entry_controller.py` — pass
`client_id` in `create_food_entry`:

```python
    input_dto = CreateFoodEntryInputDTO(
        user_id=user.id,
        name=body.name,
        input_method=body.input_method,
        total_kcal=body.total_kcal,
        carbs_g=body.carbs_g,
        protein_g=body.protein_g,
        fat_g=body.fat_g,
        meal_type=body.meal_type,
        client_id=body.client_id,
        image_url=body.image_url,
        fiber_g=body.fiber_g,
        logged_on=body.logged_on,
        ingredients=[...],  # unchanged
    )
```

- [ ] **Step 9: Fix every existing call site broken by the new required `client_id`**

`client_id` is now required everywhere these entities are constructed
directly. Fix each:

`tests/unit/test_entities.py`:
- Line 71–82 (`_food_entry()`): add `client_id="entry_1",` right after
  `meal_type=MealType.LUNCH,`.
- Line 96: `DailyGoal.create(USER_ID, 2000, 200.0, 150.0, 60.0, 2500, TODAY)`
  → `DailyGoal.create(USER_ID, 2000, 200.0, 150.0, 60.0, 2500, TODAY, client_id="goal_1")`.
- Line 99: `ActivityLog.create(USER_ID, "running", 320, ActivitySource.APPLE_HEALTH)`
  → `ActivityLog.create(USER_ID, "running", 320, client_id="activity_1", source=ActivitySource.APPLE_HEALTH)`.
- Line 100: `WeightLog.create(USER_ID, 60.4, TODAY)`
  → `WeightLog.create(USER_ID, 60.4, TODAY, client_id="weight_1")`.
- Line 101: `WaterLog.create(USER_ID, 350)`
  → `WaterLog.create(USER_ID, 350, client_id="water_1")`.
- Line 148–157 (`test_food_entry_rejects_blank_name`): add
  `client_id="entry_1",` after `meal_type=MealType.LUNCH,`.
- Line 167: `WaterLog.create(USER_ID, 0)`
  → `WaterLog.create(USER_ID, 0, client_id="water_1")`.

`tests/unit/test_list_daily_goals_use_case.py` lines 25–26: add
`, client_id="goal_1"` / `, client_id="goal_2"` to each call.

`tests/unit/test_list_diary_log_use_cases.py`:
- Line 58: `ActivityLog.create(1, "running", 320, logged_on=date(2026, 1, 15))`
  → add `client_id="activity_1", `.
- Line 73: `WaterLog.create(1, 350, logged_on=date(2026, 1, 15))`
  → add `client_id="water_1", `.
- Line 87: `WeightLog.create(1, 60.4, date(2026, 1, 15))`
  → `WeightLog.create(1, 60.4, date(2026, 1, 15), client_id="weight_1")`.

`tests/api/test_daily_goal_endpoints.py` line 32: add `client_id="goal_1"`
as the last kwarg to `DailyGoal.create(...)`.

`tests/api/test_activity_log_endpoints.py` line 42: add
`client_id="activity_1"` as the last kwarg to `ActivityLog.create(...)`.

`tests/api/test_weight_log_endpoints.py` line 32: add `client_id="weight_1"`
as the last kwarg to `WeightLog.create(...)`.

`tests/api/test_water_log_endpoints.py` line 33: add `client_id="water_1"`
as the last kwarg to `WaterLog.create(...)`.

`tests/api/test_food_entry_endpoints.py`: add `"clientId": "entry_1",` to
the shared `_BODY` dict (after `"mealType": "lunch",`), so every test in
this file keeps working since they all reuse `_BODY`.

`tests/integration/test_food_entry_repository.py` line 55–66
(`_entry_with_ingredients`): add `client_id="entry_1",` after
`meal_type=MealType.LUNCH,`.

`tests/integration/test_diary_sync_repositories.py`:
- Line 74–79 (`DailyGoal.create` x2): add `client_id="goal_1"` /
  `client_id="goal_2"`.
- Line 93–104 (`_entry()` helper): add `client_id="entry_1",` after
  `meal_type=MealType.LUNCH,` — note this helper is called 4 times with
  different `user_id`/`logged_on`, all sharing `client_id="entry_1"`; since
  the unique constraint is per-`user_id`, this is fine for the 3 same-user
  calls only if they'd collide — check: all 3 same-user calls in
  `test_food_entry_repository_list_by_date_range_is_inclusive_and_scoped`
  insert via `repo.create()`, which is now idempotent — three calls with
  the **same** `client_id` for `user_a` would collide and return the same
  row 3 times instead of creating 3! Give each call a distinct `client_id`
  instead: change `_entry()` to accept a `client_id` parameter and pass
  `"entry_1"`/`"entry_2"`/`"entry_3"` at each of the three `user_a` call
  sites (the `user_b` call can reuse `"entry_1"` — different user, no
  collision).
- Line 137–140 (`ActivityLog.create` x4): add distinct `client_id=`
  values for the 3 `user_a` calls (`"activity_1"`, `"activity_2"`,
  `"activity_3"`) and `client_id="activity_1"` for the `user_b` call.
- Line 155–158 (`WaterLog.create` x4): same pattern with `"water_1"` /
  `"water_2"` / `"water_3"` / `"water_1"`.
- Line 173–176 (`WeightLog.create` x4): same pattern with `"weight_1"` /
  `"weight_2"` / `"weight_3"` / `"weight_1"`.

(These particular list-by-date-range tests don't go through the idempotent
`create()` path for activity/water/weight logs — they build ORM rows
directly via `_orm()`/`session.add()` — so a repeated `client_id` there
would only violate the DB unique constraint at `session.flush()`, not
silently merge rows. Either way, give each row its own `client_id` to avoid
the constraint violation entirely.)

- [ ] **Step 10: Add the idempotency + soft-delete tests**

Add to `tests/unit/test_entities.py` (new tests, anywhere after the
existing invariant tests):

```python
def test_food_entry_rejects_blank_client_id():
    with pytest.raises(InvalidAttributeException):
        FoodEntry.create(
            user_id=USER_ID,
            name="Snack",
            input_method=InputMethod.MANUAL,
            total_kcal=100,
            carbs_g=10.0,
            protein_g=5.0,
            fat_g=2.0,
            meal_type=MealType.SNACK,
            client_id="   ",
        )
```

Add to `tests/integration/test_food_entry_repository.py` (new test):

```python
async def test_create_with_a_repeated_client_id_returns_the_existing_row_not_a_duplicate(session):
    user = await _make_user(session)
    repo = SQLAlchemyFoodEntryRepository(session)

    first = await repo.create(_entry_with_ingredients(user.id))
    await session.commit()

    retry = _entry_with_ingredients(user.id)  # same client_id="entry_1", different id
    second = await repo.create(retry)
    await session.commit()

    assert second.id == first.id
    rows = (
        await session.execute(select(func.count()).select_from(FoodEntryORM))
    ).scalar_one()
    assert rows == 1
```

Add `from sqlalchemy import func, select` to that file's imports (neither
is currently imported there — check first).

Verify this test actually exercises the idempotency path, not just
accidentally passing: temporarily change
`src/infrastructure/db/repositories/idempotency.py`'s `except IntegrityError:`
to `except TypeError:` (so the real `IntegrityError` propagates unhandled
instead of being caught), run the test, confirm it now fails with an
unhandled `IntegrityError` (proving the original except clause was load-bearing),
then revert the change.

Add to `tests/api/test_food_entry_endpoints.py` (new tests):

```python
async def test_posting_the_same_client_id_twice_returns_the_same_entry(client, signed_up):
    headers = {"Authorization": f"Bearer {signed_up['accessToken']}"}

    first = (await client.post("/food-entries", json=_BODY, headers=headers)).json()
    second = (await client.post("/food-entries", json=_BODY, headers=headers)).json()

    assert first["id"] == second["id"]


async def test_create_requires_client_id(client, signed_up):
    headers = {"Authorization": f"Bearer {signed_up['accessToken']}"}
    body = {k: v for k, v in _BODY.items() if k != "clientId"}

    resp = await client.post("/food-entries", json=body, headers=headers)

    assert resp.status_code == 422
```

- [ ] **Step 11: Run the full suite and import-linter**

```bash
uv run pytest tests/unit -q
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5433/foodfen_test uv run pytest tests/integration tests/api -q
uv run lint-imports
```
Expected: all green, no import-contract violations.

- [ ] **Step 12: Commit**

```bash
git add alembic/versions/0011_diary_sync_push_fields.py \
  src/infrastructure/db/repositories/idempotency.py \
  src/domain/exceptions.py \
  src/domain/entities/food_entry.py src/domain/entities/daily_goal.py \
  src/domain/entities/activity_log.py src/domain/entities/weight_log.py \
  src/domain/entities/water_log.py \
  src/infrastructure/db/models/food_entry_model.py \
  src/infrastructure/db/models/daily_goal_model.py \
  src/infrastructure/db/models/activity_log_model.py \
  src/infrastructure/db/models/weight_log_model.py \
  src/infrastructure/db/models/water_log_model.py \
  src/infrastructure/db/repositories/food_entry_repository.py \
  src/application/dtos/food_entry.py \
  src/adapters/schemas/food_entry_schemas.py \
  src/adapters/controllers/food_entry_controller.py \
  tests/unit/test_entities.py tests/unit/test_list_daily_goals_use_case.py \
  tests/unit/test_list_diary_log_use_cases.py \
  tests/api/test_daily_goal_endpoints.py tests/api/test_activity_log_endpoints.py \
  tests/api/test_weight_log_endpoints.py tests/api/test_water_log_endpoints.py \
  tests/api/test_food_entry_endpoints.py \
  tests/integration/test_food_entry_repository.py \
  tests/integration/test_diary_sync_repositories.py
git commit -m "feat: add client_id idempotency + soft-delete foundation, wired into POST /food-entries"
```

---

## Task 2: Food entries — PATCH + DELETE

**Files:**
- Modify: `src/application/ports/food_entry_repository.py`
- Modify: `src/infrastructure/db/repositories/food_entry_repository.py`
- Modify: `src/application/dtos/food_entry.py`
- Create: `src/application/use_cases/update_food_entry.py`
- Create: `src/application/use_cases/delete_food_entry.py`
- Modify: `src/adapters/schemas/food_entry_schemas.py`
- Modify: `src/adapters/controllers/food_entry_controller.py`
- Modify: `src/infrastructure/di/use_cases.py`, `src/infrastructure/di/__init__.py`
- Test: `tests/unit/test_food_entry_use_cases.py`
- Test: `tests/integration/test_food_entry_repository.py`
- Test: `tests/api/test_food_entry_endpoints.py`

**Interfaces:**
- Consumes: `create_idempotent` (Task 1), `FoodEntryNotFoundException`
  (existing).
- Produces: `FoodEntryRepositoryProtocol.update(entry: FoodEntry) -> FoodEntry`,
  `.delete(entry_id: UUID) -> None`; `UpdateFoodEntryUseCase.execute(user_id, entry_id, input_dto) -> FoodEntryOutputDTO`,
  `DeleteFoodEntryUseCase.execute(user_id, entry_id) -> None`.

- [ ] **Step 1: Extend the repository port**

Edit `src/application/ports/food_entry_repository.py`:

```python
class FoodEntryRepositoryProtocol(Protocol):
    async def create(self, entry: FoodEntry) -> FoodEntry: ...

    async def get_by_id(self, entry_id: UUID) -> FoodEntry | None: ...

    async def list_by_date_range(
        self, user_id: int, from_date: date, to_date: date
    ) -> list[FoodEntry]:
        """Inclusive range, filtered on ``logged_on``."""
        ...

    async def update(self, entry: FoodEntry) -> FoodEntry:
        """Full replace, including ``ingredients``. Raise
        ``FoodEntryNotFoundException`` if ``entry.id`` doesn't exist or is
        soft-deleted."""
        ...

    async def delete(self, entry_id: UUID) -> None:
        """Soft delete. Raise ``FoodEntryNotFoundException`` if it doesn't
        exist or is already deleted."""
        ...
```

- [ ] **Step 2: Write the failing repository tests**

Add to `tests/integration/test_food_entry_repository.py`:

```python
from datetime import UTC, datetime

from src.domain.exceptions import FoodEntryNotFoundException


async def test_update_replaces_scalar_fields_and_ingredients(session):
    user = await _make_user(session)
    repo = SQLAlchemyFoodEntryRepository(session)
    created = await repo.create(_entry_with_ingredients(user.id))
    await session.commit()

    replacement = FoodEntry(
        id=created.id,
        user_id=user.id,
        name="Different meal",
        input_method=InputMethod.MANUAL,
        total_kcal=800,
        carbs_g=90.0,
        protein_g=50.0,
        fat_g=20.0,
        meal_type=MealType.DINNER,
        client_id=created.client_id,
        ingredients=[Ingredient.create(created.id, "tofu", 100.0, 80, 5.0, 8.0, 4.0)],
    )
    updated = await repo.update(replacement)
    await session.commit()

    assert updated.name == "Different meal"
    assert updated.meal_type == MealType.DINNER
    assert [i.name for i in updated.ingredients] == ["tofu"]


async def test_update_raises_not_found_for_a_missing_entry(session):
    from uuid import uuid4

    repo = SQLAlchemyFoodEntryRepository(session)
    ghost = FoodEntry(
        id=uuid4(),
        user_id=1,
        name="Ghost",
        input_method=InputMethod.MANUAL,
        total_kcal=1,
        carbs_g=1.0,
        protein_g=1.0,
        fat_g=1.0,
        meal_type=MealType.SNACK,
        client_id="ghost",
    )
    with pytest.raises(FoodEntryNotFoundException):
        await repo.update(ghost)


async def test_delete_soft_deletes_and_get_by_id_stops_returning_it(session):
    user = await _make_user(session)
    repo = SQLAlchemyFoodEntryRepository(session)
    created = await repo.create(_entry_with_ingredients(user.id))
    await session.commit()

    await repo.delete(created.id)
    await session.commit()

    assert await repo.get_by_id(created.id) is None


async def test_delete_on_an_already_deleted_entry_raises_not_found(session):
    user = await _make_user(session)
    repo = SQLAlchemyFoodEntryRepository(session)
    created = await repo.create(_entry_with_ingredients(user.id))
    await session.commit()
    await repo.delete(created.id)
    await session.commit()

    with pytest.raises(FoodEntryNotFoundException):
        await repo.delete(created.id)
```

Add `import pytest` at the top of the file if not already present (it
isn't — check first).

- [ ] **Step 3: Run to verify the new tests fail**

```bash
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5433/foodfen_test uv run pytest tests/integration/test_food_entry_repository.py -k "update or delete" -v
```
Expected: FAIL — `AttributeError: 'SQLAlchemyFoodEntryRepository' object has no attribute 'update'`.

- [ ] **Step 4: Implement `update`/`delete` on the repository**

Edit `src/infrastructure/db/repositories/food_entry_repository.py`, add
imports and two methods:

```python
from datetime import UTC, date, datetime

from src.domain.exceptions import FoodEntryNotFoundException
```

```python
    async def update(self, entry: FoodEntry) -> FoodEntry:
        row = await self._session.get(FoodEntryORM, entry.id)
        if row is None or row.deleted_at is not None:
            raise FoodEntryNotFoundException(f"no food entry {entry.id}")
        fresh = FoodEntryORM.from_domain(entry)
        for column in FoodEntryORM.__table__.columns.keys():
            if column not in ("id", "deleted_at"):
                setattr(row, column, getattr(fresh, column))
        row.ingredients = fresh.ingredients
        await self._session.flush()
        await self._session.refresh(row)
        return row.to_domain()

    async def delete(self, entry_id: UUID) -> None:
        row = await self._session.get(FoodEntryORM, entry_id)
        if row is None or row.deleted_at is not None:
            raise FoodEntryNotFoundException(f"no food entry {entry_id}")
        row.deleted_at = datetime.now(UTC)
        await self._session.flush()
```

- [ ] **Step 5: Run to verify the repository tests pass**

```bash
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5433/foodfen_test uv run pytest tests/integration/test_food_entry_repository.py -v
```
Expected: PASS, all tests in the file.

- [ ] **Step 6: Add the update DTO**

Edit `src/application/dtos/food_entry.py`, append:

```python
@dataclass(frozen=True)
class UpdateFoodEntryInputDTO:
    name: str
    input_method: InputMethod
    total_kcal: int
    carbs_g: float
    protein_g: float
    fat_g: float
    meal_type: MealType
    image_url: str | None = None
    fiber_g: float | None = None
    ingredients: list[CreateIngredientInputDTO] | None = None
    logged_on: date | None = None
```

- [ ] **Step 7: Write the failing use-case unit tests**

Add to `tests/unit/test_food_entry_use_cases.py`:

```python
from src.application.dtos.food_entry import UpdateFoodEntryInputDTO
from src.application.use_cases.delete_food_entry import DeleteFoodEntryUseCase
from src.application.use_cases.update_food_entry import UpdateFoodEntryUseCase


class FakeFoodEntryRepoWithUpdateDelete(FakeFoodEntryRepo):
    async def update(self, entry):
        if entry.id not in self._by_id or self._by_id[entry.id] is None:
            raise FoodEntryNotFoundException(f"no food entry {entry.id}")
        self._by_id[entry.id] = entry
        return entry

    async def delete(self, entry_id):
        if self._by_id.get(entry_id) is None:
            raise FoodEntryNotFoundException(f"no food entry {entry_id}")
        self._by_id[entry_id] = None


def _update_dto(meal_type=MealType.DINNER) -> UpdateFoodEntryInputDTO:
    return UpdateFoodEntryInputDTO(
        name="Updated meal",
        input_method=InputMethod.MANUAL,
        total_kcal=700,
        carbs_g=60.0,
        protein_g=50.0,
        fat_g=20.0,
        meal_type=meal_type,
    )


async def test_update_replaces_fields_for_the_owner():
    repo = FakeFoodEntryRepoWithUpdateDelete()
    created = await CreateFoodEntryUseCase(food_entries=repo).execute(_input_dto())

    use_case = UpdateFoodEntryUseCase(food_entries=repo)
    result = await use_case.execute(user_id=1, entry_id=created.id, input_dto=_update_dto())

    assert result.name == "Updated meal"
    assert result.meal_type is MealType.DINNER


async def test_update_raises_not_found_for_another_users_entry():
    repo = FakeFoodEntryRepoWithUpdateDelete()
    created = await CreateFoodEntryUseCase(food_entries=repo).execute(_input_dto())

    use_case = UpdateFoodEntryUseCase(food_entries=repo)
    with pytest.raises(FoodEntryNotFoundException):
        await use_case.execute(user_id=999, entry_id=created.id, input_dto=_update_dto())


async def test_delete_removes_the_owners_entry():
    repo = FakeFoodEntryRepoWithUpdateDelete()
    created = await CreateFoodEntryUseCase(food_entries=repo).execute(_input_dto())

    use_case = DeleteFoodEntryUseCase(food_entries=repo)
    await use_case.execute(user_id=1, entry_id=created.id)

    assert await repo.get_by_id(created.id) is None


async def test_delete_raises_not_found_for_another_users_entry():
    repo = FakeFoodEntryRepoWithUpdateDelete()
    created = await CreateFoodEntryUseCase(food_entries=repo).execute(_input_dto())

    use_case = DeleteFoodEntryUseCase(food_entries=repo)
    with pytest.raises(FoodEntryNotFoundException):
        await use_case.execute(user_id=999, entry_id=created.id)
```

- [ ] **Step 8: Run to verify the new tests fail**

```bash
uv run pytest tests/unit/test_food_entry_use_cases.py -k "update or delete" -v
```
Expected: FAIL — `ModuleNotFoundError: No module named 'src.application.use_cases.update_food_entry'`.

- [ ] **Step 9: Implement the use cases**

Create `src/application/use_cases/update_food_entry.py`:

```python
"""Use case: full-replace an existing food entry (incl. its ingredients).

Ownership check mirrors ``GetFoodEntryUseCase``: "doesn't exist" and
"belongs to someone else" both raise the same not-found exception so
existence isn't leaked.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from src.application.dtos.food_entry import UpdateFoodEntryInputDTO, FoodEntryOutputDTO
from src.application.ports.food_entry_repository import FoodEntryRepositoryProtocol
from src.domain.entities.food_entry import FoodEntry
from src.domain.entities.ingredient import Ingredient
from src.domain.exceptions import FoodEntryNotFoundException


@dataclass
class UpdateFoodEntryUseCase:
    food_entries: FoodEntryRepositoryProtocol

    async def execute(
        self, user_id: int, entry_id: UUID, input_dto: UpdateFoodEntryInputDTO
    ) -> FoodEntryOutputDTO:
        existing = await self.food_entries.get_by_id(entry_id)
        if existing is None or existing.user_id != user_id:
            raise FoodEntryNotFoundException(f"no food entry {entry_id}")

        entry = FoodEntry(
            id=entry_id,
            user_id=user_id,
            name=input_dto.name,
            input_method=input_dto.input_method,
            total_kcal=input_dto.total_kcal,
            carbs_g=input_dto.carbs_g,
            protein_g=input_dto.protein_g,
            fat_g=input_dto.fat_g,
            meal_type=input_dto.meal_type,
            client_id=existing.client_id,
            image_url=input_dto.image_url,
            fiber_g=input_dto.fiber_g,
            ai_feedback=existing.ai_feedback,
            logged_at=existing.logged_at,
            logged_on=input_dto.logged_on or existing.logged_on,
            ingredients=[
                Ingredient.create(
                    food_entry_id=entry_id,
                    name=i.name,
                    quantity_g=i.quantity_g,
                    kcal=i.kcal,
                    carbs_g=i.carbs_g,
                    protein_g=i.protein_g,
                    fat_g=i.fat_g,
                    fiber_g=i.fiber_g,
                )
                for i in (input_dto.ingredients or [])
            ],
        )
        updated = await self.food_entries.update(entry)
        return FoodEntryOutputDTO.from_entity(updated)
```

Create `src/application/use_cases/delete_food_entry.py`:

```python
"""Use case: soft-delete a food entry."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from src.application.ports.food_entry_repository import FoodEntryRepositoryProtocol
from src.domain.exceptions import FoodEntryNotFoundException


@dataclass
class DeleteFoodEntryUseCase:
    food_entries: FoodEntryRepositoryProtocol

    async def execute(self, user_id: int, entry_id: UUID) -> None:
        existing = await self.food_entries.get_by_id(entry_id)
        if existing is None or existing.user_id != user_id:
            raise FoodEntryNotFoundException(f"no food entry {entry_id}")
        await self.food_entries.delete(entry_id)
```

- [ ] **Step 10: Run to verify the use-case tests pass**

```bash
uv run pytest tests/unit/test_food_entry_use_cases.py -v
```
Expected: PASS, all tests in the file.

- [ ] **Step 11: Add the request/response schema and controller routes**

Edit `src/adapters/schemas/food_entry_schemas.py`, append:

```python
class UpdateFoodEntryRequest(CamelModel):
    name: str = Field(min_length=1)
    input_method: InputMethod
    total_kcal: int
    carbs_g: float
    protein_g: float
    fat_g: float
    meal_type: MealType
    image_url: str | None = None
    fiber_g: float | None = None
    ingredients: list[CreateIngredientRequest] = Field(default_factory=list)
    logged_on: date | None = None
```

Edit `src/adapters/controllers/food_entry_controller.py`:

```python
from src.adapters.schemas.food_entry_schemas import (
    CreateFoodEntryRequest,
    FoodEntryResponse,
    UpdateFoodEntryRequest,
)
from src.application.dtos.food_entry import (
    CreateFoodEntryInputDTO,
    CreateIngredientInputDTO,
    UpdateFoodEntryInputDTO,
)
from src.infrastructure.di import (
    CreateFoodEntryUseCaseDep,
    CurrentUserDep,
    DeleteFoodEntryUseCaseDep,
    GetFoodEntryUseCaseDep,
    ListFoodEntriesUseCaseDep,
    UpdateFoodEntryUseCaseDep,
)
```

Append two routes at the end of the file:

```python
@router.patch("/{entry_id}", response_model=FoodEntryResponse)
async def update_food_entry(
    entry_id: UUID,
    body: UpdateFoodEntryRequest,
    user: CurrentUserDep,
    use_case: UpdateFoodEntryUseCaseDep,
) -> FoodEntryResponse:
    input_dto = UpdateFoodEntryInputDTO(
        name=body.name,
        input_method=body.input_method,
        total_kcal=body.total_kcal,
        carbs_g=body.carbs_g,
        protein_g=body.protein_g,
        fat_g=body.fat_g,
        meal_type=body.meal_type,
        image_url=body.image_url,
        fiber_g=body.fiber_g,
        logged_on=body.logged_on,
        ingredients=[
            CreateIngredientInputDTO(
                name=i.name,
                quantity_g=i.quantity_g,
                kcal=i.kcal,
                carbs_g=i.carbs_g,
                protein_g=i.protein_g,
                fat_g=i.fat_g,
                fiber_g=i.fiber_g,
            )
            for i in body.ingredients
        ],
    )
    result = await use_case.execute(user_id=user.id, entry_id=entry_id, input_dto=input_dto)
    return FoodEntryResponse.from_dto(result)


@router.delete("/{entry_id}", status_code=204)
async def delete_food_entry(
    entry_id: UUID, user: CurrentUserDep, use_case: DeleteFoodEntryUseCaseDep
) -> None:
    await use_case.execute(user_id=user.id, entry_id=entry_id)
```

- [ ] **Step 12: Wire DI**

Edit `src/infrastructure/di/use_cases.py`:

```python
from src.application.use_cases.delete_food_entry import DeleteFoodEntryUseCase
from src.application.use_cases.update_food_entry import UpdateFoodEntryUseCase
```

```python
def get_update_food_entry_use_case(
    food_entries: FoodEntryRepositoryDep,
) -> UpdateFoodEntryUseCase:
    return UpdateFoodEntryUseCase(food_entries=food_entries)


def get_delete_food_entry_use_case(
    food_entries: FoodEntryRepositoryDep,
) -> DeleteFoodEntryUseCase:
    return DeleteFoodEntryUseCase(food_entries=food_entries)


UpdateFoodEntryUseCaseDep = Annotated[
    UpdateFoodEntryUseCase, Depends(get_update_food_entry_use_case)
]
DeleteFoodEntryUseCaseDep = Annotated[
    DeleteFoodEntryUseCase, Depends(get_delete_food_entry_use_case)
]
```

Edit `src/infrastructure/di/__init__.py` — add
`UpdateFoodEntryUseCaseDep`, `DeleteFoodEntryUseCaseDep`,
`get_update_food_entry_use_case`, `get_delete_food_entry_use_case` to the
`from src.infrastructure.di.use_cases import (...)` block and the
`__all__` list (alphabetical, matching the existing style).

- [ ] **Step 13: Write the failing API tests**

Add to `tests/api/test_food_entry_endpoints.py`:

```python
async def test_patch_replaces_the_entry(client, signed_up):
    headers = {"Authorization": f"Bearer {signed_up['accessToken']}"}
    created = (await client.post("/food-entries", json=_BODY, headers=headers)).json()

    patch_body = {**_BODY, "name": "Changed", "mealType": "dinner"}
    resp = await client.patch(f"/food-entries/{created['id']}", json=patch_body, headers=headers)

    assert resp.status_code == 200
    assert resp.json()["name"] == "Changed"
    assert resp.json()["mealType"] == "dinner"


async def test_patch_rejects_another_users_entry(client, signed_up):
    headers = {"Authorization": f"Bearer {signed_up['accessToken']}"}
    created = (await client.post("/food-entries", json=_BODY, headers=headers)).json()
    other = await client.post(
        "/auth/sign-up",
        json={"email": "patcher@example.com", "password": "s3cret-pass", "displayName": "Other"},
    )
    other_headers = {"Authorization": f"Bearer {other.json()['accessToken']}"}

    resp = await client.patch(
        f"/food-entries/{created['id']}", json=_BODY, headers=other_headers
    )
    assert resp.status_code == 404


async def test_delete_soft_deletes_and_it_disappears_from_get_and_list(client, signed_up):
    headers = {"Authorization": f"Bearer {signed_up['accessToken']}"}
    created = (await client.post("/food-entries", json=_BODY, headers=headers)).json()

    resp = await client.delete(f"/food-entries/{created['id']}", headers=headers)
    assert resp.status_code == 204

    assert (await client.get(f"/food-entries/{created['id']}", headers=headers)).status_code == 404

    list_resp = await client.get(
        "/food-entries",
        params={"from": created["loggedOn"], "to": created["loggedOn"]},
        headers=headers,
    )
    assert list_resp.json() == []


async def test_delete_twice_returns_404_the_second_time(client, signed_up):
    headers = {"Authorization": f"Bearer {signed_up['accessToken']}"}
    created = (await client.post("/food-entries", json=_BODY, headers=headers)).json()
    await client.delete(f"/food-entries/{created['id']}", headers=headers)

    resp = await client.delete(f"/food-entries/{created['id']}", headers=headers)
    assert resp.status_code == 404


async def test_patch_after_delete_returns_404(client, signed_up):
    headers = {"Authorization": f"Bearer {signed_up['accessToken']}"}
    created = (await client.post("/food-entries", json=_BODY, headers=headers)).json()
    await client.delete(f"/food-entries/{created['id']}", headers=headers)

    resp = await client.patch(f"/food-entries/{created['id']}", json=_BODY, headers=headers)
    assert resp.status_code == 404


async def test_delete_rejects_another_users_entry(client, signed_up):
    headers = {"Authorization": f"Bearer {signed_up['accessToken']}"}
    created = (await client.post("/food-entries", json=_BODY, headers=headers)).json()
    other = await client.post(
        "/auth/sign-up",
        json={"email": "deleter@example.com", "password": "s3cret-pass", "displayName": "Other"},
    )
    other_headers = {"Authorization": f"Bearer {other.json()['accessToken']}"}

    resp = await client.delete(f"/food-entries/{created['id']}", headers=other_headers)
    assert resp.status_code == 404
```

- [ ] **Step 14: Run to verify, then run the full suite**

```bash
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5433/foodfen_test uv run pytest tests/api/test_food_entry_endpoints.py -v
uv run pytest tests/unit -q
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5433/foodfen_test uv run pytest tests/integration tests/api -q
uv run lint-imports
```
Expected: all green.

- [ ] **Step 15: Commit**

```bash
git add src/application/ports/food_entry_repository.py \
  src/infrastructure/db/repositories/food_entry_repository.py \
  src/application/dtos/food_entry.py \
  src/application/use_cases/update_food_entry.py \
  src/application/use_cases/delete_food_entry.py \
  src/adapters/schemas/food_entry_schemas.py \
  src/adapters/controllers/food_entry_controller.py \
  src/infrastructure/di/use_cases.py src/infrastructure/di/__init__.py \
  tests/unit/test_food_entry_use_cases.py \
  tests/integration/test_food_entry_repository.py \
  tests/api/test_food_entry_endpoints.py
git commit -m "feat: add PATCH/DELETE /food-entries/{id}"
```

---

## Task 3: Activity logs — POST + PATCH

**Files:**
- Modify: `src/application/ports/activity_log_repository.py`
- Modify: `src/infrastructure/db/repositories/activity_log_repository.py`
- Modify: `src/application/dtos/activity_log.py`
- Create: `src/application/use_cases/create_activity_log.py`
- Create: `src/application/use_cases/update_activity_log.py`
- Modify: `src/adapters/schemas/activity_log_schemas.py`
- Modify: `src/adapters/controllers/activity_log_controller.py`
- Modify: `src/infrastructure/di/use_cases.py`, `src/infrastructure/di/__init__.py`
- Test: create `tests/unit/test_activity_log_use_cases.py`
- Test: `tests/integration/test_diary_sync_repositories.py`
- Test: `tests/api/test_activity_log_endpoints.py`

**Interfaces:**
- Consumes: `create_idempotent`, `ActivityLogNotFoundException` (Task 1).
- Produces: `ActivityLogRepositoryProtocol.create()`, `.get_by_id()`,
  `.update()`; `CreateActivityLogUseCase.execute(input_dto) -> ActivityLogOutputDTO`,
  `UpdateActivityLogUseCase.execute(user_id, log_id, input_dto) -> ActivityLogOutputDTO`.

- [ ] **Step 1: Extend the repository port**

Edit `src/application/ports/activity_log_repository.py`:

```python
"""Persistence port for activity logs. Structural typing via Protocol."""

from __future__ import annotations

from datetime import date
from typing import Protocol
from uuid import UUID

from src.domain.entities.activity_log import ActivityLog


class ActivityLogRepositoryProtocol(Protocol):
    async def create(self, log: ActivityLog) -> ActivityLog: ...

    async def get_by_id(self, log_id: UUID) -> ActivityLog | None: ...

    async def update(self, log: ActivityLog) -> ActivityLog:
        """Full replace. Raise ``ActivityLogNotFoundException`` if missing."""
        ...

    async def list_by_date_range(
        self, user_id: int, from_date: date, to_date: date
    ) -> list[ActivityLog]:
        """Inclusive range, filtered on ``logged_on``."""
        ...
```

- [ ] **Step 2: Write the failing repository tests**

Add to `tests/integration/test_diary_sync_repositories.py`:

```python
from src.domain.enums import ActivitySource
from src.domain.exceptions import ActivityLogNotFoundException


async def test_activity_log_repository_create_is_idempotent_on_client_id(session):
    user_a, _ = await _make_two_users(session)
    repo = SQLAlchemyActivityLogRepository(session)

    first = await repo.create(
        ActivityLog.create(user_a.id, "running", 300, client_id="dup", logged_on=date(2026, 1, 1))
    )
    await session.commit()
    second = await repo.create(
        ActivityLog.create(user_a.id, "cycling", 999, client_id="dup", logged_on=date(2026, 1, 2))
    )
    await session.commit()

    assert second.id == first.id
    assert second.activity_type == "running"  # unchanged: the retry was ignored, not applied


async def test_activity_log_repository_update_replaces_fields(session):
    user_a, _ = await _make_two_users(session)
    repo = SQLAlchemyActivityLogRepository(session)
    created = await repo.create(
        ActivityLog.create(user_a.id, "running", 300, client_id="a1", logged_on=date(2026, 1, 1))
    )
    await session.commit()

    replacement = ActivityLog(
        id=created.id,
        user_id=user_a.id,
        activity_type="swimming",
        calories_burned=450,
        client_id=created.client_id,
        source=ActivitySource.MANUAL,
        logged_at=created.logged_at,
        logged_on=created.logged_on,
    )
    updated = await repo.update(replacement)
    await session.commit()

    assert updated.activity_type == "swimming"
    assert updated.calories_burned == 450


async def test_activity_log_repository_update_raises_not_found_for_a_missing_log(session):
    from uuid import uuid4

    repo = SQLAlchemyActivityLogRepository(session)
    ghost = ActivityLog(
        id=uuid4(), user_id=1, activity_type="running", calories_burned=100, client_id="ghost"
    )
    with pytest.raises(ActivityLogNotFoundException):
        await repo.update(ghost)


async def test_activity_log_repository_get_by_id_round_trips(session):
    user_a, _ = await _make_two_users(session)
    repo = SQLAlchemyActivityLogRepository(session)
    created = await repo.create(
        ActivityLog.create(user_a.id, "running", 300, client_id="a1", logged_on=date(2026, 1, 1))
    )
    await session.commit()

    fetched = await repo.get_by_id(created.id)
    assert fetched is not None
    assert fetched.activity_type == "running"

    assert await repo.get_by_id(uuid4()) is None
```

Add `import pytest` and `from uuid import uuid4` to this file's top-level
imports if not already present.

- [ ] **Step 3: Run to verify these fail**

```bash
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5433/foodfen_test uv run pytest tests/integration/test_diary_sync_repositories.py -k activity_log_repository -v
```
Expected: FAIL — `AttributeError: 'SQLAlchemyActivityLogRepository' object has no attribute 'create'`.

- [ ] **Step 4: Implement the repository**

Edit `src/infrastructure/db/repositories/activity_log_repository.py`:

```python
"""Concrete ``ActivityLogRepositoryProtocol`` implementation backed by async SQLAlchemy."""

from __future__ import annotations

from datetime import date
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.entities.activity_log import ActivityLog
from src.domain.exceptions import ActivityLogNotFoundException
from src.infrastructure.db.models.activity_log_model import ActivityLogORM
from src.infrastructure.db.repositories.idempotency import create_idempotent


class SQLAlchemyActivityLogRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, log: ActivityLog) -> ActivityLog:
        row = await create_idempotent(
            self._session, ActivityLogORM.from_domain(log), ActivityLogORM
        )
        return row.to_domain()

    async def get_by_id(self, log_id: UUID) -> ActivityLog | None:
        row = await self._session.get(ActivityLogORM, log_id)
        return row.to_domain() if row is not None else None

    async def update(self, log: ActivityLog) -> ActivityLog:
        row = await self._session.get(ActivityLogORM, log.id)
        if row is None:
            raise ActivityLogNotFoundException(f"no activity log {log.id}")
        fresh = ActivityLogORM.from_domain(log)
        for column in ActivityLogORM.__table__.columns.keys():
            if column != "id":
                setattr(row, column, getattr(fresh, column))
        await self._session.flush()
        await self._session.refresh(row)
        return row.to_domain()

    async def list_by_date_range(
        self, user_id: int, from_date: date, to_date: date
    ) -> list[ActivityLog]:
        rows = (
            await self._session.execute(
                select(ActivityLogORM).where(
                    ActivityLogORM.user_id == user_id,
                    ActivityLogORM.logged_on >= from_date,
                    ActivityLogORM.logged_on <= to_date,
                )
            )
        ).scalars().all()
        return [row.to_domain() for row in rows]
```

- [ ] **Step 5: Run to verify the repository tests pass**

```bash
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5433/foodfen_test uv run pytest tests/integration/test_diary_sync_repositories.py -v
```
Expected: PASS, all tests in the file.

- [ ] **Step 6: Add DTOs**

Edit `src/application/dtos/activity_log.py`, append:

```python
@dataclass(frozen=True)
class CreateActivityLogInputDTO:
    user_id: int
    activity_type: str
    calories_burned: int
    client_id: str
    source: ActivitySource = ActivitySource.MANUAL
    logged_on: date | None = None


@dataclass(frozen=True)
class UpdateActivityLogInputDTO:
    activity_type: str
    calories_burned: int
    source: ActivitySource = ActivitySource.MANUAL
    logged_on: date | None = None
```

- [ ] **Step 7: Write the failing use-case unit tests**

Create `tests/unit/test_activity_log_use_cases.py`:

```python
"""CreateActivityLogUseCase / UpdateActivityLogUseCase unit tests. No I/O."""

from __future__ import annotations

from datetime import date

import pytest

from src.application.dtos.activity_log import CreateActivityLogInputDTO, UpdateActivityLogInputDTO
from src.application.use_cases.create_activity_log import CreateActivityLogUseCase
from src.application.use_cases.update_activity_log import UpdateActivityLogUseCase
from src.domain.entities.activity_log import ActivityLog
from src.domain.enums import ActivitySource
from src.domain.exceptions import ActivityLogNotFoundException


class FakeActivityLogRepo:
    def __init__(self) -> None:
        self._by_id: dict = {}
        self._by_client_id: dict = {}

    async def create(self, log: ActivityLog) -> ActivityLog:
        key = (log.user_id, log.client_id)
        if key in self._by_client_id:
            return self._by_client_id[key]
        self._by_id[log.id] = log
        self._by_client_id[key] = log
        return log

    async def get_by_id(self, log_id):
        return self._by_id.get(log_id)

    async def update(self, log: ActivityLog) -> ActivityLog:
        if self._by_id.get(log.id) is None:
            raise ActivityLogNotFoundException(f"no activity log {log.id}")
        self._by_id[log.id] = log
        return log

    async def list_by_date_range(self, user_id, from_date, to_date):
        return [
            log
            for log in self._by_id.values()
            if log.user_id == user_id and from_date <= log.logged_on <= to_date
        ]


def _create_dto(client_id="activity_1") -> CreateActivityLogInputDTO:
    return CreateActivityLogInputDTO(
        user_id=1, activity_type="running", calories_burned=300, client_id=client_id
    )


async def test_create_returns_dto_with_assigned_id():
    use_case = CreateActivityLogUseCase(activity_logs=FakeActivityLogRepo())
    result = await use_case.execute(_create_dto())
    assert result.activity_type == "running"
    assert result.user_id == 1


async def test_create_with_repeated_client_id_returns_the_same_log():
    repo = FakeActivityLogRepo()
    use_case = CreateActivityLogUseCase(activity_logs=repo)
    first = await use_case.execute(_create_dto())
    second = await use_case.execute(_create_dto())
    assert second.id == first.id


async def test_update_replaces_fields_for_the_owner():
    repo = FakeActivityLogRepo()
    created = await CreateActivityLogUseCase(activity_logs=repo).execute(_create_dto())

    use_case = UpdateActivityLogUseCase(activity_logs=repo)
    result = await use_case.execute(
        user_id=1,
        log_id=created.id,
        input_dto=UpdateActivityLogInputDTO(
            activity_type="swimming", calories_burned=450, source=ActivitySource.MANUAL
        ),
    )
    assert result.activity_type == "swimming"
    assert result.calories_burned == 450


async def test_update_raises_not_found_for_another_users_log():
    repo = FakeActivityLogRepo()
    created = await CreateActivityLogUseCase(activity_logs=repo).execute(_create_dto())

    use_case = UpdateActivityLogUseCase(activity_logs=repo)
    with pytest.raises(ActivityLogNotFoundException):
        await use_case.execute(
            user_id=999,
            log_id=created.id,
            input_dto=UpdateActivityLogInputDTO(activity_type="x", calories_burned=1),
        )
```

- [ ] **Step 8: Run to verify these fail**

```bash
uv run pytest tests/unit/test_activity_log_use_cases.py -v
```
Expected: FAIL — `ModuleNotFoundError: No module named 'src.application.use_cases.create_activity_log'`.

- [ ] **Step 9: Implement the use cases**

Create `src/application/use_cases/create_activity_log.py`:

```python
"""Use case: log an exercise session."""

from __future__ import annotations

from dataclasses import dataclass

from src.application.dtos.activity_log import ActivityLogOutputDTO, CreateActivityLogInputDTO
from src.application.ports.activity_log_repository import ActivityLogRepositoryProtocol
from src.domain.entities.activity_log import ActivityLog


@dataclass
class CreateActivityLogUseCase:
    activity_logs: ActivityLogRepositoryProtocol

    async def execute(self, input_dto: CreateActivityLogInputDTO) -> ActivityLogOutputDTO:
        log = ActivityLog.create(
            user_id=input_dto.user_id,
            activity_type=input_dto.activity_type,
            calories_burned=input_dto.calories_burned,
            client_id=input_dto.client_id,
            source=input_dto.source,
            logged_on=input_dto.logged_on,
        )
        created = await self.activity_logs.create(log)
        return ActivityLogOutputDTO.from_entity(created)
```

Create `src/application/use_cases/update_activity_log.py`:

```python
"""Use case: full-replace an existing activity log."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from src.application.dtos.activity_log import ActivityLogOutputDTO, UpdateActivityLogInputDTO
from src.application.ports.activity_log_repository import ActivityLogRepositoryProtocol
from src.domain.entities.activity_log import ActivityLog
from src.domain.exceptions import ActivityLogNotFoundException


@dataclass
class UpdateActivityLogUseCase:
    activity_logs: ActivityLogRepositoryProtocol

    async def execute(
        self, user_id: int, log_id: UUID, input_dto: UpdateActivityLogInputDTO
    ) -> ActivityLogOutputDTO:
        existing = await self.activity_logs.get_by_id(log_id)
        if existing is None or existing.user_id != user_id:
            raise ActivityLogNotFoundException(f"no activity log {log_id}")

        log = ActivityLog(
            id=log_id,
            user_id=user_id,
            activity_type=input_dto.activity_type,
            calories_burned=input_dto.calories_burned,
            client_id=existing.client_id,
            source=input_dto.source,
            logged_at=existing.logged_at,
            logged_on=input_dto.logged_on or existing.logged_on,
        )
        updated = await self.activity_logs.update(log)
        return ActivityLogOutputDTO.from_entity(updated)
```

- [ ] **Step 10: Run to verify the use-case tests pass**

```bash
uv run pytest tests/unit/test_activity_log_use_cases.py -v
```
Expected: PASS.

- [ ] **Step 11: Add schemas and controller routes**

Edit `src/adapters/schemas/activity_log_schemas.py`, append:

```python
class CreateActivityLogRequest(CamelModel):
    activity_type: str = Field(min_length=1)
    calories_burned: int
    client_id: str = Field(min_length=1)
    source: ActivitySource = ActivitySource.MANUAL
    logged_on: date | None = None


class UpdateActivityLogRequest(CamelModel):
    activity_type: str = Field(min_length=1)
    calories_burned: int
    source: ActivitySource = ActivitySource.MANUAL
    logged_on: date | None = None
```

(add `from pydantic import Field` to the file's imports.)

Edit `src/adapters/controllers/activity_log_controller.py`:

```python
"""Activity log endpoints. HTTP <-> application DTO translation only."""

from __future__ import annotations

from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query

from src.adapters.schemas.activity_log_schemas import (
    ActivityLogResponse,
    CreateActivityLogRequest,
    UpdateActivityLogRequest,
)
from src.application.dtos.activity_log import CreateActivityLogInputDTO, UpdateActivityLogInputDTO
from src.infrastructure.di import (
    CreateActivityLogUseCaseDep,
    CurrentUserDep,
    ListActivityLogsUseCaseDep,
    UpdateActivityLogUseCaseDep,
)

router = APIRouter(prefix="/activity-logs", tags=["activity-logs"])


@router.post("", response_model=ActivityLogResponse)
async def create_activity_log(
    body: CreateActivityLogRequest, user: CurrentUserDep, use_case: CreateActivityLogUseCaseDep
) -> ActivityLogResponse:
    input_dto = CreateActivityLogInputDTO(
        user_id=user.id,
        activity_type=body.activity_type,
        calories_burned=body.calories_burned,
        client_id=body.client_id,
        source=body.source,
        logged_on=body.logged_on,
    )
    result = await use_case.execute(input_dto)
    return ActivityLogResponse.from_dto(result)


@router.get("", response_model=list[ActivityLogResponse])
async def list_activity_logs(
    user: CurrentUserDep,
    use_case: ListActivityLogsUseCaseDep,
    from_: Annotated[date, Query(alias="from")],
    to: Annotated[date, Query()],
) -> list[ActivityLogResponse]:
    result = await use_case.execute(user.id, from_, to)
    return [ActivityLogResponse.from_dto(dto) for dto in result]


@router.patch("/{log_id}", response_model=ActivityLogResponse)
async def update_activity_log(
    log_id: UUID,
    body: UpdateActivityLogRequest,
    user: CurrentUserDep,
    use_case: UpdateActivityLogUseCaseDep,
) -> ActivityLogResponse:
    input_dto = UpdateActivityLogInputDTO(
        activity_type=body.activity_type,
        calories_burned=body.calories_burned,
        source=body.source,
        logged_on=body.logged_on,
    )
    result = await use_case.execute(user_id=user.id, log_id=log_id, input_dto=input_dto)
    return ActivityLogResponse.from_dto(result)
```

- [ ] **Step 12: Wire DI**

Edit `src/infrastructure/di/use_cases.py`:

```python
from src.application.use_cases.create_activity_log import CreateActivityLogUseCase
from src.application.use_cases.update_activity_log import UpdateActivityLogUseCase
```

```python
def get_create_activity_log_use_case(
    activity_logs: ActivityLogRepositoryDep,
) -> CreateActivityLogUseCase:
    return CreateActivityLogUseCase(activity_logs=activity_logs)


def get_update_activity_log_use_case(
    activity_logs: ActivityLogRepositoryDep,
) -> UpdateActivityLogUseCase:
    return UpdateActivityLogUseCase(activity_logs=activity_logs)


CreateActivityLogUseCaseDep = Annotated[
    CreateActivityLogUseCase, Depends(get_create_activity_log_use_case)
]
UpdateActivityLogUseCaseDep = Annotated[
    UpdateActivityLogUseCase, Depends(get_update_activity_log_use_case)
]
```

Edit `src/infrastructure/di/__init__.py` — add the two new use case deps
and their provider functions to the imports and `__all__` list.

- [ ] **Step 13: Write the failing API tests**

Add to `tests/api/test_activity_log_endpoints.py`:

```python
_CREATE_BODY = {
    "activityType": "running",
    "caloriesBurned": 300,
    "clientId": "activity_1",
    "loggedOn": "2026-01-15",
}


async def test_post_creates_a_log(client, signed_up):
    headers = {"Authorization": f"Bearer {signed_up['accessToken']}"}
    resp = await client.post("/activity-logs", json=_CREATE_BODY, headers=headers)
    assert resp.status_code == 200
    assert resp.json()["activityType"] == "running"


async def test_post_with_repeated_client_id_returns_the_same_log(client, signed_up):
    headers = {"Authorization": f"Bearer {signed_up['accessToken']}"}
    first = (await client.post("/activity-logs", json=_CREATE_BODY, headers=headers)).json()
    second = (await client.post("/activity-logs", json=_CREATE_BODY, headers=headers)).json()
    assert first["id"] == second["id"]


async def test_patch_replaces_the_log(client, signed_up):
    headers = {"Authorization": f"Bearer {signed_up['accessToken']}"}
    created = (await client.post("/activity-logs", json=_CREATE_BODY, headers=headers)).json()

    resp = await client.patch(
        f"/activity-logs/{created['id']}",
        json={"activityType": "swimming", "caloriesBurned": 450, "loggedOn": "2026-01-15"},
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["activityType"] == "swimming"


async def test_patch_rejects_another_users_log(client, signed_up):
    headers = {"Authorization": f"Bearer {signed_up['accessToken']}"}
    created = (await client.post("/activity-logs", json=_CREATE_BODY, headers=headers)).json()
    other = await client.post(
        "/auth/sign-up",
        json={"email": "other2@example.com", "password": "s3cret-pass", "displayName": "Other"},
    )
    other_headers = {"Authorization": f"Bearer {other.json()['accessToken']}"}

    resp = await client.patch(
        f"/activity-logs/{created['id']}",
        json={"activityType": "x", "caloriesBurned": 1, "loggedOn": "2026-01-15"},
        headers=other_headers,
    )
    assert resp.status_code == 404
```

- [ ] **Step 14: Run to verify, then run the full suite**

```bash
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5433/foodfen_test uv run pytest tests/api/test_activity_log_endpoints.py -v
uv run pytest tests/unit -q
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5433/foodfen_test uv run pytest tests/integration tests/api -q
uv run lint-imports
```
Expected: all green.

- [ ] **Step 15: Commit**

```bash
git add src/application/ports/activity_log_repository.py \
  src/infrastructure/db/repositories/activity_log_repository.py \
  src/application/dtos/activity_log.py \
  src/application/use_cases/create_activity_log.py \
  src/application/use_cases/update_activity_log.py \
  src/adapters/schemas/activity_log_schemas.py \
  src/adapters/controllers/activity_log_controller.py \
  src/infrastructure/di/use_cases.py src/infrastructure/di/__init__.py \
  tests/unit/test_activity_log_use_cases.py \
  tests/integration/test_diary_sync_repositories.py \
  tests/api/test_activity_log_endpoints.py
git commit -m "feat: add POST/PATCH /activity-logs"
```

---

## Task 4: Daily goals — POST

**Files:**
- Modify: `src/application/ports/daily_goal_repository.py`
- Modify: `src/infrastructure/db/repositories/daily_goal_repository.py`
- Modify: `src/application/dtos/daily_goal.py`
- Create: `src/application/use_cases/create_daily_goal.py`
- Modify: `src/adapters/schemas/daily_goal_schemas.py`
- Modify: `src/adapters/controllers/daily_goal_controller.py`
- Modify: `src/infrastructure/di/use_cases.py`, `src/infrastructure/di/__init__.py`
- Test: create `tests/unit/test_create_daily_goal_use_case.py`
- Test: `tests/integration/test_diary_sync_repositories.py`
- Test: `tests/api/test_daily_goal_endpoints.py`

**Interfaces:**
- Consumes: `create_idempotent` (Task 1).
- Produces: `DailyGoalRepositoryProtocol.create()`;
  `CreateDailyGoalUseCase.execute(input_dto) -> DailyGoalOutputDTO`.

- [ ] **Step 1: Extend the repository port**

Edit `src/application/ports/daily_goal_repository.py`:

```python
"""Persistence port for daily goals. Structural typing via Protocol."""

from __future__ import annotations

from typing import Protocol

from src.domain.entities.daily_goal import DailyGoal


class DailyGoalRepositoryProtocol(Protocol):
    async def create(self, goal: DailyGoal) -> DailyGoal: ...

    async def list_by_user(self, user_id: int) -> list[DailyGoal]: ...
```

- [ ] **Step 2: Write the failing repository test**

Add to `tests/integration/test_diary_sync_repositories.py`:

```python
async def test_daily_goal_repository_create_is_idempotent_on_client_id(session):
    user_a, _ = await _make_two_users(session)
    repo = SQLAlchemyDailyGoalRepository(session)

    first = await repo.create(
        DailyGoal.create(user_a.id, 2000, 200.0, 150.0, 60.0, 2500, date(2026, 1, 1), client_id="dup")
    )
    await session.commit()
    second = await repo.create(
        DailyGoal.create(user_a.id, 1800, 180.0, 120.0, 50.0, 2000, date(2026, 1, 1), client_id="dup")
    )
    await session.commit()

    assert second.id == first.id
    assert second.target_kcal == 2000  # unchanged: the retry was ignored
```

- [ ] **Step 3: Run to verify it fails**

```bash
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5433/foodfen_test uv run pytest tests/integration/test_diary_sync_repositories.py -k daily_goal_repository_create -v
```
Expected: FAIL — `AttributeError: 'SQLAlchemyDailyGoalRepository' object has no attribute 'create'`.

- [ ] **Step 4: Implement the repository**

Edit `src/infrastructure/db/repositories/daily_goal_repository.py`:

```python
"""Concrete ``DailyGoalRepositoryProtocol`` implementation backed by async SQLAlchemy."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.entities.daily_goal import DailyGoal
from src.infrastructure.db.models.daily_goal_model import DailyGoalORM
from src.infrastructure.db.repositories.idempotency import create_idempotent


class SQLAlchemyDailyGoalRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, goal: DailyGoal) -> DailyGoal:
        row = await create_idempotent(self._session, DailyGoalORM.from_domain(goal), DailyGoalORM)
        return row.to_domain()

    async def list_by_user(self, user_id: int) -> list[DailyGoal]:
        rows = (
            await self._session.execute(select(DailyGoalORM).where(DailyGoalORM.user_id == user_id))
        ).scalars().all()
        return [row.to_domain() for row in rows]
```

- [ ] **Step 5: Run to verify the repository test passes**

```bash
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5433/foodfen_test uv run pytest tests/integration/test_diary_sync_repositories.py -v
```
Expected: PASS, all tests in the file.

- [ ] **Step 6: Add the DTO**

Edit `src/application/dtos/daily_goal.py`, append:

```python
@dataclass(frozen=True)
class CreateDailyGoalInputDTO:
    user_id: int
    target_kcal: int
    target_carbs_g: float
    target_protein_g: float
    target_fat_g: float
    target_water_ml: int
    effective_date: date
    client_id: str
```

- [ ] **Step 7: Write the failing use-case unit test**

Create `tests/unit/test_create_daily_goal_use_case.py`:

```python
"""CreateDailyGoalUseCase unit tests. No I/O."""

from __future__ import annotations

from datetime import date

from src.application.dtos.daily_goal import CreateDailyGoalInputDTO
from src.application.use_cases.create_daily_goal import CreateDailyGoalUseCase
from src.domain.entities.daily_goal import DailyGoal


class FakeDailyGoalRepo:
    def __init__(self) -> None:
        self._by_client_id: dict = {}

    async def create(self, goal: DailyGoal) -> DailyGoal:
        key = (goal.user_id, goal.client_id)
        if key in self._by_client_id:
            return self._by_client_id[key]
        self._by_client_id[key] = goal
        return goal

    async def list_by_user(self, user_id):
        return [g for g in self._by_client_id.values() if g.user_id == user_id]


def _dto(client_id="goal_1") -> CreateDailyGoalInputDTO:
    return CreateDailyGoalInputDTO(
        user_id=1,
        target_kcal=2000,
        target_carbs_g=200.0,
        target_protein_g=150.0,
        target_fat_g=60.0,
        target_water_ml=2500,
        effective_date=date(2026, 1, 1),
        client_id=client_id,
    )


async def test_create_returns_dto():
    use_case = CreateDailyGoalUseCase(daily_goals=FakeDailyGoalRepo())
    result = await use_case.execute(_dto())
    assert result.target_kcal == 2000
    assert result.effective_date == date(2026, 1, 1)


async def test_create_with_repeated_client_id_returns_the_same_goal():
    repo = FakeDailyGoalRepo()
    use_case = CreateDailyGoalUseCase(daily_goals=repo)
    first = await use_case.execute(_dto())
    second = await use_case.execute(_dto())
    assert second.id == first.id
```

- [ ] **Step 8: Run to verify it fails**

```bash
uv run pytest tests/unit/test_create_daily_goal_use_case.py -v
```
Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 9: Implement the use case**

Create `src/application/use_cases/create_daily_goal.py`:

```python
"""Use case: set a new daily target. Goals are append-only — never edited or
deleted once created (see DailyGoal's own docstring)."""

from __future__ import annotations

from dataclasses import dataclass

from src.application.dtos.daily_goal import CreateDailyGoalInputDTO, DailyGoalOutputDTO
from src.application.ports.daily_goal_repository import DailyGoalRepositoryProtocol
from src.domain.entities.daily_goal import DailyGoal


@dataclass
class CreateDailyGoalUseCase:
    daily_goals: DailyGoalRepositoryProtocol

    async def execute(self, input_dto: CreateDailyGoalInputDTO) -> DailyGoalOutputDTO:
        goal = DailyGoal.create(
            user_id=input_dto.user_id,
            target_kcal=input_dto.target_kcal,
            target_carbs_g=input_dto.target_carbs_g,
            target_protein_g=input_dto.target_protein_g,
            target_fat_g=input_dto.target_fat_g,
            target_water_ml=input_dto.target_water_ml,
            effective_date=input_dto.effective_date,
            client_id=input_dto.client_id,
        )
        created = await self.daily_goals.create(goal)
        return DailyGoalOutputDTO.from_entity(created)
```

- [ ] **Step 10: Run to verify it passes**

```bash
uv run pytest tests/unit/test_create_daily_goal_use_case.py -v
```
Expected: PASS.

- [ ] **Step 11: Add schema and controller route**

Edit `src/adapters/schemas/daily_goal_schemas.py`, append:

```python
class CreateDailyGoalRequest(CamelModel):
    target_kcal: int
    target_carbs_g: float
    target_protein_g: float
    target_fat_g: float
    target_water_ml: int
    effective_date: date
    client_id: str = Field(min_length=1)
```

(add `from pydantic import Field` to the imports.)

Edit `src/adapters/controllers/daily_goal_controller.py`:

```python
"""Daily goal endpoints. HTTP <-> application DTO translation only."""

from __future__ import annotations

from fastapi import APIRouter

from src.adapters.schemas.daily_goal_schemas import CreateDailyGoalRequest, DailyGoalResponse
from src.application.dtos.daily_goal import CreateDailyGoalInputDTO
from src.infrastructure.di import CreateDailyGoalUseCaseDep, CurrentUserDep, ListDailyGoalsUseCaseDep

router = APIRouter(prefix="/daily-goals", tags=["daily-goals"])


@router.post("", response_model=DailyGoalResponse)
async def create_daily_goal(
    body: CreateDailyGoalRequest, user: CurrentUserDep, use_case: CreateDailyGoalUseCaseDep
) -> DailyGoalResponse:
    input_dto = CreateDailyGoalInputDTO(
        user_id=user.id,
        target_kcal=body.target_kcal,
        target_carbs_g=body.target_carbs_g,
        target_protein_g=body.target_protein_g,
        target_fat_g=body.target_fat_g,
        target_water_ml=body.target_water_ml,
        effective_date=body.effective_date,
        client_id=body.client_id,
    )
    result = await use_case.execute(input_dto)
    return DailyGoalResponse.from_dto(result)


@router.get("", response_model=list[DailyGoalResponse])
async def list_daily_goals(
    user: CurrentUserDep, use_case: ListDailyGoalsUseCaseDep
) -> list[DailyGoalResponse]:
    result = await use_case.execute(user.id)
    return [DailyGoalResponse.from_dto(dto) for dto in result]
```

- [ ] **Step 12: Wire DI**

Edit `src/infrastructure/di/use_cases.py`:

```python
from src.application.use_cases.create_daily_goal import CreateDailyGoalUseCase
```

```python
def get_create_daily_goal_use_case(
    daily_goals: DailyGoalRepositoryDep,
) -> CreateDailyGoalUseCase:
    return CreateDailyGoalUseCase(daily_goals=daily_goals)


CreateDailyGoalUseCaseDep = Annotated[
    CreateDailyGoalUseCase, Depends(get_create_daily_goal_use_case)
]
```

Edit `src/infrastructure/di/__init__.py` — add `CreateDailyGoalUseCaseDep`
and `get_create_daily_goal_use_case` to the imports and `__all__`.

- [ ] **Step 13: Write the failing API tests**

Add to `tests/api/test_daily_goal_endpoints.py`:

```python
_CREATE_BODY = {
    "targetKcal": 2000,
    "targetCarbsG": 200.0,
    "targetProteinG": 150.0,
    "targetFatG": 60.0,
    "targetWaterMl": 2500,
    "effectiveDate": "2026-01-01",
    "clientId": "goal_1",
}


async def test_post_creates_a_goal(client, signed_up):
    headers = {"Authorization": f"Bearer {signed_up['accessToken']}"}
    resp = await client.post("/daily-goals", json=_CREATE_BODY, headers=headers)
    assert resp.status_code == 200
    assert resp.json()["targetKcal"] == 2000


async def test_post_with_repeated_client_id_returns_the_same_goal(client, signed_up):
    headers = {"Authorization": f"Bearer {signed_up['accessToken']}"}
    first = (await client.post("/daily-goals", json=_CREATE_BODY, headers=headers)).json()
    second = (await client.post("/daily-goals", json=_CREATE_BODY, headers=headers)).json()
    assert first["id"] == second["id"]


async def test_create_requires_auth(client):
    resp = await client.post("/daily-goals", json=_CREATE_BODY)
    assert resp.status_code == 401
```

- [ ] **Step 14: Run to verify, then run the full suite**

```bash
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5433/foodfen_test uv run pytest tests/api/test_daily_goal_endpoints.py -v
uv run pytest tests/unit -q
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5433/foodfen_test uv run pytest tests/integration tests/api -q
uv run lint-imports
```
Expected: all green.

- [ ] **Step 15: Commit**

```bash
git add src/application/ports/daily_goal_repository.py \
  src/infrastructure/db/repositories/daily_goal_repository.py \
  src/application/dtos/daily_goal.py \
  src/application/use_cases/create_daily_goal.py \
  src/adapters/schemas/daily_goal_schemas.py \
  src/adapters/controllers/daily_goal_controller.py \
  src/infrastructure/di/use_cases.py src/infrastructure/di/__init__.py \
  tests/unit/test_create_daily_goal_use_case.py \
  tests/integration/test_diary_sync_repositories.py \
  tests/api/test_daily_goal_endpoints.py
git commit -m "feat: add POST /daily-goals"
```

---

## Task 5: Weight logs — POST

**Files:**
- Modify: `src/application/ports/weight_log_repository.py`
- Modify: `src/infrastructure/db/repositories/weight_log_repository.py`
- Modify: `src/application/dtos/weight_log.py`
- Create: `src/application/use_cases/create_weight_log.py`
- Modify: `src/adapters/schemas/weight_log_schemas.py`
- Modify: `src/adapters/controllers/weight_log_controller.py`
- Modify: `src/infrastructure/di/use_cases.py`, `src/infrastructure/di/__init__.py`
- Test: create `tests/unit/test_create_weight_log_use_case.py`
- Test: `tests/integration/test_diary_sync_repositories.py`
- Test: `tests/api/test_weight_log_endpoints.py`

**Interfaces:**
- Consumes: `create_idempotent` (Task 1).
- Produces: `WeightLogRepositoryProtocol.create()`;
  `CreateWeightLogUseCase.execute(input_dto) -> WeightLogOutputDTO`.

- [ ] **Step 1: Extend the repository port**

Edit `src/application/ports/weight_log_repository.py`:

```python
"""Persistence port for weight logs. Structural typing via Protocol."""

from __future__ import annotations

from datetime import date
from typing import Protocol

from src.domain.entities.weight_log import WeightLog


class WeightLogRepositoryProtocol(Protocol):
    async def create(self, log: WeightLog) -> WeightLog: ...

    async def list_by_date_range(
        self, user_id: int, from_date: date, to_date: date
    ) -> list[WeightLog]:
        """Inclusive range, filtered on ``recorded_at``."""
        ...
```

- [ ] **Step 2: Write the failing repository test**

Add to `tests/integration/test_diary_sync_repositories.py`:

```python
async def test_weight_log_repository_create_is_idempotent_on_client_id(session):
    user_a, _ = await _make_two_users(session)
    repo = SQLAlchemyWeightLogRepository(session)

    first = await repo.create(WeightLog.create(user_a.id, 60.4, date(2026, 1, 1), client_id="dup"))
    await session.commit()
    second = await repo.create(WeightLog.create(user_a.id, 99.9, date(2026, 1, 2), client_id="dup"))
    await session.commit()

    assert second.id == first.id
    assert second.weight == 60.4  # unchanged: the retry was ignored
```

- [ ] **Step 3: Run to verify it fails**

```bash
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5433/foodfen_test uv run pytest tests/integration/test_diary_sync_repositories.py -k weight_log_repository_create -v
```
Expected: FAIL — `AttributeError`.

- [ ] **Step 4: Implement the repository**

Edit `src/infrastructure/db/repositories/weight_log_repository.py`:

```python
"""Concrete ``WeightLogRepositoryProtocol`` implementation backed by async SQLAlchemy."""

from __future__ import annotations

from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.entities.weight_log import WeightLog
from src.infrastructure.db.models.weight_log_model import WeightLogORM
from src.infrastructure.db.repositories.idempotency import create_idempotent


class SQLAlchemyWeightLogRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, log: WeightLog) -> WeightLog:
        row = await create_idempotent(self._session, WeightLogORM.from_domain(log), WeightLogORM)
        return row.to_domain()

    async def list_by_date_range(
        self, user_id: int, from_date: date, to_date: date
    ) -> list[WeightLog]:
        rows = (
            await self._session.execute(
                select(WeightLogORM).where(
                    WeightLogORM.user_id == user_id,
                    WeightLogORM.recorded_at >= from_date,
                    WeightLogORM.recorded_at <= to_date,
                )
            )
        ).scalars().all()
        return [row.to_domain() for row in rows]
```

- [ ] **Step 5: Run to verify the repository test passes**

```bash
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5433/foodfen_test uv run pytest tests/integration/test_diary_sync_repositories.py -v
```
Expected: PASS, all tests in the file.

- [ ] **Step 6: Add the DTO**

Edit `src/application/dtos/weight_log.py`, append:

```python
@dataclass(frozen=True)
class CreateWeightLogInputDTO:
    user_id: int
    weight: float
    client_id: str
    recorded_at: date | None = None
```

- [ ] **Step 7: Write the failing use-case unit test**

Create `tests/unit/test_create_weight_log_use_case.py`:

```python
"""CreateWeightLogUseCase unit tests. No I/O."""

from __future__ import annotations

from datetime import date

from src.application.dtos.weight_log import CreateWeightLogInputDTO
from src.application.use_cases.create_weight_log import CreateWeightLogUseCase
from src.domain.entities.weight_log import WeightLog


class FakeWeightLogRepo:
    def __init__(self) -> None:
        self._by_client_id: dict = {}

    async def create(self, log: WeightLog) -> WeightLog:
        key = (log.user_id, log.client_id)
        if key in self._by_client_id:
            return self._by_client_id[key]
        self._by_client_id[key] = log
        return log

    async def list_by_date_range(self, user_id, from_date, to_date):
        return [
            log
            for log in self._by_client_id.values()
            if log.user_id == user_id and from_date <= log.recorded_at <= to_date
        ]


async def test_create_returns_dto():
    use_case = CreateWeightLogUseCase(weight_logs=FakeWeightLogRepo())
    result = await use_case.execute(
        CreateWeightLogInputDTO(user_id=1, weight=60.4, client_id="weight_1", recorded_at=date(2026, 1, 1))
    )
    assert result.weight == 60.4


async def test_create_with_repeated_client_id_returns_the_same_log():
    repo = FakeWeightLogRepo()
    use_case = CreateWeightLogUseCase(weight_logs=repo)
    dto = CreateWeightLogInputDTO(user_id=1, weight=60.4, client_id="weight_1")
    first = await use_case.execute(dto)
    second = await use_case.execute(dto)
    assert second.id == first.id
```

- [ ] **Step 8: Run to verify it fails**

```bash
uv run pytest tests/unit/test_create_weight_log_use_case.py -v
```
Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 9: Implement the use case**

Create `src/application/use_cases/create_weight_log.py`:

```python
"""Use case: log a weigh-in."""

from __future__ import annotations

from dataclasses import dataclass

from src.application.dtos.weight_log import CreateWeightLogInputDTO, WeightLogOutputDTO
from src.application.ports.weight_log_repository import WeightLogRepositoryProtocol
from src.domain.entities.weight_log import WeightLog


@dataclass
class CreateWeightLogUseCase:
    weight_logs: WeightLogRepositoryProtocol

    async def execute(self, input_dto: CreateWeightLogInputDTO) -> WeightLogOutputDTO:
        log = WeightLog.create(
            user_id=input_dto.user_id,
            weight=input_dto.weight,
            recorded_at=input_dto.recorded_at,
            client_id=input_dto.client_id,
        )
        created = await self.weight_logs.create(log)
        return WeightLogOutputDTO.from_entity(created)
```

- [ ] **Step 10: Run to verify it passes**

```bash
uv run pytest tests/unit/test_create_weight_log_use_case.py -v
```
Expected: PASS.

- [ ] **Step 11: Add schema and controller route**

Edit `src/adapters/schemas/weight_log_schemas.py`, append:

```python
class CreateWeightLogRequest(CamelModel):
    weight: float
    client_id: str = Field(min_length=1)
    recorded_at: date | None = None
```

(add `from pydantic import Field` to the imports.)

Edit `src/adapters/controllers/weight_log_controller.py`:

```python
"""Weight log endpoints. HTTP <-> application DTO translation only."""

from __future__ import annotations

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Query

from src.adapters.schemas.weight_log_schemas import CreateWeightLogRequest, WeightLogResponse
from src.application.dtos.weight_log import CreateWeightLogInputDTO
from src.infrastructure.di import (
    CreateWeightLogUseCaseDep,
    CurrentUserDep,
    ListWeightLogsUseCaseDep,
)

router = APIRouter(prefix="/weight-logs", tags=["weight-logs"])


@router.post("", response_model=WeightLogResponse)
async def create_weight_log(
    body: CreateWeightLogRequest, user: CurrentUserDep, use_case: CreateWeightLogUseCaseDep
) -> WeightLogResponse:
    input_dto = CreateWeightLogInputDTO(
        user_id=user.id, weight=body.weight, client_id=body.client_id, recorded_at=body.recorded_at
    )
    result = await use_case.execute(input_dto)
    return WeightLogResponse.from_dto(result)


@router.get("", response_model=list[WeightLogResponse])
async def list_weight_logs(
    user: CurrentUserDep,
    use_case: ListWeightLogsUseCaseDep,
    from_: Annotated[date, Query(alias="from")],
    to: Annotated[date, Query()],
) -> list[WeightLogResponse]:
    result = await use_case.execute(user.id, from_, to)
    return [WeightLogResponse.from_dto(dto) for dto in result]
```

- [ ] **Step 12: Wire DI**

Edit `src/infrastructure/di/use_cases.py`:

```python
from src.application.use_cases.create_weight_log import CreateWeightLogUseCase
```

```python
def get_create_weight_log_use_case(
    weight_logs: WeightLogRepositoryDep,
) -> CreateWeightLogUseCase:
    return CreateWeightLogUseCase(weight_logs=weight_logs)


CreateWeightLogUseCaseDep = Annotated[
    CreateWeightLogUseCase, Depends(get_create_weight_log_use_case)
]
```

Edit `src/infrastructure/di/__init__.py` — add `CreateWeightLogUseCaseDep`
and `get_create_weight_log_use_case` to the imports and `__all__`.

- [ ] **Step 13: Write the failing API tests**

Add to `tests/api/test_weight_log_endpoints.py`:

```python
_CREATE_BODY = {"weight": 60.4, "clientId": "weight_1", "recordedAt": "2026-01-15"}


async def test_post_creates_a_log(client, signed_up):
    headers = {"Authorization": f"Bearer {signed_up['accessToken']}"}
    resp = await client.post("/weight-logs", json=_CREATE_BODY, headers=headers)
    assert resp.status_code == 200
    assert resp.json()["weight"] == 60.4


async def test_post_with_repeated_client_id_returns_the_same_log(client, signed_up):
    headers = {"Authorization": f"Bearer {signed_up['accessToken']}"}
    first = (await client.post("/weight-logs", json=_CREATE_BODY, headers=headers)).json()
    second = (await client.post("/weight-logs", json=_CREATE_BODY, headers=headers)).json()
    assert first["id"] == second["id"]
```

- [ ] **Step 14: Run to verify, then run the full suite**

```bash
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5433/foodfen_test uv run pytest tests/api/test_weight_log_endpoints.py -v
uv run pytest tests/unit -q
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5433/foodfen_test uv run pytest tests/integration tests/api -q
uv run lint-imports
```
Expected: all green.

- [ ] **Step 15: Commit**

```bash
git add src/application/ports/weight_log_repository.py \
  src/infrastructure/db/repositories/weight_log_repository.py \
  src/application/dtos/weight_log.py \
  src/application/use_cases/create_weight_log.py \
  src/adapters/schemas/weight_log_schemas.py \
  src/adapters/controllers/weight_log_controller.py \
  src/infrastructure/di/use_cases.py src/infrastructure/di/__init__.py \
  tests/unit/test_create_weight_log_use_case.py \
  tests/integration/test_diary_sync_repositories.py \
  tests/api/test_weight_log_endpoints.py
git commit -m "feat: add POST /weight-logs"
```

---

## Task 6: Water logs — POST + DELETE

**Files:**
- Modify: `src/application/ports/water_log_repository.py`
- Modify: `src/infrastructure/db/repositories/water_log_repository.py`
- Modify: `src/application/dtos/water_log.py`
- Create: `src/application/use_cases/create_water_log.py`
- Create: `src/application/use_cases/delete_water_log.py`
- Modify: `src/adapters/schemas/water_log_schemas.py`
- Modify: `src/adapters/controllers/water_log_controller.py`
- Modify: `src/infrastructure/di/use_cases.py`, `src/infrastructure/di/__init__.py`
- Test: create `tests/unit/test_water_log_use_cases.py`
- Test: `tests/integration/test_diary_sync_repositories.py`
- Test: `tests/api/test_water_log_endpoints.py`

**Interfaces:**
- Consumes: `create_idempotent`, `WaterLogNotFoundException` (Task 1).
- Produces: `WaterLogRepositoryProtocol.create()`, `.get_by_id()`,
  `.delete()`; `CreateWaterLogUseCase.execute(input_dto) -> WaterLogOutputDTO`,
  `DeleteWaterLogUseCase.execute(user_id, log_id) -> None`.

- [ ] **Step 1: Extend the repository port**

Edit `src/application/ports/water_log_repository.py`:

```python
"""Persistence port for water logs. Structural typing via Protocol."""

from __future__ import annotations

from datetime import date
from typing import Protocol
from uuid import UUID

from src.domain.entities.water_log import WaterLog


class WaterLogRepositoryProtocol(Protocol):
    async def create(self, log: WaterLog) -> WaterLog: ...

    async def get_by_id(self, log_id: UUID) -> WaterLog | None: ...

    async def delete(self, log_id: UUID) -> None:
        """Soft delete. Raise ``WaterLogNotFoundException`` if it doesn't
        exist or is already deleted."""
        ...

    async def list_by_date_range(
        self, user_id: int, from_date: date, to_date: date
    ) -> list[WaterLog]:
        """Inclusive range, filtered on ``logged_on``."""
        ...
```

- [ ] **Step 2: Write the failing repository tests**

Add to `tests/integration/test_diary_sync_repositories.py`:

```python
from src.domain.exceptions import WaterLogNotFoundException


async def test_water_log_repository_create_is_idempotent_on_client_id(session):
    user_a, _ = await _make_two_users(session)
    repo = SQLAlchemyWaterLogRepository(session)

    first = await repo.create(
        WaterLog.create(user_a.id, 350, client_id="dup", logged_on=date(2026, 1, 1))
    )
    await session.commit()
    second = await repo.create(
        WaterLog.create(user_a.id, 999, client_id="dup", logged_on=date(2026, 1, 2))
    )
    await session.commit()

    assert second.id == first.id
    assert second.amount_ml == 350  # unchanged: the retry was ignored


async def test_water_log_repository_delete_soft_deletes_and_list_stops_returning_it(session):
    user_a, _ = await _make_two_users(session)
    repo = SQLAlchemyWaterLogRepository(session)
    created = await repo.create(
        WaterLog.create(user_a.id, 350, client_id="w1", logged_on=date(2026, 1, 1))
    )
    await session.commit()

    await repo.delete(created.id)
    await session.commit()

    assert await repo.get_by_id(created.id) is None
    result = await repo.list_by_date_range(user_a.id, date(2026, 1, 1), date(2026, 1, 1))
    assert result == []


async def test_water_log_repository_delete_twice_raises_not_found(session):
    user_a, _ = await _make_two_users(session)
    repo = SQLAlchemyWaterLogRepository(session)
    created = await repo.create(
        WaterLog.create(user_a.id, 350, client_id="w1", logged_on=date(2026, 1, 1))
    )
    await session.commit()
    await repo.delete(created.id)
    await session.commit()

    with pytest.raises(WaterLogNotFoundException):
        await repo.delete(created.id)
```

- [ ] **Step 3: Run to verify these fail**

```bash
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5433/foodfen_test uv run pytest tests/integration/test_diary_sync_repositories.py -k water_log_repository -v
```
Expected: FAIL — `AttributeError: 'SQLAlchemyWaterLogRepository' object has no attribute 'create'`.

- [ ] **Step 4: Implement the repository**

Edit `src/infrastructure/db/repositories/water_log_repository.py`:

```python
"""Concrete ``WaterLogRepositoryProtocol`` implementation backed by async SQLAlchemy."""

from __future__ import annotations

from datetime import UTC, date, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.entities.water_log import WaterLog
from src.domain.exceptions import WaterLogNotFoundException
from src.infrastructure.db.models.water_log_model import WaterLogORM
from src.infrastructure.db.repositories.idempotency import create_idempotent


class SQLAlchemyWaterLogRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, log: WaterLog) -> WaterLog:
        row = await create_idempotent(self._session, WaterLogORM.from_domain(log), WaterLogORM)
        return row.to_domain()

    async def get_by_id(self, log_id: UUID) -> WaterLog | None:
        row = await self._session.get(WaterLogORM, log_id)
        if row is None or row.deleted_at is not None:
            return None
        return row.to_domain()

    async def delete(self, log_id: UUID) -> None:
        row = await self._session.get(WaterLogORM, log_id)
        if row is None or row.deleted_at is not None:
            raise WaterLogNotFoundException(f"no water log {log_id}")
        row.deleted_at = datetime.now(UTC)
        await self._session.flush()

    async def list_by_date_range(
        self, user_id: int, from_date: date, to_date: date
    ) -> list[WaterLog]:
        rows = (
            await self._session.execute(
                select(WaterLogORM).where(
                    WaterLogORM.user_id == user_id,
                    WaterLogORM.logged_on >= from_date,
                    WaterLogORM.logged_on <= to_date,
                    WaterLogORM.deleted_at.is_(None),
                )
            )
        ).scalars().all()
        return [row.to_domain() for row in rows]
```

- [ ] **Step 5: Run to verify the repository tests pass**

```bash
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5433/foodfen_test uv run pytest tests/integration/test_diary_sync_repositories.py -v
```
Expected: PASS, all tests in the file.

- [ ] **Step 6: Add the DTO**

Edit `src/application/dtos/water_log.py`, append:

```python
@dataclass(frozen=True)
class CreateWaterLogInputDTO:
    user_id: int
    amount_ml: int
    client_id: str
    logged_on: date | None = None
```

- [ ] **Step 7: Write the failing use-case unit tests**

Create `tests/unit/test_water_log_use_cases.py`:

```python
"""CreateWaterLogUseCase / DeleteWaterLogUseCase unit tests. No I/O."""

from __future__ import annotations

from datetime import date

import pytest

from src.application.dtos.water_log import CreateWaterLogInputDTO
from src.application.use_cases.create_water_log import CreateWaterLogUseCase
from src.application.use_cases.delete_water_log import DeleteWaterLogUseCase
from src.domain.entities.water_log import WaterLog
from src.domain.exceptions import WaterLogNotFoundException


class FakeWaterLogRepo:
    def __init__(self) -> None:
        self._by_id: dict = {}
        self._by_client_id: dict = {}

    async def create(self, log: WaterLog) -> WaterLog:
        key = (log.user_id, log.client_id)
        if key in self._by_client_id:
            return self._by_client_id[key]
        self._by_id[log.id] = log
        self._by_client_id[key] = log
        return log

    async def get_by_id(self, log_id):
        return self._by_id.get(log_id)

    async def delete(self, log_id):
        if self._by_id.get(log_id) is None:
            raise WaterLogNotFoundException(f"no water log {log_id}")
        self._by_id[log_id] = None

    async def list_by_date_range(self, user_id, from_date, to_date):
        return [
            log
            for log in self._by_id.values()
            if log is not None and log.user_id == user_id and from_date <= log.logged_on <= to_date
        ]


def _dto(client_id="water_1") -> CreateWaterLogInputDTO:
    return CreateWaterLogInputDTO(user_id=1, amount_ml=350, client_id=client_id)


async def test_create_returns_dto():
    use_case = CreateWaterLogUseCase(water_logs=FakeWaterLogRepo())
    result = await use_case.execute(_dto())
    assert result.amount_ml == 350


async def test_create_with_repeated_client_id_returns_the_same_log():
    repo = FakeWaterLogRepo()
    use_case = CreateWaterLogUseCase(water_logs=repo)
    first = await use_case.execute(_dto())
    second = await use_case.execute(_dto())
    assert second.id == first.id


async def test_delete_removes_the_owners_log():
    repo = FakeWaterLogRepo()
    created = await CreateWaterLogUseCase(water_logs=repo).execute(_dto())

    use_case = DeleteWaterLogUseCase(water_logs=repo)
    await use_case.execute(user_id=1, log_id=created.id)

    assert await repo.get_by_id(created.id) is None


async def test_delete_raises_not_found_for_another_users_log():
    repo = FakeWaterLogRepo()
    created = await CreateWaterLogUseCase(water_logs=repo).execute(_dto())

    use_case = DeleteWaterLogUseCase(water_logs=repo)
    with pytest.raises(WaterLogNotFoundException):
        await use_case.execute(user_id=999, log_id=created.id)
```

- [ ] **Step 8: Run to verify these fail**

```bash
uv run pytest tests/unit/test_water_log_use_cases.py -v
```
Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 9: Implement the use cases**

Create `src/application/use_cases/create_water_log.py`:

```python
"""Use case: log a drink."""

from __future__ import annotations

from dataclasses import dataclass

from src.application.dtos.water_log import CreateWaterLogInputDTO, WaterLogOutputDTO
from src.application.ports.water_log_repository import WaterLogRepositoryProtocol
from src.domain.entities.water_log import WaterLog


@dataclass
class CreateWaterLogUseCase:
    water_logs: WaterLogRepositoryProtocol

    async def execute(self, input_dto: CreateWaterLogInputDTO) -> WaterLogOutputDTO:
        log = WaterLog.create(
            user_id=input_dto.user_id,
            amount_ml=input_dto.amount_ml,
            client_id=input_dto.client_id,
            logged_on=input_dto.logged_on,
        )
        created = await self.water_logs.create(log)
        return WaterLogOutputDTO.from_entity(created)
```

Create `src/application/use_cases/delete_water_log.py`:

```python
"""Use case: undo a logged drink (soft delete), for the "undo my last cup" flow."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from src.application.ports.water_log_repository import WaterLogRepositoryProtocol
from src.domain.exceptions import WaterLogNotFoundException


@dataclass
class DeleteWaterLogUseCase:
    water_logs: WaterLogRepositoryProtocol

    async def execute(self, user_id: int, log_id: UUID) -> None:
        existing = await self.water_logs.get_by_id(log_id)
        if existing is None or existing.user_id != user_id:
            raise WaterLogNotFoundException(f"no water log {log_id}")
        await self.water_logs.delete(log_id)
```

- [ ] **Step 10: Run to verify the use-case tests pass**

```bash
uv run pytest tests/unit/test_water_log_use_cases.py -v
```
Expected: PASS.

- [ ] **Step 11: Add schema and controller routes**

Edit `src/adapters/schemas/water_log_schemas.py`, append:

```python
class CreateWaterLogRequest(CamelModel):
    amount_ml: int
    client_id: str = Field(min_length=1)
    logged_on: date | None = None
```

(add `from pydantic import Field` to the imports.)

Edit `src/adapters/controllers/water_log_controller.py`:

```python
"""Water log endpoints. HTTP <-> application DTO translation only."""

from __future__ import annotations

from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query

from src.adapters.schemas.water_log_schemas import CreateWaterLogRequest, WaterLogResponse
from src.application.dtos.water_log import CreateWaterLogInputDTO
from src.infrastructure.di import (
    CreateWaterLogUseCaseDep,
    CurrentUserDep,
    DeleteWaterLogUseCaseDep,
    ListWaterLogsUseCaseDep,
)

router = APIRouter(prefix="/water-logs", tags=["water-logs"])


@router.post("", response_model=WaterLogResponse)
async def create_water_log(
    body: CreateWaterLogRequest, user: CurrentUserDep, use_case: CreateWaterLogUseCaseDep
) -> WaterLogResponse:
    input_dto = CreateWaterLogInputDTO(
        user_id=user.id, amount_ml=body.amount_ml, client_id=body.client_id, logged_on=body.logged_on
    )
    result = await use_case.execute(input_dto)
    return WaterLogResponse.from_dto(result)


@router.get("", response_model=list[WaterLogResponse])
async def list_water_logs(
    user: CurrentUserDep,
    use_case: ListWaterLogsUseCaseDep,
    from_: Annotated[date, Query(alias="from")],
    to: Annotated[date, Query()],
) -> list[WaterLogResponse]:
    result = await use_case.execute(user.id, from_, to)
    return [WaterLogResponse.from_dto(dto) for dto in result]


@router.delete("/{log_id}", status_code=204)
async def delete_water_log(
    log_id: UUID, user: CurrentUserDep, use_case: DeleteWaterLogUseCaseDep
) -> None:
    await use_case.execute(user_id=user.id, log_id=log_id)
```

- [ ] **Step 12: Wire DI**

Edit `src/infrastructure/di/use_cases.py`:

```python
from src.application.use_cases.create_water_log import CreateWaterLogUseCase
from src.application.use_cases.delete_water_log import DeleteWaterLogUseCase
```

```python
def get_create_water_log_use_case(water_logs: WaterLogRepositoryDep) -> CreateWaterLogUseCase:
    return CreateWaterLogUseCase(water_logs=water_logs)


def get_delete_water_log_use_case(water_logs: WaterLogRepositoryDep) -> DeleteWaterLogUseCase:
    return DeleteWaterLogUseCase(water_logs=water_logs)


CreateWaterLogUseCaseDep = Annotated[
    CreateWaterLogUseCase, Depends(get_create_water_log_use_case)
]
DeleteWaterLogUseCaseDep = Annotated[
    DeleteWaterLogUseCase, Depends(get_delete_water_log_use_case)
]
```

Edit `src/infrastructure/di/__init__.py` — add both new deps and provider
functions to the imports and `__all__`.

- [ ] **Step 13: Write the failing API tests**

Add to `tests/api/test_water_log_endpoints.py`:

```python
_CREATE_BODY = {"amountMl": 350, "clientId": "water_1", "loggedOn": "2026-01-15"}


async def test_post_creates_a_log(client, signed_up):
    headers = {"Authorization": f"Bearer {signed_up['accessToken']}"}
    resp = await client.post("/water-logs", json=_CREATE_BODY, headers=headers)
    assert resp.status_code == 200
    assert resp.json()["amountMl"] == 350


async def test_post_with_repeated_client_id_returns_the_same_log(client, signed_up):
    headers = {"Authorization": f"Bearer {signed_up['accessToken']}"}
    first = (await client.post("/water-logs", json=_CREATE_BODY, headers=headers)).json()
    second = (await client.post("/water-logs", json=_CREATE_BODY, headers=headers)).json()
    assert first["id"] == second["id"]


async def test_delete_soft_deletes_and_it_disappears_from_list(client, signed_up):
    headers = {"Authorization": f"Bearer {signed_up['accessToken']}"}
    created = (await client.post("/water-logs", json=_CREATE_BODY, headers=headers)).json()

    resp = await client.delete(f"/water-logs/{created['id']}", headers=headers)
    assert resp.status_code == 204

    list_resp = await client.get(
        "/water-logs", params={"from": "2026-01-15", "to": "2026-01-15"}, headers=headers
    )
    assert list_resp.json() == []


async def test_delete_rejects_another_users_log(client, signed_up):
    headers = {"Authorization": f"Bearer {signed_up['accessToken']}"}
    created = (await client.post("/water-logs", json=_CREATE_BODY, headers=headers)).json()
    other = await client.post(
        "/auth/sign-up",
        json={"email": "waterother@example.com", "password": "s3cret-pass", "displayName": "Other"},
    )
    other_headers = {"Authorization": f"Bearer {other.json()['accessToken']}"}

    resp = await client.delete(f"/water-logs/{created['id']}", headers=other_headers)
    assert resp.status_code == 404
```

- [ ] **Step 14: Run to verify, then run the full suite**

```bash
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5433/foodfen_test uv run pytest tests/api/test_water_log_endpoints.py -v
uv run pytest tests/unit -q
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5433/foodfen_test uv run pytest tests/integration tests/api -q
uv run lint-imports
```
Expected: all green.

- [ ] **Step 15: Commit**

```bash
git add src/application/ports/water_log_repository.py \
  src/infrastructure/db/repositories/water_log_repository.py \
  src/application/dtos/water_log.py \
  src/application/use_cases/create_water_log.py \
  src/application/use_cases/delete_water_log.py \
  src/adapters/schemas/water_log_schemas.py \
  src/adapters/controllers/water_log_controller.py \
  src/infrastructure/di/use_cases.py src/infrastructure/di/__init__.py \
  tests/unit/test_water_log_use_cases.py \
  tests/integration/test_diary_sync_repositories.py \
  tests/api/test_water_log_endpoints.py
git commit -m "feat: add POST/DELETE /water-logs"
```

---

## Task 7: User profile — PATCH /users/me

**Files:**
- Create: `src/application/dtos/update_user_profile.py`
- Create: `src/application/use_cases/update_user_profile.py`
- Modify: `src/adapters/schemas/user_schemas.py`
- Modify: `src/adapters/controllers/user_controller.py`
- Modify: `src/infrastructure/di/use_cases.py`, `src/infrastructure/di/__init__.py`
- Test: create `tests/unit/test_update_user_profile_use_case.py`
- Test: create `tests/api/test_update_user_profile_endpoint.py`

**Interfaces:**
- Consumes: `UserRepositoryProtocol.update()` (existing, already
  implemented — no change needed), `UserAlreadyExistsException` (existing).
- Produces: `UpdateUserProfileUseCase.execute(user_id, updates: dict) -> UserOutputDTO`.

- [ ] **Step 1: Add the input DTO**

Create `src/application/dtos/update_user_profile.py`:

```python
"""Input DTO for partial profile updates.

``updates`` carries only the fields the client actually sent (built by the
controller via Pydantic's ``exclude_unset``) — a plain ``dict`` rather than
one optional field per profile attribute, since every one of the 13
editable fields would otherwise need its own sentinel-vs-None handling for
no benefit: the use case only ever needs to know *which* fields to apply,
not carry a fixed shape for them.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class UpdateUserProfileInputDTO:
    user_id: int
    updates: dict[str, Any]
```

- [ ] **Step 2: Write the failing use-case unit tests**

Create `tests/unit/test_update_user_profile_use_case.py`:

```python
"""UpdateUserProfileUseCase unit tests. No I/O."""

from __future__ import annotations

import pytest

from src.application.dtos.update_user_profile import UpdateUserProfileInputDTO
from src.application.use_cases.update_user_profile import UpdateUserProfileUseCase
from src.domain.entities.user import User
from src.domain.enums import Gender
from src.domain.exceptions import InvalidUserAttributeException, UserAlreadyExistsException, UserNotFoundException


class FakeUserRepo:
    def __init__(self, users: list[User]) -> None:
        self._by_id = {u.id: u for u in users}

    async def get_by_id(self, user_id):
        return self._by_id.get(user_id)

    async def get_by_email(self, email):
        return next((u for u in self._by_id.values() if u.email == email), None)

    async def create(self, user):
        raise NotImplementedError

    async def update(self, user):
        if user.id not in self._by_id:
            raise UserNotFoundException(f"user {user.id} not found")
        self._by_id[user.id] = user
        return user


def _user(user_id=1, **overrides) -> User:
    user = User.create(email="a@example.com", name="Original")
    user.id = user_id
    for field, value in overrides.items():
        setattr(user, field, value)
    return user


async def test_only_the_sent_fields_change():
    repo = FakeUserRepo([_user(height=170.0, weight_current=70.0)])
    use_case = UpdateUserProfileUseCase(users=repo)

    result = await use_case.execute(
        UpdateUserProfileInputDTO(user_id=1, updates={"height": 180.0})
    )

    assert result.height == 180.0
    assert result.weight_current == 70.0  # untouched: not in `updates`


async def test_empty_updates_leaves_the_user_unchanged():
    repo = FakeUserRepo([_user(name="Original")])
    use_case = UpdateUserProfileUseCase(users=repo)

    result = await use_case.execute(UpdateUserProfileInputDTO(user_id=1, updates={}))

    assert result.name == "Original"


async def test_display_name_maps_to_the_domains_name_field():
    repo = FakeUserRepo([_user(name="Original")])
    use_case = UpdateUserProfileUseCase(users=repo)

    result = await use_case.execute(
        UpdateUserProfileInputDTO(user_id=1, updates={"display_name": "New Name"})
    )

    assert result.name == "New Name"


async def test_gender_updates():
    repo = FakeUserRepo([_user()])
    use_case = UpdateUserProfileUseCase(users=repo)

    result = await use_case.execute(
        UpdateUserProfileInputDTO(user_id=1, updates={"gender": Gender.FEMALE})
    )

    assert result.gender is Gender.FEMALE


async def test_invalid_value_raises_domain_exception():
    repo = FakeUserRepo([_user()])
    use_case = UpdateUserProfileUseCase(users=repo)

    with pytest.raises(InvalidUserAttributeException):
        await use_case.execute(UpdateUserProfileInputDTO(user_id=1, updates={"height": -5.0}))


async def test_changing_email_to_one_already_taken_raises():
    repo = FakeUserRepo([_user(user_id=1), _user(user_id=2, name="Taken")])
    repo._by_id[2].email = "taken@example.com"
    use_case = UpdateUserProfileUseCase(users=repo)

    with pytest.raises(UserAlreadyExistsException):
        await use_case.execute(
            UpdateUserProfileInputDTO(user_id=1, updates={"email": "taken@example.com"})
        )
```

- [ ] **Step 3: Run to verify these fail**

```bash
uv run pytest tests/unit/test_update_user_profile_use_case.py -v
```
Expected: FAIL — `ModuleNotFoundError: No module named 'src.application.use_cases.update_user_profile'`.

- [ ] **Step 4: Implement the use case**

Create `src/application/use_cases/update_user_profile.py`:

```python
"""Use case: partial update of the caller's own profile (PATCH /users/me).

True partial-patch semantics — only keys present in ``updates`` are applied;
everything else on the user is left exactly as it was. ``display_name`` is
the one field whose wire/DTO name doesn't match the domain attribute
(``User.name``), same mapping ``user_schemas.py`` already does for reads.
"""

from __future__ import annotations

from dataclasses import dataclass

from src.application.dtos.update_user_profile import UpdateUserProfileInputDTO
from src.application.dtos.user import UserOutputDTO
from src.application.ports.user_repository import UserRepositoryProtocol
from src.domain.exceptions import UserAlreadyExistsException, UserNotFoundException


@dataclass
class UpdateUserProfileUseCase:
    users: UserRepositoryProtocol

    async def execute(self, input_dto: UpdateUserProfileInputDTO) -> UserOutputDTO:
        user = await self.users.get_by_id(input_dto.user_id)
        if user is None:
            raise UserNotFoundException(f"user {input_dto.user_id} not found")

        updates = dict(input_dto.updates)
        if "display_name" in updates:
            updates["name"] = updates.pop("display_name")

        new_email = updates.get("email")
        if new_email is not None and new_email != user.email:
            existing = await self.users.get_by_email(new_email)
            if existing is not None and existing.id != user.id:
                raise UserAlreadyExistsException(f"user with email {new_email!r} already exists")

        for field, value in updates.items():
            setattr(user, field, value)
        user.__post_init__()

        updated = await self.users.update(user)
        return UserOutputDTO.from_entity(updated)
```

- [ ] **Step 5: Run to verify these pass**

```bash
uv run pytest tests/unit/test_update_user_profile_use_case.py -v
```
Expected: PASS.

- [ ] **Step 6: Add the request schema**

Edit `src/adapters/schemas/user_schemas.py`, append:

```python
class UpdateUserProfileRequest(CamelModel):
    """Partial patch — every field optional; omitted fields are left
    unchanged. ``extra="forbid"`` (overriding ``CamelModel``'s default)
    rejects ``id``/``createdAt``/``subscriptionTier`` in the body outright,
    rather than silently ignoring an attempt to self-grant Premium."""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, extra="forbid")

    email: str | None = None
    display_name: str | None = None
    gender: Gender | None = None
    birth_year: int | None = None
    unit_system: UnitSystem | None = None
    height: float | None = None
    weight_current: float | None = None
    weight_goal: float | None = None
    activity_level: ActivityLevel | None = None
    diet_type: DietType | None = None
    calorie_calc_mode: CalorieCalcMode | None = None
    calorie_left_mode: CalorieLeftMode | None = None
    weekly_rate_kg: float | None = None
```

Add `from pydantic import ConfigDict` and
`from pydantic.alias_generators import to_camel` to the file's imports.

- [ ] **Step 7: Add the controller route**

Edit `src/adapters/controllers/user_controller.py`:

```python
"""User endpoints. HTTP <-> application DTO translation only. No business rules here.

Creation now lives in the auth slice (`POST /auth/sign-up`); what remains here
is lookup by id, and `PATCH /me` for offline profile-edit sync (contract:
docs/backend-contracts/sync.md in the FoodFenFE repo). Not part of the
front-end contract for lookup-by-id (which uses `GET /auth/me` for the
caller's own profile) — kept as an extra.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, status

from src.adapters.schemas.user_schemas import UpdateUserProfileRequest, UserResponse
from src.application.dtos.update_user_profile import UpdateUserProfileInputDTO
from src.infrastructure.di import GetUserUseCaseDep, UpdateUserProfileUseCaseDep, get_current_user

router = APIRouter(
    prefix="/users",
    tags=["users"],
    dependencies=[Depends(get_current_user)],  # every route here needs auth
)


@router.get("/{user_id}", response_model=UserResponse, status_code=status.HTTP_200_OK)
async def get_user(user_id: int, use_case: GetUserUseCaseDep) -> UserResponse:
    result = await use_case.execute(user_id)
    return UserResponse.from_dto(result)


@router.patch("/me", response_model=UserResponse)
async def update_my_profile(
    body: UpdateUserProfileRequest,
    user: CurrentUserDep,
    use_case: UpdateUserProfileUseCaseDep,
) -> UserResponse:
    input_dto = UpdateUserProfileInputDTO(
        user_id=user.id, updates=body.model_dump(exclude_unset=True)
    )
    result = await use_case.execute(input_dto)
    return UserResponse.from_dto(result)
```

Add `CurrentUserDep` to the `from src.infrastructure.di import (...)` line
(needed for `update_my_profile`'s `user` parameter — `GET /{user_id}`
doesn't need it since it takes `user_id` from the path, only the router's
blanket `dependencies=[Depends(get_current_user)]` auth-gates it).

- [ ] **Step 8: Wire DI**

Edit `src/infrastructure/di/use_cases.py`:

```python
from src.application.use_cases.update_user_profile import UpdateUserProfileUseCase
```

```python
def get_update_user_profile_use_case(
    users: UserRepositoryDep,
) -> UpdateUserProfileUseCase:
    return UpdateUserProfileUseCase(users=users)


UpdateUserProfileUseCaseDep = Annotated[
    UpdateUserProfileUseCase, Depends(get_update_user_profile_use_case)
]
```

Edit `src/infrastructure/di/__init__.py` — add `UpdateUserProfileUseCaseDep`
and `get_update_user_profile_use_case` to the imports and `__all__`.

- [ ] **Step 9: Write the failing API tests**

Create `tests/api/test_update_user_profile_endpoint.py`:

```python
"""PATCH /users/me — end-to-end against the real app."""

from __future__ import annotations


async def test_patch_updates_only_the_sent_field(client, signed_up):
    headers = {"Authorization": f"Bearer {signed_up['accessToken']}"}

    resp = await client.patch("/users/me", json={"height": 180.0}, headers=headers)

    assert resp.status_code == 200
    body = resp.json()
    assert body["height"] == 180.0
    assert body["displayName"] == signed_up["displayName"]  # untouched


async def test_patch_requires_auth(client):
    resp = await client.patch("/users/me", json={"height": 180.0})
    assert resp.status_code == 401


async def test_patch_rejects_subscription_tier(client, signed_up):
    headers = {"Authorization": f"Bearer {signed_up['accessToken']}"}

    resp = await client.patch(
        "/users/me", json={"subscriptionTier": "premium"}, headers=headers
    )

    assert resp.status_code == 422


async def test_patch_display_name_updates_the_domain_name_field(client, signed_up):
    headers = {"Authorization": f"Bearer {signed_up['accessToken']}"}

    resp = await client.patch("/users/me", json={"displayName": "New Name"}, headers=headers)

    assert resp.status_code == 200
    assert resp.json()["displayName"] == "New Name"


async def test_patch_email_collision_returns_400_with_field_error(client, signed_up):
    headers = {"Authorization": f"Bearer {signed_up['accessToken']}"}
    await client.post(
        "/auth/sign-up",
        json={"email": "taken@example.com", "password": "s3cret-pass", "displayName": "Taken"},
    )

    resp = await client.patch("/users/me", json={"email": "taken@example.com"}, headers=headers)

    assert resp.status_code == 400
    assert "email" in resp.json()["errors"]
```

- [ ] **Step 10: Run to verify, then run the full suite**

```bash
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5433/foodfen_test uv run pytest tests/api/test_update_user_profile_endpoint.py -v
uv run pytest tests/unit -q
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5433/foodfen_test uv run pytest tests/integration tests/api -q
uv run lint-imports
```
Expected: all green.

- [ ] **Step 11: Commit**

```bash
git add src/application/dtos/update_user_profile.py \
  src/application/use_cases/update_user_profile.py \
  src/adapters/schemas/user_schemas.py \
  src/adapters/controllers/user_controller.py \
  src/infrastructure/di/use_cases.py src/infrastructure/di/__init__.py \
  tests/unit/test_update_user_profile_use_case.py \
  tests/api/test_update_user_profile_endpoint.py
git commit -m "feat: add PATCH /users/me for offline profile sync"
```
