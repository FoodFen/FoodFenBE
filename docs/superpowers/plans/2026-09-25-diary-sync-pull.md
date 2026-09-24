# Diary Sync Pull Endpoints (Phase 1) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Serve the five `GET` endpoints `FoodFenFE/docs/backend-contracts/sync.md` documents (`daily-goals`, `food-entries?from=&to=`, `activity-logs?from=&to=`, `water-logs?from=&to=`, `weight-logs?from=&to=`), plus the migration those responses depend on.

**Architecture:** Clean Architecture, inside-out, mirroring the `FoodEntry` slice already built this session: domain entities gain two new fields (`meal_type`, `logged_on`) landing together with their ORM columns and migration (they share a round-trip test that would otherwise break mid-plan), then four new list-by-date-range/list-by-user application slices, then repositories, DI wiring, and controllers.

**Tech Stack:** Python 3.11+, FastAPI, async SQLAlchemy 2.0 + asyncpg, Pydantic v2, Alembic, pytest/pytest-asyncio/httpx.

**Spec:** `docs/superpowers/specs/2026-09-24-diary-sync-pull-design.md`

## Global Constraints

- Layering: `domain` imports stdlib only; `application` imports stdlib + `domain` only. Run `uv run lint-imports` after touching imports — must stay green.
- Every new/changed ORM model needs its migration; `logged_on`/`meal_type` are `NOT NULL` — this repo has no real data yet beyond test fixtures, so no backfill step.
- Wire format is camelCase via `CamelModel`. Response field names must match `FoodFenFE/docs/backend-contracts/sync.md` exactly (`userId`, `foodEntryId`, `loggedOn`, `recordedAt`, etc.) — that file is the source of truth for every shape below, not re-derived here.
- New use-case providers go in `src/infrastructure/di/use_cases.py`; repository providers in `src/infrastructure/di/repositories.py`; both re-exported from `src/infrastructure/di/__init__.py`.
- Tests: `tests/unit/` = in-memory fakes, no DB. `tests/integration/` = real Postgres (`make docker-up` first). `tests/api/` = `httpx.AsyncClient` against the real app.
- Run tests with `uv run pytest <path> -v`.

## Review Focus

- **Empty result, not 404 or 500.** A user with zero daily goals, or no entries in a date range, gets `200` with `[]` — every list use case and its API test must prove this, not just the happy path with rows present.
- **Inclusive date-range boundaries.** A row logged exactly on `from` or exactly on `to` must be included, not just one strictly between them — the integration tests below assert both boundary dates explicitly, not just "somewhere inside the range."
- **Cross-user leakage.** Every list query filters by the requesting user's id — each integration test seeds a second user's row in the same date range and asserts it's excluded.
- **`from` is a Python keyword.** The query-param binding in Task 7 must alias it (`from_: Annotated[date, Query(alias="from")]`) — a naive `from: date` parameter is a `SyntaxError`, not a runtime bug, but worth calling out since it's easy to copy-paste wrong from the other four (non-keyword) endpoints.
- **`FoodEntry.create()`'s new required `meal_type` argument breaks every existing caller.** Both `tests/unit/test_entities.py`'s `_food_entry()` helper and `create_food_entry.py`'s use case call `FoodEntry.create(...)` today without it — Task 1 and Task 3 each fix one of these; missing either leaves a broken test or a broken endpoint.

---

### Task 1: Domain + ORM + migration — `MealType`, `logged_on` on `FoodEntry`/`ActivityLog`/`WaterLog`, `meal_type` on `FoodEntry`

Domain and ORM land together here (not split across tasks) because `tests/unit/test_entities.py`'s `ROUND_TRIPS` list round-trips every entity through its ORM class at **module import time** — a domain-only change would break that test file's collection until the matching ORM columns exist.

**Files:**
- Modify: `src/domain/enums.py` (append `MealType`)
- Modify: `src/domain/entities/food_entry.py`
- Modify: `src/domain/entities/activity_log.py`
- Modify: `src/domain/entities/water_log.py`
- Modify: `src/infrastructure/db/models/food_entry_model.py`
- Modify: `src/infrastructure/db/models/activity_log_model.py`
- Modify: `src/infrastructure/db/models/water_log_model.py`
- Modify: `tests/unit/test_entities.py`
- Create: `alembic/versions/0010_diary_sync_fields.py`

**Interfaces:**
- Produces: `MealType(StrEnum)` with `BREAKFAST/LUNCH/DINNER/SNACK`; `FoodEntry.create(..., meal_type: MealType, ..., logged_on: date | None = None)` (now requires `meal_type`); `FoodEntry.meal_type: MealType`, `FoodEntry.logged_on: date`; `ActivityLog.create(..., logged_on: date | None = None)`, `ActivityLog.logged_on: date`; `WaterLog.create(..., logged_on: date | None = None)`, `WaterLog.logged_on: date`.

- [ ] **Step 1: Add `MealType` to `src/domain/enums.py`**

Append after `class PaymentStatus(StrEnum): ...`:

```python
class MealType(StrEnum):
    BREAKFAST = "breakfast"
    LUNCH = "lunch"
    DINNER = "dinner"
    SNACK = "snack"
```

- [ ] **Step 2: Update the failing round-trip test's helper (write this before the domain change, so it fails for the right reason)**

In `tests/unit/test_entities.py`, add `MealType` to the enum import block:

```python
from src.domain.enums import (
    ActivitySource,
    CalorieLeftMode,
    CoinReason,
    Gender,
    InputMethod,
    MealType,
    PlanType,
    QuestType,
    SubscriptionStatus,
    SubscriptionTier,
)
```

Then change `_food_entry()`'s call to add `meal_type`:

```python
def _food_entry() -> FoodEntry:
    entry = FoodEntry.create(
        user_id=USER_ID,
        name="Post-workout lunch",
        input_method=InputMethod.IMAGE,
        total_kcal=520,
        carbs_g=45.0,
        protein_g=30.0,
        fat_g=22.5,
        meal_type=MealType.LUNCH,
        image_url="https://cdn.example/meal.jpg",
        fiber_g=6.0,
    )
    entry.ingredients = [
        Ingredient.create(entry.id, "chicken breast", 150.0, 250, 0.0, 46.0, 5.4, fiber_g=0.0),
        Ingredient.create(entry.id, "brown rice", 120.0, 140, 30.0, 3.0, 1.1),
    ]
    return entry
```

- [ ] **Step 3: Run the test file to verify it fails**

Run: `uv run pytest tests/unit/test_entities.py -v`
Expected: FAIL at collection — `TypeError: FoodEntry.create() missing 1 required positional argument: 'meal_type'` (the domain entity doesn't accept it yet).

- [ ] **Step 4: Update `src/domain/entities/food_entry.py`**

```python
"""FoodEntry entity — the aggregate root for one logged meal, owning its Ingredients."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from uuid import UUID, uuid4

from src.domain.entities.ingredient import Ingredient
from src.domain.enums import AiFeedback, InputMethod, MealType
from src.domain.validation import require_non_empty, require_non_negative


@dataclass
class FoodEntry:
    """One logged meal.

    ``fiber_g`` is a Premium-only field: it stays ``None`` for free-tier users
    rather than being stored as zero, so "not tracked" and "zero fibre" stay
    distinguishable. ``logged_on`` is the user's local calendar day, distinct
    from ``logged_at`` (a UTC instant) — the client supplies it, because only
    the device knows the user's actual local day at write time; deriving it
    from ``logged_at`` server-side would get the wrong day near midnight.
    """

    id: UUID
    user_id: int
    name: str
    input_method: InputMethod
    total_kcal: int
    carbs_g: float
    protein_g: float
    fat_g: float
    meal_type: MealType
    image_url: str | None = None
    fiber_g: float | None = None
    ai_feedback: AiFeedback | None = None
    logged_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    logged_on: date = field(default_factory=lambda: datetime.now(UTC).date())
    ingredients: list[Ingredient] = field(default_factory=list)

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
            image_url=image_url,
            fiber_g=fiber_g,
            logged_at=logged_at,
            logged_on=logged_on or logged_at.date(),
            ingredients=ingredients or [],
        )
```

- [ ] **Step 5: Update `src/domain/entities/activity_log.py`**

```python
"""ActivityLog entity — one exercise session, manual or synced from a health app."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from uuid import UUID, uuid4

from src.domain.enums import ActivitySource
from src.domain.validation import require_non_empty, require_non_negative


@dataclass
class ActivityLog:
    id: UUID
    user_id: int
    activity_type: str
    calories_burned: int
    source: ActivitySource = ActivitySource.MANUAL
    logged_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    logged_on: date = field(default_factory=lambda: datetime.now(UTC).date())

    def __post_init__(self) -> None:
        self.activity_type = require_non_empty(self.activity_type, "activity_type")
        require_non_negative(self.calories_burned, "calories_burned")

    @classmethod
    def create(
        cls,
        user_id: int,
        activity_type: str,
        calories_burned: int,
        source: ActivitySource = ActivitySource.MANUAL,
        logged_on: date | None = None,
    ) -> ActivityLog:
        logged_at = datetime.now(UTC)
        return cls(
            id=uuid4(),
            user_id=user_id,
            activity_type=activity_type,
            calories_burned=calories_burned,
            source=source,
            logged_at=logged_at,
            logged_on=logged_on or logged_at.date(),
        )
```

- [ ] **Step 6: Update `src/domain/entities/water_log.py`**

```python
"""WaterLog entity — one drink."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from uuid import UUID, uuid4

from src.domain.validation import require_positive


@dataclass
class WaterLog:
    id: UUID
    user_id: int
    amount_ml: int
    logged_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    logged_on: date = field(default_factory=lambda: datetime.now(UTC).date())

    def __post_init__(self) -> None:
        require_positive(self.amount_ml, "amount_ml")

    @classmethod
    def create(cls, user_id: int, amount_ml: int, logged_on: date | None = None) -> WaterLog:
        logged_at = datetime.now(UTC)
        return cls(
            id=uuid4(),
            user_id=user_id,
            amount_ml=amount_ml,
            logged_at=logged_at,
            logged_on=logged_on or logged_at.date(),
        )
```

- [ ] **Step 7: Update `src/infrastructure/db/models/food_entry_model.py`**

```python
"""ORM models for food entries and their ingredients."""

from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from sqlalchemy import Date, DateTime, Float, ForeignKey, Index, Integer, String
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.domain.entities.food_entry import FoodEntry
from src.domain.entities.ingredient import Ingredient
from src.domain.enums import AiFeedback, InputMethod, MealType
from src.infrastructure.db.base import Base
from src.infrastructure.db.mixins import UserOwned, UUIDPrimaryKey
from src.infrastructure.db.types import enum_column


class IngredientORM(UUIDPrimaryKey, Base):
    __tablename__ = "ingredients"

    food_entry_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("food_entries.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    quantity_g: Mapped[float] = mapped_column(Float, nullable=False)
    kcal: Mapped[int] = mapped_column(Integer, nullable=False)
    carbs_g: Mapped[float] = mapped_column(Float, nullable=False)
    protein_g: Mapped[float] = mapped_column(Float, nullable=False)
    fat_g: Mapped[float] = mapped_column(Float, nullable=False)
    fiber_g: Mapped[float | None] = mapped_column(Float, nullable=True)

    def to_domain(self) -> Ingredient:
        return Ingredient(
            id=self.id,
            food_entry_id=self.food_entry_id,
            name=self.name,
            quantity_g=self.quantity_g,
            kcal=self.kcal,
            carbs_g=self.carbs_g,
            protein_g=self.protein_g,
            fat_g=self.fat_g,
            fiber_g=self.fiber_g,
        )

    @staticmethod
    def from_domain(ingredient: Ingredient) -> IngredientORM:
        return IngredientORM(
            id=ingredient.id,
            food_entry_id=ingredient.food_entry_id,
            name=ingredient.name,
            quantity_g=ingredient.quantity_g,
            kcal=ingredient.kcal,
            carbs_g=ingredient.carbs_g,
            protein_g=ingredient.protein_g,
            fat_g=ingredient.fat_g,
            fiber_g=ingredient.fiber_g,
        )


class FoodEntryORM(UUIDPrimaryKey, UserOwned, Base):
    __tablename__ = "food_entries"
    __table_args__ = (
        Index("ix_food_entries_user_logged_at", "user_id", "logged_at"),
        Index("ix_food_entries_user_logged_on", "user_id", "logged_on"),
    )

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    input_method: Mapped[InputMethod] = mapped_column(
        enum_column(InputMethod, "input_method"), nullable=False
    )
    meal_type: Mapped[MealType] = mapped_column(enum_column(MealType, "meal_type"), nullable=False)
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

    # selectin (not the lazy default) so to_domain() can read .ingredients without
    # tripping MissingGreenlet on the async engine.
    ingredients: Mapped[list[IngredientORM]] = relationship(
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    def to_domain(self) -> FoodEntry:
        return FoodEntry(
            id=self.id,
            user_id=self.user_id,
            name=self.name,
            input_method=self.input_method,
            meal_type=self.meal_type,
            total_kcal=self.total_kcal,
            carbs_g=self.carbs_g,
            protein_g=self.protein_g,
            fat_g=self.fat_g,
            image_url=self.image_url,
            fiber_g=self.fiber_g,
            ai_feedback=self.ai_feedback,
            logged_at=self.logged_at,
            logged_on=self.logged_on,
            ingredients=[row.to_domain() for row in self.ingredients],
        )

    @staticmethod
    def from_domain(entry: FoodEntry) -> FoodEntryORM:
        return FoodEntryORM(
            id=entry.id,
            user_id=entry.user_id,
            name=entry.name,
            input_method=entry.input_method,
            meal_type=entry.meal_type,
            image_url=entry.image_url,
            total_kcal=entry.total_kcal,
            carbs_g=entry.carbs_g,
            protein_g=entry.protein_g,
            fat_g=entry.fat_g,
            fiber_g=entry.fiber_g,
            ai_feedback=entry.ai_feedback,
            logged_at=entry.logged_at,
            logged_on=entry.logged_on,
            ingredients=[IngredientORM.from_domain(i) for i in entry.ingredients],
        )
```

- [ ] **Step 8: Update `src/infrastructure/db/models/activity_log_model.py`**

```python
"""ORM model for activity logs."""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Date, DateTime, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from src.domain.entities.activity_log import ActivityLog
from src.domain.enums import ActivitySource
from src.infrastructure.db.base import Base
from src.infrastructure.db.mixins import UserOwned, UUIDPrimaryKey
from src.infrastructure.db.types import enum_column


class ActivityLogORM(UUIDPrimaryKey, UserOwned, Base):
    __tablename__ = "activity_logs"
    __table_args__ = (
        Index("ix_activity_logs_user_logged_at", "user_id", "logged_at"),
        Index("ix_activity_logs_user_logged_on", "user_id", "logged_on"),
    )

    activity_type: Mapped[str] = mapped_column(String(120), nullable=False)
    calories_burned: Mapped[int] = mapped_column(Integer, nullable=False)
    source: Mapped[ActivitySource] = mapped_column(
        enum_column(ActivitySource, "activity_source"),
        nullable=False,
        server_default=ActivitySource.MANUAL.value,
    )
    logged_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    logged_on: Mapped[date] = mapped_column(Date, nullable=False)

    def to_domain(self) -> ActivityLog:
        return ActivityLog(
            id=self.id,
            user_id=self.user_id,
            activity_type=self.activity_type,
            calories_burned=self.calories_burned,
            source=self.source,
            logged_at=self.logged_at,
            logged_on=self.logged_on,
        )

    @staticmethod
    def from_domain(log: ActivityLog) -> ActivityLogORM:
        return ActivityLogORM(
            id=log.id,
            user_id=log.user_id,
            activity_type=log.activity_type,
            calories_burned=log.calories_burned,
            source=log.source,
            logged_at=log.logged_at,
            logged_on=log.logged_on,
        )
```

- [ ] **Step 9: Update `src/infrastructure/db/models/water_log_model.py`**

```python
"""ORM model for water logs."""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Date, DateTime, Index, Integer
from sqlalchemy.orm import Mapped, mapped_column

from src.domain.entities.water_log import WaterLog
from src.infrastructure.db.base import Base
from src.infrastructure.db.mixins import UserOwned, UUIDPrimaryKey


class WaterLogORM(UUIDPrimaryKey, UserOwned, Base):
    __tablename__ = "water_logs"
    __table_args__ = (
        Index("ix_water_logs_user_logged_at", "user_id", "logged_at"),
        Index("ix_water_logs_user_logged_on", "user_id", "logged_on"),
    )

    amount_ml: Mapped[int] = mapped_column(Integer, nullable=False)
    logged_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    logged_on: Mapped[date] = mapped_column(Date, nullable=False)

    def to_domain(self) -> WaterLog:
        return WaterLog(
            id=self.id,
            user_id=self.user_id,
            amount_ml=self.amount_ml,
            logged_at=self.logged_at,
            logged_on=self.logged_on,
        )

    @staticmethod
    def from_domain(log: WaterLog) -> WaterLogORM:
        return WaterLogORM(
            id=log.id,
            user_id=log.user_id,
            amount_ml=log.amount_ml,
            logged_at=log.logged_at,
            logged_on=log.logged_on,
        )
```

- [ ] **Step 10: Run the round-trip test to verify it passes**

Run: `uv run pytest tests/unit/test_entities.py -v`
Expected: PASS (all `ROUND_TRIPS` cases, including `FoodEntry`/`ActivityLog`/`WaterLog`)

- [ ] **Step 11: Write the migration — `alembic/versions/0010_diary_sync_fields.py`**

```python
"""add meal_type/logged_on diary sync fields

Revision ID: 0010
Revises: 0009
Create Date: 2026-09-25
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0010"
down_revision: str | None = "0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_MEAL_TYPE = ("breakfast", "lunch", "dinner", "snack")


def upgrade() -> None:
    op.add_column("food_entries", sa.Column("meal_type", sa.String(length=9), nullable=False))
    op.add_column("food_entries", sa.Column("logged_on", sa.Date(), nullable=False))
    op.create_check_constraint("meal_type", "food_entries", f"meal_type IN {_MEAL_TYPE}")
    op.create_index("ix_food_entries_user_logged_on", "food_entries", ["user_id", "logged_on"])

    op.add_column("activity_logs", sa.Column("logged_on", sa.Date(), nullable=False))
    op.create_index("ix_activity_logs_user_logged_on", "activity_logs", ["user_id", "logged_on"])

    op.add_column("water_logs", sa.Column("logged_on", sa.Date(), nullable=False))
    op.create_index("ix_water_logs_user_logged_on", "water_logs", ["user_id", "logged_on"])


def downgrade() -> None:
    op.drop_index("ix_water_logs_user_logged_on", table_name="water_logs")
    op.drop_column("water_logs", "logged_on")

    op.drop_index("ix_activity_logs_user_logged_on", table_name="activity_logs")
    op.drop_column("activity_logs", "logged_on")

    op.drop_index("ix_food_entries_user_logged_on", table_name="food_entries")
    op.drop_constraint("ck_food_entries_meal_type", "food_entries", type_="check")
    op.drop_column("food_entries", "logged_on")
    op.drop_column("food_entries", "meal_type")
```

- [ ] **Step 12: Verify the migration matches the models, then apply it**

Run (needs `make docker-up` first): `uv run alembic upgrade head --sql`
Expected: DDL for the three `ALTER TABLE ADD COLUMN` statements, the `meal_type` CHECK constraint, and the two new indexes, matching the ORM models above — no errors.

Then: `uv run alembic upgrade head`
Expected: exits 0.

- [ ] **Step 13: Full unit suite still green (confirms nothing else broke)**

Run: `uv run pytest tests/unit -v`
Expected: `create_food_entry.py`'s own tests (`test_food_entry_use_cases.py`) will FAIL here —
that's Task 3's job to fix, not this task's. Confirm the failure is specifically
`TypeError: ... missing 1 required positional argument: 'meal_type'` in that file and
nowhere else; every other unit test file passes.

- [ ] **Step 14: Commit**

```bash
git add src/domain/enums.py src/domain/entities/food_entry.py src/domain/entities/activity_log.py src/domain/entities/water_log.py src/infrastructure/db/models/food_entry_model.py src/infrastructure/db/models/activity_log_model.py src/infrastructure/db/models/water_log_model.py tests/unit/test_entities.py alembic/versions/0010_diary_sync_fields.py
git commit -m "feat: add MealType and logged_on/meal_type diary sync fields"
```

---

### Task 2: Application — daily goals list slice

**Files:**
- Create: `src/application/ports/daily_goal_repository.py`
- Create: `src/application/dtos/daily_goal.py`
- Create: `src/application/use_cases/list_daily_goals.py`
- Test: `tests/unit/test_list_daily_goals_use_case.py`

**Interfaces:**
- Consumes: `DailyGoal` (existing domain entity)
- Produces: `DailyGoalRepositoryProtocol` (`list_by_user`), `DailyGoalOutputDTO` (`from_entity`), `ListDailyGoalsUseCase.execute(user_id: int) -> list[DailyGoalOutputDTO]`

- [ ] **Step 1: Write the failing test**

Create `tests/unit/test_list_daily_goals_use_case.py`:

```python
"""ListDailyGoalsUseCase unit tests. No I/O."""

from __future__ import annotations

from datetime import date

from src.application.use_cases.list_daily_goals import ListDailyGoalsUseCase
from src.domain.entities.daily_goal import DailyGoal


class FakeDailyGoalRepo:
    def __init__(self, goals: list[DailyGoal] | None = None) -> None:
        self._goals = goals or []

    async def list_by_user(self, user_id: int) -> list[DailyGoal]:
        return [g for g in self._goals if g.user_id == user_id]


async def test_returns_empty_list_when_user_has_no_goals():
    use_case = ListDailyGoalsUseCase(daily_goals=FakeDailyGoalRepo())
    assert await use_case.execute(1) == []


async def test_returns_dtos_for_the_users_goals():
    goal = DailyGoal.create(1, 2000, 200.0, 150.0, 60.0, 2500, date(2026, 1, 1))
    other_users_goal = DailyGoal.create(2, 1800, 180.0, 120.0, 50.0, 2000, date(2026, 1, 1))
    use_case = ListDailyGoalsUseCase(daily_goals=FakeDailyGoalRepo([goal, other_users_goal]))

    result = await use_case.execute(1)

    assert len(result) == 1
    assert result[0].target_kcal == 2000
    assert result[0].effective_date == date(2026, 1, 1)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_list_daily_goals_use_case.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.application.use_cases.list_daily_goals'`

- [ ] **Step 3: Write `src/application/ports/daily_goal_repository.py`**

```python
"""Persistence port for daily goals. Structural typing via Protocol."""

from __future__ import annotations

from typing import Protocol

from src.domain.entities.daily_goal import DailyGoal


class DailyGoalRepositoryProtocol(Protocol):
    async def list_by_user(self, user_id: int) -> list[DailyGoal]: ...
```

- [ ] **Step 4: Write `src/application/dtos/daily_goal.py`**

```python
"""Daily goal DTO — frozen dataclass, never a Pydantic model or ORM row."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from uuid import UUID

from src.domain.entities.daily_goal import DailyGoal


@dataclass(frozen=True)
class DailyGoalOutputDTO:
    id: UUID
    user_id: int
    target_kcal: int
    target_carbs_g: float
    target_protein_g: float
    target_fat_g: float
    target_water_ml: int
    effective_date: date

    @classmethod
    def from_entity(cls, goal: DailyGoal) -> DailyGoalOutputDTO:
        return cls(
            id=goal.id,
            user_id=goal.user_id,
            target_kcal=goal.target_kcal,
            target_carbs_g=goal.target_carbs_g,
            target_protein_g=goal.target_protein_g,
            target_fat_g=goal.target_fat_g,
            target_water_ml=goal.target_water_ml,
            effective_date=goal.effective_date,
        )
```

- [ ] **Step 5: Write `src/application/use_cases/list_daily_goals.py`**

```python
"""Use case: list every daily goal ever set for the account (append-only, all history)."""

from __future__ import annotations

from dataclasses import dataclass

from src.application.dtos.daily_goal import DailyGoalOutputDTO
from src.application.ports.daily_goal_repository import DailyGoalRepositoryProtocol


@dataclass
class ListDailyGoalsUseCase:
    daily_goals: DailyGoalRepositoryProtocol

    async def execute(self, user_id: int) -> list[DailyGoalOutputDTO]:
        goals = await self.daily_goals.list_by_user(user_id)
        return [DailyGoalOutputDTO.from_entity(g) for g in goals]
```

- [ ] **Step 6: Run test to verify it passes**

Run: `uv run pytest tests/unit/test_list_daily_goals_use_case.py -v`
Expected: PASS (2 tests)

- [ ] **Step 7: Commit**

```bash
git add src/application/ports/daily_goal_repository.py src/application/dtos/daily_goal.py src/application/use_cases/list_daily_goals.py tests/unit/test_list_daily_goals_use_case.py
git commit -m "feat: add daily goals list use case"
```

---

### Task 3: Application — extend the `FoodEntry` slice (`meal_type`/`logged_on`/`userId`/`foodEntryId` fields, date-range list)

**Files:**
- Modify: `src/application/dtos/food_entry.py`
- Modify: `src/application/ports/food_entry_repository.py`
- Modify: `src/application/use_cases/create_food_entry.py`
- Create: `src/application/use_cases/list_food_entries.py`
- Modify: `tests/unit/test_food_entry_use_cases.py`

**Interfaces:**
- Consumes: `FoodEntry`/`Ingredient` (Task 1's updated entities)
- Produces: `FoodEntryRepositoryProtocol.list_by_date_range(user_id, from_date, to_date) -> list[FoodEntry]` (added to the existing protocol); `CreateFoodEntryInputDTO` gains `meal_type: MealType`; `FoodEntryOutputDTO` gains `user_id: int`, `meal_type: MealType`, `logged_on: date`; `IngredientOutputDTO` gains `food_entry_id: UUID`; `ListFoodEntriesUseCase.execute(user_id, from_date, to_date) -> list[FoodEntryOutputDTO]`.

- [ ] **Step 1: Write the failing tests**

Rewrite `tests/unit/test_food_entry_use_cases.py`:

```python
"""CreateFoodEntryUseCase / GetFoodEntryUseCase / ListFoodEntriesUseCase unit tests. No I/O."""

from __future__ import annotations

from datetime import date

import pytest

from src.application.dtos.food_entry import CreateFoodEntryInputDTO, CreateIngredientInputDTO
from src.application.use_cases.create_food_entry import CreateFoodEntryUseCase
from src.application.use_cases.get_food_entry import GetFoodEntryUseCase
from src.application.use_cases.list_food_entries import ListFoodEntriesUseCase
from src.domain.entities.food_entry import FoodEntry
from src.domain.enums import InputMethod, MealType
from src.domain.exceptions import FoodEntryNotFoundException


class FakeFoodEntryRepo:
    def __init__(self) -> None:
        self._by_id: dict = {}

    async def create(self, entry: FoodEntry) -> FoodEntry:
        self._by_id[entry.id] = entry
        return entry

    async def get_by_id(self, entry_id):
        return self._by_id.get(entry_id)

    async def list_by_date_range(self, user_id, from_date, to_date):
        return [
            e
            for e in self._by_id.values()
            if e.user_id == user_id and from_date <= e.logged_on <= to_date
        ]


def _input_dto(fiber_g=None, ingredient_fiber_g=None, meal_type=MealType.LUNCH) -> CreateFoodEntryInputDTO:
    return CreateFoodEntryInputDTO(
        user_id=1,
        name="Grilled chicken with rice",
        input_method=InputMethod.MANUAL,
        total_kcal=650,
        carbs_g=70.0,
        protein_g=45.0,
        fat_g=15.0,
        meal_type=meal_type,
        image_url=None,
        fiber_g=fiber_g,
        ingredients=[
            CreateIngredientInputDTO(
                name="chicken breast",
                quantity_g=200.0,
                kcal=330,
                carbs_g=0.0,
                protein_g=40.0,
                fat_g=15.0,
                fiber_g=ingredient_fiber_g,
            )
        ],
    )


async def test_fiber_g_is_always_stored_regardless_of_tier():
    """Premium gates fiber_g *display* client-side only — the server never
    drops it, or a free user who later upgrades permanently loses data they
    already logged (mirrors ai-food-capture.md's "no Premium check" rule)."""
    use_case = CreateFoodEntryUseCase(food_entries=FakeFoodEntryRepo())
    result = await use_case.execute(_input_dto(fiber_g=8.0, ingredient_fiber_g=2.0))
    assert result.fiber_g == 8.0
    assert result.ingredients[0].fiber_g == 2.0


async def test_fiber_g_stays_none_when_not_submitted():
    use_case = CreateFoodEntryUseCase(food_entries=FakeFoodEntryRepo())
    result = await use_case.execute(_input_dto())
    assert result.fiber_g is None
    assert result.ingredients[0].fiber_g is None


async def test_create_result_carries_user_id_meal_type_and_ingredient_food_entry_id():
    use_case = CreateFoodEntryUseCase(food_entries=FakeFoodEntryRepo())
    result = await use_case.execute(_input_dto(meal_type=MealType.BREAKFAST))
    assert result.user_id == 1
    assert result.meal_type is MealType.BREAKFAST
    assert result.ingredients[0].food_entry_id == result.id


async def test_get_returns_entry_for_its_owner():
    repo = FakeFoodEntryRepo()
    create_use_case = CreateFoodEntryUseCase(food_entries=repo)
    created = await create_use_case.execute(_input_dto())

    get_use_case = GetFoodEntryUseCase(food_entries=repo)
    result = await get_use_case.execute(user_id=1, entry_id=created.id)
    assert result.id == created.id


async def test_get_raises_not_found_for_another_users_entry():
    repo = FakeFoodEntryRepo()
    created = await CreateFoodEntryUseCase(food_entries=repo).execute(_input_dto())

    get_use_case = GetFoodEntryUseCase(food_entries=repo)
    with pytest.raises(FoodEntryNotFoundException):
        await get_use_case.execute(user_id=999, entry_id=created.id)


async def test_list_returns_empty_when_nothing_in_range():
    repo = FakeFoodEntryRepo()
    use_case = ListFoodEntriesUseCase(food_entries=repo)
    result = await use_case.execute(user_id=1, from_date=date(2026, 1, 1), to_date=date(2026, 1, 31))
    assert result == []


async def test_list_returns_entries_created_via_the_create_use_case():
    repo = FakeFoodEntryRepo()
    created = await CreateFoodEntryUseCase(food_entries=repo).execute(_input_dto())

    use_case = ListFoodEntriesUseCase(food_entries=repo)
    result = await use_case.execute(
        user_id=1, from_date=created.logged_on, to_date=created.logged_on
    )

    assert [r.id for r in result] == [created.id]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/test_food_entry_use_cases.py -v`
Expected: FAIL — `TypeError: CreateFoodEntryInputDTO.__init__() got an unexpected keyword argument 'meal_type'`

- [ ] **Step 3: Update `src/application/dtos/food_entry.py`**

```python
"""Food entry / ingredient DTOs — frozen dataclasses, never a Pydantic model or ORM row."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from uuid import UUID

from src.domain.entities.food_entry import FoodEntry
from src.domain.entities.ingredient import Ingredient
from src.domain.enums import AiFeedback, InputMethod, MealType


@dataclass(frozen=True)
class CreateIngredientInputDTO:
    name: str
    quantity_g: float
    kcal: int
    carbs_g: float
    protein_g: float
    fat_g: float
    fiber_g: float | None = None


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
    image_url: str | None = None
    fiber_g: float | None = None
    ingredients: list[CreateIngredientInputDTO] | None = None


@dataclass(frozen=True)
class IngredientOutputDTO:
    id: UUID
    food_entry_id: UUID
    name: str
    quantity_g: float
    kcal: int
    carbs_g: float
    protein_g: float
    fat_g: float
    fiber_g: float | None

    @classmethod
    def from_entity(cls, ingredient: Ingredient) -> IngredientOutputDTO:
        return cls(
            id=ingredient.id,
            food_entry_id=ingredient.food_entry_id,
            name=ingredient.name,
            quantity_g=ingredient.quantity_g,
            kcal=ingredient.kcal,
            carbs_g=ingredient.carbs_g,
            protein_g=ingredient.protein_g,
            fat_g=ingredient.fat_g,
            fiber_g=ingredient.fiber_g,
        )


@dataclass(frozen=True)
class FoodEntryOutputDTO:
    id: UUID
    user_id: int
    name: str
    input_method: InputMethod
    meal_type: MealType
    total_kcal: int
    carbs_g: float
    protein_g: float
    fat_g: float
    image_url: str | None
    fiber_g: float | None
    ai_feedback: AiFeedback | None
    logged_at: datetime
    logged_on: date
    ingredients: list[IngredientOutputDTO]

    @classmethod
    def from_entity(cls, entry: FoodEntry) -> FoodEntryOutputDTO:
        return cls(
            id=entry.id,
            user_id=entry.user_id,
            name=entry.name,
            input_method=entry.input_method,
            meal_type=entry.meal_type,
            total_kcal=entry.total_kcal,
            carbs_g=entry.carbs_g,
            protein_g=entry.protein_g,
            fat_g=entry.fat_g,
            image_url=entry.image_url,
            fiber_g=entry.fiber_g,
            ai_feedback=entry.ai_feedback,
            logged_at=entry.logged_at,
            logged_on=entry.logged_on,
            ingredients=[IngredientOutputDTO.from_entity(i) for i in entry.ingredients],
        )
```

- [ ] **Step 4: Add `list_by_date_range` to `src/application/ports/food_entry_repository.py`**

```python
"""Persistence port for food entries. Structural typing via Protocol."""

from __future__ import annotations

from datetime import date
from typing import Protocol
from uuid import UUID

from src.domain.entities.food_entry import FoodEntry


class FoodEntryRepositoryProtocol(Protocol):
    async def create(self, entry: FoodEntry) -> FoodEntry: ...

    async def get_by_id(self, entry_id: UUID) -> FoodEntry | None: ...

    async def list_by_date_range(
        self, user_id: int, from_date: date, to_date: date
    ) -> list[FoodEntry]:
        """Inclusive range, filtered on ``logged_on``."""
        ...
```

- [ ] **Step 5: Add `meal_type` to `src/application/use_cases/create_food_entry.py`'s `FoodEntry.create(...)` call**

Change:

```python
        entry = FoodEntry.create(
            user_id=input_dto.user_id,
            name=input_dto.name,
            input_method=input_dto.input_method,
            total_kcal=input_dto.total_kcal,
            carbs_g=input_dto.carbs_g,
            protein_g=input_dto.protein_g,
            fat_g=input_dto.fat_g,
            image_url=input_dto.image_url,
            fiber_g=input_dto.fiber_g,
        )
```

to:

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
            image_url=input_dto.image_url,
            fiber_g=input_dto.fiber_g,
        )
```

- [ ] **Step 6: Write `src/application/use_cases/list_food_entries.py`**

```python
"""Use case: list food entries logged in an inclusive date range."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from src.application.dtos.food_entry import FoodEntryOutputDTO
from src.application.ports.food_entry_repository import FoodEntryRepositoryProtocol


@dataclass
class ListFoodEntriesUseCase:
    food_entries: FoodEntryRepositoryProtocol

    async def execute(self, user_id: int, from_date: date, to_date: date) -> list[FoodEntryOutputDTO]:
        entries = await self.food_entries.list_by_date_range(user_id, from_date, to_date)
        return [FoodEntryOutputDTO.from_entity(e) for e in entries]
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `uv run pytest tests/unit/test_food_entry_use_cases.py -v`
Expected: PASS (8 tests)

- [ ] **Step 8: Commit**

```bash
git add src/application/dtos/food_entry.py src/application/ports/food_entry_repository.py src/application/use_cases/create_food_entry.py src/application/use_cases/list_food_entries.py tests/unit/test_food_entry_use_cases.py
git commit -m "feat: extend FoodEntry slice with meal_type/logged_on and date-range listing"
```

---

### Task 4: Application — activity log, water log, weight log list slices

**Files:**
- Create: `src/application/ports/activity_log_repository.py`, `src/application/ports/water_log_repository.py`, `src/application/ports/weight_log_repository.py`
- Create: `src/application/dtos/activity_log.py`, `src/application/dtos/water_log.py`, `src/application/dtos/weight_log.py`
- Create: `src/application/use_cases/list_activity_logs.py`, `src/application/use_cases/list_water_logs.py`, `src/application/use_cases/list_weight_logs.py`
- Test: `tests/unit/test_list_diary_log_use_cases.py`

**Interfaces:**
- Consumes: `ActivityLog`/`WaterLog`/`WeightLog` (existing/Task-1-updated domain entities)
- Produces: `ActivityLogRepositoryProtocol`/`WaterLogRepositoryProtocol`/`WeightLogRepositoryProtocol`, each `list_by_date_range(user_id, from_date, to_date) -> list[...]`; `ActivityLogOutputDTO`/`WaterLogOutputDTO`/`WeightLogOutputDTO`, each `from_entity`; `ListActivityLogsUseCase`/`ListWaterLogsUseCase`/`ListWeightLogsUseCase`, each `.execute(user_id, from_date, to_date) -> list[...OutputDTO]`.

- [ ] **Step 1: Write the failing tests**

Create `tests/unit/test_list_diary_log_use_cases.py`:

```python
"""ListActivityLogsUseCase / ListWaterLogsUseCase / ListWeightLogsUseCase unit tests. No I/O."""

from __future__ import annotations

from datetime import date

from src.application.use_cases.list_activity_logs import ListActivityLogsUseCase
from src.application.use_cases.list_water_logs import ListWaterLogsUseCase
from src.application.use_cases.list_weight_logs import ListWeightLogsUseCase
from src.domain.entities.activity_log import ActivityLog
from src.domain.entities.water_log import WaterLog
from src.domain.entities.weight_log import WeightLog


class FakeActivityLogRepo:
    def __init__(self, logs: list[ActivityLog] | None = None) -> None:
        self._logs = logs or []

    async def list_by_date_range(self, user_id, from_date, to_date):
        return [
            log
            for log in self._logs
            if log.user_id == user_id and from_date <= log.logged_on <= to_date
        ]


class FakeWaterLogRepo:
    def __init__(self, logs: list[WaterLog] | None = None) -> None:
        self._logs = logs or []

    async def list_by_date_range(self, user_id, from_date, to_date):
        return [
            log
            for log in self._logs
            if log.user_id == user_id and from_date <= log.logged_on <= to_date
        ]


class FakeWeightLogRepo:
    def __init__(self, logs: list[WeightLog] | None = None) -> None:
        self._logs = logs or []

    async def list_by_date_range(self, user_id, from_date, to_date):
        return [
            log
            for log in self._logs
            if log.user_id == user_id and from_date <= log.recorded_at <= to_date
        ]


async def test_activity_logs_empty_when_none_in_range():
    use_case = ListActivityLogsUseCase(activity_logs=FakeActivityLogRepo())
    result = await use_case.execute(1, date(2026, 1, 1), date(2026, 1, 31))
    assert result == []


async def test_activity_logs_returns_dtos():
    log = ActivityLog.create(1, "running", 320, logged_on=date(2026, 1, 15))
    use_case = ListActivityLogsUseCase(activity_logs=FakeActivityLogRepo([log]))
    result = await use_case.execute(1, date(2026, 1, 1), date(2026, 1, 31))
    assert len(result) == 1
    assert result[0].activity_type == "running"
    assert result[0].logged_on == date(2026, 1, 15)


async def test_water_logs_empty_when_none_in_range():
    use_case = ListWaterLogsUseCase(water_logs=FakeWaterLogRepo())
    result = await use_case.execute(1, date(2026, 1, 1), date(2026, 1, 31))
    assert result == []


async def test_water_logs_returns_dtos():
    log = WaterLog.create(1, 350, logged_on=date(2026, 1, 15))
    use_case = ListWaterLogsUseCase(water_logs=FakeWaterLogRepo([log]))
    result = await use_case.execute(1, date(2026, 1, 1), date(2026, 1, 31))
    assert len(result) == 1
    assert result[0].amount_ml == 350


async def test_weight_logs_empty_when_none_in_range():
    use_case = ListWeightLogsUseCase(weight_logs=FakeWeightLogRepo())
    result = await use_case.execute(1, date(2026, 1, 1), date(2026, 1, 31))
    assert result == []


async def test_weight_logs_returns_dtos():
    log = WeightLog.create(1, 60.4, date(2026, 1, 15))
    use_case = ListWeightLogsUseCase(weight_logs=FakeWeightLogRepo([log]))
    result = await use_case.execute(1, date(2026, 1, 1), date(2026, 1, 31))
    assert len(result) == 1
    assert result[0].weight == 60.4
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/test_list_diary_log_use_cases.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.application.use_cases.list_activity_logs'`

- [ ] **Step 3: Write the three ports**

`src/application/ports/activity_log_repository.py`:

```python
"""Persistence port for activity logs. Structural typing via Protocol."""

from __future__ import annotations

from datetime import date
from typing import Protocol

from src.domain.entities.activity_log import ActivityLog


class ActivityLogRepositoryProtocol(Protocol):
    async def list_by_date_range(
        self, user_id: int, from_date: date, to_date: date
    ) -> list[ActivityLog]:
        """Inclusive range, filtered on ``logged_on``."""
        ...
```

`src/application/ports/water_log_repository.py`:

```python
"""Persistence port for water logs. Structural typing via Protocol."""

from __future__ import annotations

from datetime import date
from typing import Protocol

from src.domain.entities.water_log import WaterLog


class WaterLogRepositoryProtocol(Protocol):
    async def list_by_date_range(
        self, user_id: int, from_date: date, to_date: date
    ) -> list[WaterLog]:
        """Inclusive range, filtered on ``logged_on``."""
        ...
```

`src/application/ports/weight_log_repository.py`:

```python
"""Persistence port for weight logs. Structural typing via Protocol."""

from __future__ import annotations

from datetime import date
from typing import Protocol

from src.domain.entities.weight_log import WeightLog


class WeightLogRepositoryProtocol(Protocol):
    async def list_by_date_range(
        self, user_id: int, from_date: date, to_date: date
    ) -> list[WeightLog]:
        """Inclusive range, filtered on ``recorded_at``."""
        ...
```

- [ ] **Step 4: Write the three DTOs**

`src/application/dtos/activity_log.py`:

```python
"""Activity log DTO — frozen dataclass, never a Pydantic model or ORM row."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from uuid import UUID

from src.domain.entities.activity_log import ActivityLog
from src.domain.enums import ActivitySource


@dataclass(frozen=True)
class ActivityLogOutputDTO:
    id: UUID
    user_id: int
    activity_type: str
    calories_burned: int
    source: ActivitySource
    logged_at: datetime
    logged_on: date

    @classmethod
    def from_entity(cls, log: ActivityLog) -> ActivityLogOutputDTO:
        return cls(
            id=log.id,
            user_id=log.user_id,
            activity_type=log.activity_type,
            calories_burned=log.calories_burned,
            source=log.source,
            logged_at=log.logged_at,
            logged_on=log.logged_on,
        )
```

`src/application/dtos/water_log.py`:

```python
"""Water log DTO — frozen dataclass, never a Pydantic model or ORM row."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from uuid import UUID

from src.domain.entities.water_log import WaterLog


@dataclass(frozen=True)
class WaterLogOutputDTO:
    id: UUID
    user_id: int
    amount_ml: int
    logged_at: datetime
    logged_on: date

    @classmethod
    def from_entity(cls, log: WaterLog) -> WaterLogOutputDTO:
        return cls(
            id=log.id,
            user_id=log.user_id,
            amount_ml=log.amount_ml,
            logged_at=log.logged_at,
            logged_on=log.logged_on,
        )
```

`src/application/dtos/weight_log.py`:

```python
"""Weight log DTO — frozen dataclass, never a Pydantic model or ORM row."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from uuid import UUID

from src.domain.entities.weight_log import WeightLog


@dataclass(frozen=True)
class WeightLogOutputDTO:
    id: UUID
    user_id: int
    weight: float
    recorded_at: date

    @classmethod
    def from_entity(cls, log: WeightLog) -> WeightLogOutputDTO:
        return cls(
            id=log.id,
            user_id=log.user_id,
            weight=log.weight,
            recorded_at=log.recorded_at,
        )
```

- [ ] **Step 5: Write the three use cases**

`src/application/use_cases/list_activity_logs.py`:

```python
"""Use case: list activity logs in an inclusive date range."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from src.application.dtos.activity_log import ActivityLogOutputDTO
from src.application.ports.activity_log_repository import ActivityLogRepositoryProtocol


@dataclass
class ListActivityLogsUseCase:
    activity_logs: ActivityLogRepositoryProtocol

    async def execute(self, user_id: int, from_date: date, to_date: date) -> list[ActivityLogOutputDTO]:
        logs = await self.activity_logs.list_by_date_range(user_id, from_date, to_date)
        return [ActivityLogOutputDTO.from_entity(log) for log in logs]
```

`src/application/use_cases/list_water_logs.py`:

```python
"""Use case: list water logs in an inclusive date range."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from src.application.dtos.water_log import WaterLogOutputDTO
from src.application.ports.water_log_repository import WaterLogRepositoryProtocol


@dataclass
class ListWaterLogsUseCase:
    water_logs: WaterLogRepositoryProtocol

    async def execute(self, user_id: int, from_date: date, to_date: date) -> list[WaterLogOutputDTO]:
        logs = await self.water_logs.list_by_date_range(user_id, from_date, to_date)
        return [WaterLogOutputDTO.from_entity(log) for log in logs]
```

`src/application/use_cases/list_weight_logs.py`:

```python
"""Use case: list weight logs in an inclusive date range."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from src.application.dtos.weight_log import WeightLogOutputDTO
from src.application.ports.weight_log_repository import WeightLogRepositoryProtocol


@dataclass
class ListWeightLogsUseCase:
    weight_logs: WeightLogRepositoryProtocol

    async def execute(self, user_id: int, from_date: date, to_date: date) -> list[WeightLogOutputDTO]:
        logs = await self.weight_logs.list_by_date_range(user_id, from_date, to_date)
        return [WeightLogOutputDTO.from_entity(log) for log in logs]
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `uv run pytest tests/unit/test_list_diary_log_use_cases.py -v`
Expected: PASS (6 tests)

- [ ] **Step 7: Commit**

```bash
git add src/application/ports/activity_log_repository.py src/application/ports/water_log_repository.py src/application/ports/weight_log_repository.py src/application/dtos/activity_log.py src/application/dtos/water_log.py src/application/dtos/weight_log.py src/application/use_cases/list_activity_logs.py src/application/use_cases/list_water_logs.py src/application/use_cases/list_weight_logs.py tests/unit/test_list_diary_log_use_cases.py
git commit -m "feat: add activity log, water log, weight log list use cases"
```

---

### Task 5: Infrastructure — repositories for all five resources

**Files:**
- Create: `src/infrastructure/db/repositories/daily_goal_repository.py`, `src/infrastructure/db/repositories/activity_log_repository.py`, `src/infrastructure/db/repositories/water_log_repository.py`, `src/infrastructure/db/repositories/weight_log_repository.py`
- Modify: `src/infrastructure/db/repositories/food_entry_repository.py`
- Test: `tests/integration/test_diary_sync_repositories.py`

**Interfaces:**
- Consumes: `DailyGoalORM`/`ActivityLogORM`/`WaterLogORM`/`WeightLogORM`/`FoodEntryORM` (existing/Task-1-updated ORM models)
- Produces: `SQLAlchemyDailyGoalRepository`, `SQLAlchemyActivityLogRepository`, `SQLAlchemyWaterLogRepository`, `SQLAlchemyWeightLogRepository` (each implementing its Task 2/4 protocol); `SQLAlchemyFoodEntryRepository.list_by_date_range`.

- [ ] **Step 1: Write the failing integration tests**

Create `tests/integration/test_diary_sync_repositories.py`:

```python
"""Integration tests: the five diary-sync repositories against a real PostgreSQL.

Requires a reachable database. Override with TEST_DATABASE_URL; defaults to the
``foodfen`` database from docker-compose. The schema is (re)created per test.
"""

from __future__ import annotations

import os
from datetime import date

import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from src.domain.entities.activity_log import ActivityLog
from src.domain.entities.daily_goal import DailyGoal
from src.domain.entities.food_entry import FoodEntry
from src.domain.entities.user import User
from src.domain.entities.water_log import WaterLog
from src.domain.entities.weight_log import WeightLog
from src.domain.enums import InputMethod, MealType
from src.infrastructure.db.base import Base
from src.infrastructure.db.models.activity_log_model import ActivityLogORM  # noqa: F401
from src.infrastructure.db.models.daily_goal_model import DailyGoalORM  # noqa: F401
from src.infrastructure.db.models.food_entry_model import FoodEntryORM  # noqa: F401
from src.infrastructure.db.models.user_model import UserORM  # noqa: F401
from src.infrastructure.db.models.water_log_model import WaterLogORM  # noqa: F401
from src.infrastructure.db.models.weight_log_model import WeightLogORM  # noqa: F401
from src.infrastructure.db.repositories.activity_log_repository import (
    SQLAlchemyActivityLogRepository,
)
from src.infrastructure.db.repositories.daily_goal_repository import SQLAlchemyDailyGoalRepository
from src.infrastructure.db.repositories.food_entry_repository import SQLAlchemyFoodEntryRepository
from src.infrastructure.db.repositories.user_repository import SQLAlchemyUserRepository
from src.infrastructure.db.repositories.water_log_repository import SQLAlchemyWaterLogRepository
from src.infrastructure.db.repositories.weight_log_repository import SQLAlchemyWeightLogRepository

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


async def _make_two_users(session) -> tuple[User, User]:
    repo = SQLAlchemyUserRepository(session)
    a = await repo.create(User.create(email="a@example.com"))
    b = await repo.create(User.create(email="b@example.com"))
    await session.commit()
    return a, b


async def test_daily_goal_repository_lists_only_the_users_goals(session):
    user_a, user_b = await _make_two_users(session)
    repo = SQLAlchemyDailyGoalRepository(session)
    await repo.create(
        DailyGoal.create(user_a.id, 2000, 200.0, 150.0, 60.0, 2500, date(2026, 1, 1))
    ) if hasattr(repo, "create") else None

    # DailyGoalRepositoryProtocol only defines list_by_user for phase 1 — insert
    # directly via the domain->ORM mapping the same way `create` will once push exists.
    from src.infrastructure.db.models.daily_goal_model import DailyGoalORM as _DailyGoalORM

    session.add(_DailyGoalORM.from_domain(
        DailyGoal.create(user_a.id, 2000, 200.0, 150.0, 60.0, 2500, date(2026, 1, 1))
    ))
    session.add(_DailyGoalORM.from_domain(
        DailyGoal.create(user_b.id, 1800, 180.0, 120.0, 50.0, 2000, date(2026, 1, 1))
    ))
    await session.flush()
    await session.commit()

    result = await repo.list_by_user(user_a.id)

    assert len(result) == 1
    assert result[0].target_kcal == 2000


async def test_food_entry_repository_list_by_date_range_is_inclusive_and_scoped(session):
    user_a, user_b = await _make_two_users(session)
    repo = SQLAlchemyFoodEntryRepository(session)

    def _entry(user_id: int, logged_on: date) -> FoodEntry:
        return FoodEntry.create(
            user_id=user_id,
            name="Meal",
            input_method=InputMethod.MANUAL,
            total_kcal=500,
            carbs_g=50.0,
            protein_g=30.0,
            fat_g=10.0,
            meal_type=MealType.LUNCH,
            logged_on=logged_on,
        )

    await repo.create(_entry(user_a.id, date(2026, 1, 1)))  # lower boundary
    await repo.create(_entry(user_a.id, date(2026, 1, 31)))  # upper boundary
    await repo.create(_entry(user_a.id, date(2026, 2, 1)))  # outside range
    await repo.create(_entry(user_b.id, date(2026, 1, 15)))  # different user
    await session.commit()

    result = await repo.list_by_date_range(user_a.id, date(2026, 1, 1), date(2026, 1, 31))

    assert len(result) == 2
    assert {e.logged_on for e in result} == {date(2026, 1, 1), date(2026, 1, 31)}


async def test_activity_log_repository_list_by_date_range(session):
    user_a, user_b = await _make_two_users(session)
    repo = SQLAlchemyActivityLogRepository(session)

    session.add(_orm(ActivityLog.create(user_a.id, "running", 300, logged_on=date(2026, 1, 15))))
    session.add(_orm(ActivityLog.create(user_b.id, "running", 300, logged_on=date(2026, 1, 15))))
    await session.flush()
    await session.commit()

    result = await repo.list_by_date_range(user_a.id, date(2026, 1, 1), date(2026, 1, 31))
    assert len(result) == 1
    assert result[0].user_id == user_a.id


async def test_water_log_repository_list_by_date_range(session):
    user_a, user_b = await _make_two_users(session)
    repo = SQLAlchemyWaterLogRepository(session)

    session.add(_orm(WaterLog.create(user_a.id, 350, logged_on=date(2026, 1, 15))))
    session.add(_orm(WaterLog.create(user_b.id, 350, logged_on=date(2026, 1, 15))))
    await session.flush()
    await session.commit()

    result = await repo.list_by_date_range(user_a.id, date(2026, 1, 1), date(2026, 1, 31))
    assert len(result) == 1
    assert result[0].user_id == user_a.id


async def test_weight_log_repository_list_by_date_range(session):
    user_a, user_b = await _make_two_users(session)
    repo = SQLAlchemyWeightLogRepository(session)

    session.add(_orm(WeightLog.create(user_a.id, 60.4, date(2026, 1, 15))))
    session.add(_orm(WeightLog.create(user_b.id, 60.4, date(2026, 1, 15))))
    await session.flush()
    await session.commit()

    result = await repo.list_by_date_range(user_a.id, date(2026, 1, 1), date(2026, 1, 31))
    assert len(result) == 1
    assert result[0].user_id == user_a.id


def _orm(entity):
    """Map any of the three simple log entities to its ORM row via its own from_domain."""
    from src.infrastructure.db.models.activity_log_model import ActivityLogORM
    from src.infrastructure.db.models.water_log_model import WaterLogORM
    from src.infrastructure.db.models.weight_log_model import WeightLogORM

    if isinstance(entity, ActivityLog):
        return ActivityLogORM.from_domain(entity)
    if isinstance(entity, WaterLog):
        return WaterLogORM.from_domain(entity)
    if isinstance(entity, WeightLog):
        return WeightLogORM.from_domain(entity)
    raise TypeError(type(entity))
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/integration/test_diary_sync_repositories.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.infrastructure.db.repositories.daily_goal_repository'`

- [ ] **Step 3: Write `src/infrastructure/db/repositories/daily_goal_repository.py`**

```python
"""Concrete ``DailyGoalRepositoryProtocol`` implementation backed by async SQLAlchemy."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.entities.daily_goal import DailyGoal
from src.infrastructure.db.models.daily_goal_model import DailyGoalORM


class SQLAlchemyDailyGoalRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_by_user(self, user_id: int) -> list[DailyGoal]:
        rows = (
            await self._session.execute(
                select(DailyGoalORM)
                .where(DailyGoalORM.user_id == user_id)
                .order_by(DailyGoalORM.effective_date)
            )
        ).scalars().all()
        return [row.to_domain() for row in rows]
```

- [ ] **Step 4: Write `src/infrastructure/db/repositories/activity_log_repository.py`**

```python
"""Concrete ``ActivityLogRepositoryProtocol`` implementation backed by async SQLAlchemy."""

from __future__ import annotations

from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.entities.activity_log import ActivityLog
from src.infrastructure.db.models.activity_log_model import ActivityLogORM


class SQLAlchemyActivityLogRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

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

- [ ] **Step 5: Write `src/infrastructure/db/repositories/water_log_repository.py`**

```python
"""Concrete ``WaterLogRepositoryProtocol`` implementation backed by async SQLAlchemy."""

from __future__ import annotations

from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.entities.water_log import WaterLog
from src.infrastructure.db.models.water_log_model import WaterLogORM


class SQLAlchemyWaterLogRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_by_date_range(
        self, user_id: int, from_date: date, to_date: date
    ) -> list[WaterLog]:
        rows = (
            await self._session.execute(
                select(WaterLogORM).where(
                    WaterLogORM.user_id == user_id,
                    WaterLogORM.logged_on >= from_date,
                    WaterLogORM.logged_on <= to_date,
                )
            )
        ).scalars().all()
        return [row.to_domain() for row in rows]
```

- [ ] **Step 6: Write `src/infrastructure/db/repositories/weight_log_repository.py`**

```python
"""Concrete ``WeightLogRepositoryProtocol`` implementation backed by async SQLAlchemy."""

from __future__ import annotations

from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.entities.weight_log import WeightLog
from src.infrastructure.db.models.weight_log_model import WeightLogORM


class SQLAlchemyWeightLogRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

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

- [ ] **Step 7: Add `list_by_date_range` to `src/infrastructure/db/repositories/food_entry_repository.py`**

Add this import at the top:

```python
from datetime import date
```

Then add this method to `SQLAlchemyFoodEntryRepository`, alongside `create`/`get_by_id`:

```python
    async def list_by_date_range(
        self, user_id: int, from_date: date, to_date: date
    ) -> list[FoodEntry]:
        rows = (
            await self._session.execute(
                select(FoodEntryORM).where(
                    FoodEntryORM.user_id == user_id,
                    FoodEntryORM.logged_on >= from_date,
                    FoodEntryORM.logged_on <= to_date,
                )
            )
        ).scalars().all()
        return [row.to_domain() for row in rows]
```

- [ ] **Step 8: Run tests to verify they pass**

Run: `uv run pytest tests/integration/test_diary_sync_repositories.py -v`
Expected: PASS (5 tests)

- [ ] **Step 9: Commit**

```bash
git add src/infrastructure/db/repositories/daily_goal_repository.py src/infrastructure/db/repositories/activity_log_repository.py src/infrastructure/db/repositories/water_log_repository.py src/infrastructure/db/repositories/weight_log_repository.py src/infrastructure/db/repositories/food_entry_repository.py tests/integration/test_diary_sync_repositories.py
git commit -m "feat: add diary sync repositories (daily goals, activity/water/weight logs, food entry date-range list)"
```

---

### Task 6: DI wiring — repositories and use cases for all five resources

**Files:**
- Modify: `src/infrastructure/di/repositories.py`
- Modify: `src/infrastructure/di/use_cases.py`
- Modify: `src/infrastructure/di/__init__.py`

**Interfaces:**
- Consumes: everything from Tasks 2–5
- Produces: `DailyGoalRepositoryDep`, `ActivityLogRepositoryDep`, `WaterLogRepositoryDep`, `WeightLogRepositoryDep`; `ListDailyGoalsUseCaseDep`, `ListFoodEntriesUseCaseDep`, `ListActivityLogsUseCaseDep`, `ListWaterLogsUseCaseDep`, `ListWeightLogsUseCaseDep` — all importable from `src.infrastructure.di`.

No isolated test for this task (pure wiring) — verified by import checks here and exercised end-to-end by Task 7's API tests.

- [ ] **Step 1: Add repository providers to `src/infrastructure/di/repositories.py`**

Add these imports alongside the existing port imports:

```python
from src.application.ports.activity_log_repository import ActivityLogRepositoryProtocol
from src.application.ports.daily_goal_repository import DailyGoalRepositoryProtocol
from src.application.ports.water_log_repository import WaterLogRepositoryProtocol
from src.application.ports.weight_log_repository import WeightLogRepositoryProtocol
```

Add these imports alongside the existing repository-implementation imports:

```python
from src.infrastructure.db.repositories.activity_log_repository import (
    SQLAlchemyActivityLogRepository,
)
from src.infrastructure.db.repositories.daily_goal_repository import SQLAlchemyDailyGoalRepository
from src.infrastructure.db.repositories.water_log_repository import SQLAlchemyWaterLogRepository
from src.infrastructure.db.repositories.weight_log_repository import SQLAlchemyWeightLogRepository
```

Then append at the end of the file:

```python


def get_daily_goal_repository(session: SessionDep) -> DailyGoalRepositoryProtocol:
    return SQLAlchemyDailyGoalRepository(session)


DailyGoalRepositoryDep = Annotated[DailyGoalRepositoryProtocol, Depends(get_daily_goal_repository)]


def get_activity_log_repository(session: SessionDep) -> ActivityLogRepositoryProtocol:
    return SQLAlchemyActivityLogRepository(session)


ActivityLogRepositoryDep = Annotated[
    ActivityLogRepositoryProtocol, Depends(get_activity_log_repository)
]


def get_water_log_repository(session: SessionDep) -> WaterLogRepositoryProtocol:
    return SQLAlchemyWaterLogRepository(session)


WaterLogRepositoryDep = Annotated[WaterLogRepositoryProtocol, Depends(get_water_log_repository)]


def get_weight_log_repository(session: SessionDep) -> WeightLogRepositoryProtocol:
    return SQLAlchemyWeightLogRepository(session)


WeightLogRepositoryDep = Annotated[WeightLogRepositoryProtocol, Depends(get_weight_log_repository)]
```

- [ ] **Step 2: Verify repositories.py imports cleanly**

Run: `uv run python -c "from src.infrastructure.di.repositories import DailyGoalRepositoryDep, ActivityLogRepositoryDep, WaterLogRepositoryDep, WeightLogRepositoryDep; print('ok')"`
Expected: `ok`

- [ ] **Step 3: Add use-case providers to `src/infrastructure/di/use_cases.py`**

Add these imports alongside the existing use-case imports:

```python
from src.application.use_cases.list_activity_logs import ListActivityLogsUseCase
from src.application.use_cases.list_daily_goals import ListDailyGoalsUseCase
from src.application.use_cases.list_food_entries import ListFoodEntriesUseCase
from src.application.use_cases.list_water_logs import ListWaterLogsUseCase
from src.application.use_cases.list_weight_logs import ListWeightLogsUseCase
```

Change this import block:

```python
from src.infrastructure.di.repositories import (
    ChatMessageRepositoryDep,
    FoodEntryRepositoryDep,
    PaymentRepositoryDep,
    RefreshTokenRepositoryDep,
    SocialIdentityRepositoryDep,
    SubscriptionRepositoryDep,
    UserRepositoryDep,
)
```

to:

```python
from src.infrastructure.di.repositories import (
    ActivityLogRepositoryDep,
    ChatMessageRepositoryDep,
    DailyGoalRepositoryDep,
    FoodEntryRepositoryDep,
    PaymentRepositoryDep,
    RefreshTokenRepositoryDep,
    SocialIdentityRepositoryDep,
    SubscriptionRepositoryDep,
    UserRepositoryDep,
    WaterLogRepositoryDep,
    WeightLogRepositoryDep,
)
```

Then append at the end of the file:

```python


def get_list_daily_goals_use_case(daily_goals: DailyGoalRepositoryDep) -> ListDailyGoalsUseCase:
    return ListDailyGoalsUseCase(daily_goals=daily_goals)


def get_list_food_entries_use_case(food_entries: FoodEntryRepositoryDep) -> ListFoodEntriesUseCase:
    return ListFoodEntriesUseCase(food_entries=food_entries)


def get_list_activity_logs_use_case(
    activity_logs: ActivityLogRepositoryDep,
) -> ListActivityLogsUseCase:
    return ListActivityLogsUseCase(activity_logs=activity_logs)


def get_list_water_logs_use_case(water_logs: WaterLogRepositoryDep) -> ListWaterLogsUseCase:
    return ListWaterLogsUseCase(water_logs=water_logs)


def get_list_weight_logs_use_case(weight_logs: WeightLogRepositoryDep) -> ListWeightLogsUseCase:
    return ListWeightLogsUseCase(weight_logs=weight_logs)


ListDailyGoalsUseCaseDep = Annotated[ListDailyGoalsUseCase, Depends(get_list_daily_goals_use_case)]
ListFoodEntriesUseCaseDep = Annotated[
    ListFoodEntriesUseCase, Depends(get_list_food_entries_use_case)
]
ListActivityLogsUseCaseDep = Annotated[
    ListActivityLogsUseCase, Depends(get_list_activity_logs_use_case)
]
ListWaterLogsUseCaseDep = Annotated[ListWaterLogsUseCase, Depends(get_list_water_logs_use_case)]
ListWeightLogsUseCaseDep = Annotated[
    ListWeightLogsUseCase, Depends(get_list_weight_logs_use_case)
]
```

- [ ] **Step 4: Re-export everything from `src/infrastructure/di/__init__.py`**

Add `DailyGoalRepositoryDep`, `ActivityLogRepositoryDep`, `WaterLogRepositoryDep`,
`WeightLogRepositoryDep`, `get_daily_goal_repository`, `get_activity_log_repository`,
`get_water_log_repository`, `get_weight_log_repository` to the
`from src.infrastructure.di.repositories import (...)` block; add `ListDailyGoalsUseCaseDep`,
`ListFoodEntriesUseCaseDep`, `ListActivityLogsUseCaseDep`, `ListWaterLogsUseCaseDep`,
`ListWeightLogsUseCaseDep`, `get_list_daily_goals_use_case`, `get_list_food_entries_use_case`,
`get_list_activity_logs_use_case`, `get_list_water_logs_use_case`,
`get_list_weight_logs_use_case` to the `from src.infrastructure.di.use_cases import (...)`
block. Add all of the same names to `__all__`, keeping it alphabetically sorted as the
existing list is.

- [ ] **Step 5: Verify the whole DI graph imports and resolves**

Run: `uv run python -c "from src.infrastructure.di import ListDailyGoalsUseCaseDep, ListFoodEntriesUseCaseDep, ListActivityLogsUseCaseDep, ListWaterLogsUseCaseDep, ListWeightLogsUseCaseDep; print('ok')"`
Expected: `ok`

Run: `uv run lint-imports`
Expected: no violations

- [ ] **Step 6: Commit**

```bash
git add src/infrastructure/di/repositories.py src/infrastructure/di/use_cases.py src/infrastructure/di/__init__.py
git commit -m "feat: wire diary sync repositories and list use cases into DI"
```

---

### Task 7: Adapters — schemas, controllers, `main.py`, API tests

**Files:**
- Create: `src/adapters/schemas/daily_goal_schemas.py`, `src/adapters/schemas/activity_log_schemas.py`, `src/adapters/schemas/water_log_schemas.py`, `src/adapters/schemas/weight_log_schemas.py`
- Modify: `src/adapters/schemas/food_entry_schemas.py`
- Create: `src/adapters/controllers/daily_goal_controller.py`, `src/adapters/controllers/activity_log_controller.py`, `src/adapters/controllers/water_log_controller.py`, `src/adapters/controllers/weight_log_controller.py`
- Modify: `src/adapters/controllers/food_entry_controller.py`
- Modify: `src/main.py`
- Test: `tests/api/test_food_entry_endpoints.py` (extend), `tests/api/test_daily_goal_endpoints.py`, `tests/api/test_activity_log_endpoints.py`, `tests/api/test_water_log_endpoints.py`, `tests/api/test_weight_log_endpoints.py`

**Interfaces:**
- Consumes: everything from Tasks 1–6
- Produces: `GET /daily-goals`, `GET /food-entries?from=&to=`, `GET /activity-logs?from=&to=`, `GET /water-logs?from=&to=`, `GET /weight-logs?from=&to=` — all registered on `app`

- [ ] **Step 1: Write `src/adapters/schemas/daily_goal_schemas.py`**

```python
"""HTTP wire models for the daily goals API."""

from __future__ import annotations

from datetime import date
from uuid import UUID

from src.adapters.schemas.base import CamelModel
from src.application.dtos.daily_goal import DailyGoalOutputDTO


class DailyGoalResponse(CamelModel):
    id: UUID
    user_id: int
    target_kcal: int
    target_carbs_g: float
    target_protein_g: float
    target_fat_g: float
    target_water_ml: int
    effective_date: date

    @classmethod
    def from_dto(cls, dto: DailyGoalOutputDTO) -> DailyGoalResponse:
        return cls(
            id=dto.id,
            user_id=dto.user_id,
            target_kcal=dto.target_kcal,
            target_carbs_g=dto.target_carbs_g,
            target_protein_g=dto.target_protein_g,
            target_fat_g=dto.target_fat_g,
            target_water_ml=dto.target_water_ml,
            effective_date=dto.effective_date,
        )
```

- [ ] **Step 2: Write `src/adapters/schemas/activity_log_schemas.py`**

```python
"""HTTP wire models for the activity logs API."""

from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from src.adapters.schemas.base import CamelModel
from src.application.dtos.activity_log import ActivityLogOutputDTO
from src.domain.enums import ActivitySource


class ActivityLogResponse(CamelModel):
    id: UUID
    user_id: int
    activity_type: str
    calories_burned: int
    source: ActivitySource
    logged_at: datetime
    logged_on: date

    @classmethod
    def from_dto(cls, dto: ActivityLogOutputDTO) -> ActivityLogResponse:
        return cls(
            id=dto.id,
            user_id=dto.user_id,
            activity_type=dto.activity_type,
            calories_burned=dto.calories_burned,
            source=dto.source,
            logged_at=dto.logged_at,
            logged_on=dto.logged_on,
        )
```

- [ ] **Step 3: Write `src/adapters/schemas/water_log_schemas.py`**

```python
"""HTTP wire models for the water logs API."""

from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from src.adapters.schemas.base import CamelModel
from src.application.dtos.water_log import WaterLogOutputDTO


class WaterLogResponse(CamelModel):
    id: UUID
    user_id: int
    amount_ml: int
    logged_at: datetime
    logged_on: date

    @classmethod
    def from_dto(cls, dto: WaterLogOutputDTO) -> WaterLogResponse:
        return cls(
            id=dto.id,
            user_id=dto.user_id,
            amount_ml=dto.amount_ml,
            logged_at=dto.logged_at,
            logged_on=dto.logged_on,
        )
```

- [ ] **Step 4: Write `src/adapters/schemas/weight_log_schemas.py`**

```python
"""HTTP wire models for the weight logs API."""

from __future__ import annotations

from datetime import date
from uuid import UUID

from src.adapters.schemas.base import CamelModel
from src.application.dtos.weight_log import WeightLogOutputDTO


class WeightLogResponse(CamelModel):
    id: UUID
    user_id: int
    weight: float
    recorded_at: date

    @classmethod
    def from_dto(cls, dto: WeightLogOutputDTO) -> WeightLogResponse:
        return cls(id=dto.id, user_id=dto.user_id, weight=dto.weight, recorded_at=dto.recorded_at)
```

- [ ] **Step 5: Update `src/adapters/schemas/food_entry_schemas.py`**

```python
"""HTTP wire models for the food entry (meal log) API."""

from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from pydantic import Field

from src.adapters.schemas.base import CamelModel
from src.application.dtos.food_entry import FoodEntryOutputDTO, IngredientOutputDTO
from src.domain.enums import AiFeedback, InputMethod, MealType


class CreateIngredientRequest(CamelModel):
    name: str = Field(min_length=1)
    quantity_g: float
    kcal: int
    carbs_g: float
    protein_g: float
    fat_g: float
    fiber_g: float | None = None


class CreateFoodEntryRequest(CamelModel):
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


class IngredientResponse(CamelModel):
    id: UUID
    food_entry_id: UUID
    name: str
    quantity_g: float
    kcal: int
    carbs_g: float
    protein_g: float
    fat_g: float
    fiber_g: float | None

    @classmethod
    def from_dto(cls, dto: IngredientOutputDTO) -> IngredientResponse:
        return cls(
            id=dto.id,
            food_entry_id=dto.food_entry_id,
            name=dto.name,
            quantity_g=dto.quantity_g,
            kcal=dto.kcal,
            carbs_g=dto.carbs_g,
            protein_g=dto.protein_g,
            fat_g=dto.fat_g,
            fiber_g=dto.fiber_g,
        )


class FoodEntryResponse(CamelModel):
    id: UUID
    user_id: int
    name: str
    input_method: InputMethod
    meal_type: MealType
    total_kcal: int
    carbs_g: float
    protein_g: float
    fat_g: float
    image_url: str | None
    fiber_g: float | None
    ai_feedback: AiFeedback | None
    logged_at: datetime
    logged_on: date
    ingredients: list[IngredientResponse]

    @classmethod
    def from_dto(cls, dto: FoodEntryOutputDTO) -> FoodEntryResponse:
        return cls(
            id=dto.id,
            user_id=dto.user_id,
            name=dto.name,
            input_method=dto.input_method,
            meal_type=dto.meal_type,
            total_kcal=dto.total_kcal,
            carbs_g=dto.carbs_g,
            protein_g=dto.protein_g,
            fat_g=dto.fat_g,
            image_url=dto.image_url,
            fiber_g=dto.fiber_g,
            ai_feedback=dto.ai_feedback,
            logged_at=dto.logged_at,
            logged_on=dto.logged_on,
            ingredients=[IngredientResponse.from_dto(i) for i in dto.ingredients],
        )
```

- [ ] **Step 6: Write `src/adapters/controllers/daily_goal_controller.py`**

```python
"""Daily goal endpoints. HTTP <-> application DTO translation only."""

from __future__ import annotations

from fastapi import APIRouter

from src.adapters.schemas.daily_goal_schemas import DailyGoalResponse
from src.infrastructure.di import CurrentUserDep, ListDailyGoalsUseCaseDep

router = APIRouter(prefix="/daily-goals", tags=["daily-goals"])


@router.get("", response_model=list[DailyGoalResponse])
async def list_daily_goals(
    user: CurrentUserDep, use_case: ListDailyGoalsUseCaseDep
) -> list[DailyGoalResponse]:
    result = await use_case.execute(user.id)
    return [DailyGoalResponse.from_dto(dto) for dto in result]
```

- [ ] **Step 7: Write `src/adapters/controllers/activity_log_controller.py`**

```python
"""Activity log endpoints. HTTP <-> application DTO translation only."""

from __future__ import annotations

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Query

from src.adapters.schemas.activity_log_schemas import ActivityLogResponse
from src.infrastructure.di import CurrentUserDep, ListActivityLogsUseCaseDep

router = APIRouter(prefix="/activity-logs", tags=["activity-logs"])


@router.get("", response_model=list[ActivityLogResponse])
async def list_activity_logs(
    user: CurrentUserDep,
    use_case: ListActivityLogsUseCaseDep,
    from_: Annotated[date, Query(alias="from")],
    to: Annotated[date, Query()],
) -> list[ActivityLogResponse]:
    result = await use_case.execute(user.id, from_, to)
    return [ActivityLogResponse.from_dto(dto) for dto in result]
```

- [ ] **Step 8: Write `src/adapters/controllers/water_log_controller.py`**

```python
"""Water log endpoints. HTTP <-> application DTO translation only."""

from __future__ import annotations

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Query

from src.adapters.schemas.water_log_schemas import WaterLogResponse
from src.infrastructure.di import CurrentUserDep, ListWaterLogsUseCaseDep

router = APIRouter(prefix="/water-logs", tags=["water-logs"])


@router.get("", response_model=list[WaterLogResponse])
async def list_water_logs(
    user: CurrentUserDep,
    use_case: ListWaterLogsUseCaseDep,
    from_: Annotated[date, Query(alias="from")],
    to: Annotated[date, Query()],
) -> list[WaterLogResponse]:
    result = await use_case.execute(user.id, from_, to)
    return [WaterLogResponse.from_dto(dto) for dto in result]
```

- [ ] **Step 9: Write `src/adapters/controllers/weight_log_controller.py`**

```python
"""Weight log endpoints. HTTP <-> application DTO translation only."""

from __future__ import annotations

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Query

from src.adapters.schemas.weight_log_schemas import WeightLogResponse
from src.infrastructure.di import CurrentUserDep, ListWeightLogsUseCaseDep

router = APIRouter(prefix="/weight-logs", tags=["weight-logs"])


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

- [ ] **Step 10: Update `src/adapters/controllers/food_entry_controller.py`**

Change the imports:

```python
"""Food entry (meal log) endpoints. HTTP <-> application DTO translation only."""

from __future__ import annotations

from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query

from src.adapters.schemas.food_entry_schemas import CreateFoodEntryRequest, FoodEntryResponse
from src.application.dtos.food_entry import CreateFoodEntryInputDTO, CreateIngredientInputDTO
from src.infrastructure.di import (
    CreateFoodEntryUseCaseDep,
    CurrentUserDep,
    GetFoodEntryUseCaseDep,
    ListFoodEntriesUseCaseDep,
)

router = APIRouter(prefix="/food-entries", tags=["food-entries"])


@router.post("", response_model=FoodEntryResponse)
async def create_food_entry(
    body: CreateFoodEntryRequest,
    user: CurrentUserDep,
    use_case: CreateFoodEntryUseCaseDep,
) -> FoodEntryResponse:
    input_dto = CreateFoodEntryInputDTO(
        user_id=user.id,
        name=body.name,
        input_method=body.input_method,
        total_kcal=body.total_kcal,
        carbs_g=body.carbs_g,
        protein_g=body.protein_g,
        fat_g=body.fat_g,
        meal_type=body.meal_type,
        image_url=body.image_url,
        fiber_g=body.fiber_g,
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
    result = await use_case.execute(input_dto)
    return FoodEntryResponse.from_dto(result)


@router.get("", response_model=list[FoodEntryResponse])
async def list_food_entries(
    user: CurrentUserDep,
    use_case: ListFoodEntriesUseCaseDep,
    from_: Annotated[date, Query(alias="from")],
    to: Annotated[date, Query()],
) -> list[FoodEntryResponse]:
    result = await use_case.execute(user.id, from_, to)
    return [FoodEntryResponse.from_dto(dto) for dto in result]


@router.get("/{entry_id}", response_model=FoodEntryResponse)
async def get_food_entry(
    entry_id: UUID, user: CurrentUserDep, use_case: GetFoodEntryUseCaseDep
) -> FoodEntryResponse:
    result = await use_case.execute(user_id=user.id, entry_id=entry_id)
    return FoodEntryResponse.from_dto(result)
```

- [ ] **Step 11: Register the four new routers in `src/main.py`**

Add imports alongside the existing controller imports:

```python
from src.adapters.controllers.activity_log_controller import router as activity_log_router
from src.adapters.controllers.daily_goal_controller import router as daily_goal_router
from src.adapters.controllers.water_log_controller import router as water_log_router
from src.adapters.controllers.weight_log_controller import router as weight_log_router
```

In `create_app`, add after `app.include_router(food_entry_router)`:

```python
    app.include_router(daily_goal_router)
    app.include_router(activity_log_router)
    app.include_router(water_log_router)
    app.include_router(weight_log_router)
```

- [ ] **Step 12: Update the `_BODY` fixture and existing tests in `tests/api/test_food_entry_endpoints.py` for `meal_type`**

Change `_BODY`'s dict:

```python
_BODY = {
    "name": "Grilled chicken with rice",
    "inputMethod": "manual",
    "totalKcal": 650,
    "carbsG": 70.0,
    "proteinG": 45.0,
    "fatG": 15.0,
    "fiberG": 8.0,
    "mealType": "lunch",
    "ingredients": [
        {
            "name": "chicken breast",
            "quantityG": 200.0,
            "kcal": 330,
            "carbsG": 0.0,
            "proteinG": 40.0,
            "fatG": 15.0,
            "fiberG": 2.0,
        }
    ],
}
```

Then append these two new tests to the same file:

```python
async def test_list_returns_entries_in_the_requested_range(client, signed_up):
    headers = {"Authorization": f"Bearer {signed_up['accessToken']}"}
    created = (await client.post("/food-entries", json=_BODY, headers=headers)).json()
    today = created["loggedOn"]

    resp = await client.get(
        "/food-entries", params={"from": today, "to": today}, headers=headers
    )

    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["id"] == created["id"]
    assert body[0]["mealType"] == "lunch"
    assert body[0]["userId"] == signed_up["user"]["id"]
    assert body[0]["ingredients"][0]["foodEntryId"] == created["id"]


async def test_list_excludes_entries_outside_the_range(client, signed_up):
    headers = {"Authorization": f"Bearer {signed_up['accessToken']}"}
    created = (await client.post("/food-entries", json=_BODY, headers=headers)).json()
    today = created["loggedOn"]

    resp = await client.get(
        "/food-entries", params={"from": "2020-01-01", "to": "2020-01-02"}, headers=headers
    )

    assert resp.status_code == 200
    assert resp.json() == []
```

- [ ] **Step 13: Write `tests/api/test_daily_goal_endpoints.py`**

```python
"""GET /daily-goals — end-to-end against the real app."""

from __future__ import annotations


async def test_returns_empty_list_for_a_new_user(client, signed_up):
    headers = {"Authorization": f"Bearer {signed_up['accessToken']}"}
    resp = await client.get("/daily-goals", headers=headers)
    assert resp.status_code == 200
    assert resp.json() == []


async def test_requires_auth(client):
    resp = await client.get("/daily-goals")
    assert resp.status_code == 401
```

- [ ] **Step 14: Write `tests/api/test_activity_log_endpoints.py`**

```python
"""GET /activity-logs — end-to-end against the real app."""

from __future__ import annotations


async def test_returns_empty_list_in_a_given_range(client, signed_up):
    headers = {"Authorization": f"Bearer {signed_up['accessToken']}"}
    resp = await client.get(
        "/activity-logs", params={"from": "2026-01-01", "to": "2026-01-31"}, headers=headers
    )
    assert resp.status_code == 200
    assert resp.json() == []


async def test_requires_from_and_to_query_params(client, signed_up):
    headers = {"Authorization": f"Bearer {signed_up['accessToken']}"}
    resp = await client.get("/activity-logs", headers=headers)
    assert resp.status_code == 422


async def test_requires_auth(client):
    resp = await client.get(
        "/activity-logs", params={"from": "2026-01-01", "to": "2026-01-31"}
    )
    assert resp.status_code == 401
```

- [ ] **Step 15: Write `tests/api/test_water_log_endpoints.py`**

```python
"""GET /water-logs — end-to-end against the real app."""

from __future__ import annotations


async def test_returns_empty_list_in_a_given_range(client, signed_up):
    headers = {"Authorization": f"Bearer {signed_up['accessToken']}"}
    resp = await client.get(
        "/water-logs", params={"from": "2026-01-01", "to": "2026-01-31"}, headers=headers
    )
    assert resp.status_code == 200
    assert resp.json() == []


async def test_requires_auth(client):
    resp = await client.get("/water-logs", params={"from": "2026-01-01", "to": "2026-01-31"})
    assert resp.status_code == 401
```

- [ ] **Step 16: Write `tests/api/test_weight_log_endpoints.py`**

```python
"""GET /weight-logs — end-to-end against the real app."""

from __future__ import annotations


async def test_returns_empty_list_in_a_given_range(client, signed_up):
    headers = {"Authorization": f"Bearer {signed_up['accessToken']}"}
    resp = await client.get(
        "/weight-logs", params={"from": "2026-01-01", "to": "2026-01-31"}, headers=headers
    )
    assert resp.status_code == 200
    assert resp.json() == []


async def test_requires_auth(client):
    resp = await client.get("/weight-logs", params={"from": "2026-01-01", "to": "2026-01-31"})
    assert resp.status_code == 401
```

- [ ] **Step 17: Run the full test suite**

Run (needs `make docker-up` first): `uv run pytest -v`
Expected: PASS — every test in `tests/unit/`, `tests/integration/`, `tests/api/`, including
all new/changed files from this plan, with no regressions elsewhere.

Also run: `uv run lint-imports`
Expected: no violations

- [ ] **Step 18: Commit**

```bash
git add src/adapters/schemas/daily_goal_schemas.py src/adapters/schemas/activity_log_schemas.py src/adapters/schemas/water_log_schemas.py src/adapters/schemas/weight_log_schemas.py src/adapters/schemas/food_entry_schemas.py src/adapters/controllers/daily_goal_controller.py src/adapters/controllers/activity_log_controller.py src/adapters/controllers/water_log_controller.py src/adapters/controllers/weight_log_controller.py src/adapters/controllers/food_entry_controller.py src/main.py tests/api/test_food_entry_endpoints.py tests/api/test_daily_goal_endpoints.py tests/api/test_activity_log_endpoints.py tests/api/test_water_log_endpoints.py tests/api/test_weight_log_endpoints.py
git commit -m "feat: add diary sync GET endpoints (daily-goals, food-entries range, activity/water/weight logs)"
```

---

## Self-Review Notes

- **Spec coverage:** every "Pull" section of the spec has a task — domain/ORM/migration
  (Task 1), application layer for all five resources (Tasks 2–4), infrastructure (Task 5),
  DI (Task 6), adapters + API tests (Task 7). The spec's explicit non-goals (push, quests,
  coin-transactions, deletion/conflict handling) have no task, correctly.
- **Placeholder scan:** no TBD/TODO; every step has real, complete code.
- **Type consistency:** `list_by_date_range(user_id, from_date, to_date)` is the same
  signature across every port (Tasks 2–5) and every repository (Task 5). `DailyGoalOutputDTO`/
  `ActivityLogOutputDTO`/`WaterLogOutputDTO`/`WeightLogOutputDTO`/`FoodEntryOutputDTO` and
  their `*Response` schema counterparts (Task 7) use the same field names throughout.
- **Review Focus:** all five items have an owning task's test — empty-list (Tasks 2, 4, 7
  API tests), inclusive boundaries (Task 5's `test_food_entry_repository_list_by_date_range_is_inclusive_and_scoped`),
  cross-user leakage (Task 5, every repository test seeds a second user), the `from`/keyword
  alias (Task 7, every new controller), and the `FoodEntry.create()` breakage sequencing
  (Task 1 fixes the test helper, Task 3 fixes the use case — Task 1's Step 13 explicitly
  confirms the *expected* intermediate failure rather than silently leaving it unexplained).
