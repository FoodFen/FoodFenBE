"""Food catalog write side, audit log and miss log repositories on in-memory SQLite."""

from __future__ import annotations

import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "unit"))
from catalog_foods import make_food  # noqa: E402

import src.infrastructure.db.models  # noqa: E402, F401 — registers every table
from src.domain.entities.food_change import FoodChange  # noqa: E402
from src.domain.entities.user import User  # noqa: E402
from src.domain.enums import FoodChangeAction, FoodMissStatus  # noqa: E402
from src.infrastructure.db.base import Base  # noqa: E402
from src.infrastructure.db.repositories.food_catalog_repository import SQLAlchemyFoodCatalogRepository  # noqa: E402
from src.infrastructure.db.repositories.food_change_repository import SQLAlchemyFoodChangeRepository  # noqa: E402
from src.infrastructure.db.repositories.food_miss_repository import SQLAlchemyFoodMissRepository  # noqa: E402
from src.infrastructure.db.repositories.user_repository import SQLAlchemyUserRepository  # noqa: E402

T0 = datetime(2026, 11, 3, 8, tzinfo=UTC)


@pytest_asyncio.fixture
async def session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with async_sessionmaker(engine, expire_on_commit=False)() as s:
        yield s
    await engine.dispose()


async def test_catalog_add_update_and_list_all_include_archived(session):
    repo = SQLAlchemyFoodCatalogRepository(session)
    food = make_food("pho-bo", name_en="Beef pho")
    await repo.add(food)
    food.name, food.name_en, food.fiber_g, food.archived = "Phở bò tái", None, None, True
    await repo.update(food)
    [got] = await repo.list_all()
    assert (got.name, got.name_en, got.fiber_g, got.archived) == ("Phở bò tái", None, None, True)
    assert got.servings == food.servings and got.slug == "pho-bo"
    assert await repo.list_active() == []


async def test_changes_newest_first_with_admin_email(session):
    repo, food = SQLAlchemyFoodChangeRepository(session), make_food("pho-bo")
    await SQLAlchemyFoodCatalogRepository(session).add(food)
    admin = await SQLAlchemyUserRepository(session).create(User.create("admin@example.com"))
    first = FoodChange.create(food.id, admin.id, FoodChangeAction.CREATE, None, {"name": "a"}, T0)
    second = FoodChange.create(food.id, admin.id, FoodChangeAction.UPDATE, {"name": "a"}, {"name": "b"}, T0 + timedelta(minutes=1))
    for c in (first, second):
        await repo.add(c)
    rows = await repo.list_for_food(food.id)
    assert [(c.action, email) for c, email in rows] == [
        (FoodChangeAction.UPDATE, "admin@example.com"), (FoodChangeAction.CREATE, "admin@example.com")
    ]
    assert rows[1][0].before is None and rows[0][0].before == {"name": "a"}
    assert await repo.list_for_food(make_food("other").id) == []


async def test_changes_keep_the_row_when_the_admin_is_gone(session):
    repo, food = SQLAlchemyFoodChangeRepository(session), make_food("pho-bo")
    await SQLAlchemyFoodCatalogRepository(session).add(food)
    await repo.add(FoodChange(uuid4(), food.id, None, FoodChangeAction.CREATE, None, {}, T0))
    [(change, email)] = await repo.list_for_food(food.id)
    assert change.admin_id is None and email is None


async def test_record_twice_counts_and_keeps_name_language_status(session):
    repo = SQLAlchemyFoodMissRepository(session)
    await repo.record([("banh xeo", "Bánh xèo")], "vi", T0)
    await repo.record([("banh xeo", "BANH XEO"), ("egg", "Egg")], "en", T0 + timedelta(hours=1))
    misses, total = await repo.list(FoodMissStatus.OPEN, 0, 10)
    assert total == 2
    xeo = next(m for m in misses if m.key == "banh xeo")
    assert (xeo.count, xeo.name, xeo.language, xeo.status) == (2, "Bánh xèo", "vi", FoodMissStatus.OPEN)
    assert (xeo.first_seen_at, xeo.last_seen_at) == (T0, T0 + timedelta(hours=1))
    egg = next(m for m in misses if m.key == "egg")
    assert (egg.count, egg.language, egg.first_seen_at) == (1, "en", T0 + timedelta(hours=1))


async def test_an_ignored_miss_stays_ignored_after_another_sighting(session):
    repo = SQLAlchemyFoodMissRepository(session)
    await repo.record([("egg", "Egg")], "en", T0)
    [miss], _ = await repo.list(FoodMissStatus.OPEN, 0, 10)
    miss.ignore()
    await repo.update(miss)
    await repo.record([("egg", "Egg")], "en", T0 + timedelta(days=1))
    got = await repo.get(miss.id)
    assert (got.status, got.count, got.last_seen_at) == (FoodMissStatus.IGNORED, 2, T0 + timedelta(days=1))


async def test_list_orders_by_count_then_recency_and_pages(session):
    repo = SQLAlchemyFoodMissRepository(session)
    await repo.record([("a", "A"), ("b", "B"), ("c", "C")], "vi", T0)
    await repo.record([("b", "B")], "vi", T0 + timedelta(hours=1))
    await repo.record([("c", "C")], "vi", T0 + timedelta(hours=2))
    page, total = await repo.list(FoodMissStatus.OPEN, 0, 2)
    assert ([m.key for m in page], total) == (["c", "b"], 3)
    assert [m.key for m in (await repo.list(FoodMissStatus.OPEN, 2, 2))[0]] == ["a"]
    assert await repo.list(FoodMissStatus.IGNORED, 0, 10) == ([], 0)


async def test_resolve_open_only_touches_open_misses_with_those_keys(session):
    repo, foods = SQLAlchemyFoodMissRepository(session), SQLAlchemyFoodCatalogRepository(session)
    food = make_food("pho-bo")
    await foods.add(food)
    await repo.record([("a", "A"), ("b", "B"), ("c", "C")], "vi", T0)
    by_key = {m.key: m for m in (await repo.list(FoodMissStatus.OPEN, 0, 10))[0]}
    by_key["b"].ignore()
    await repo.update(by_key["b"])
    await repo.resolve_open({"a", "b"}, food.id)
    await repo.resolve_open(set(), food.id)
    got = {k: await repo.get(m.id) for k, m in by_key.items()}
    assert [(m.status, m.resolved_food_id) for m in (got["a"], got["b"], got["c"])] == [
        (FoodMissStatus.RESOLVED, food.id), (FoodMissStatus.IGNORED, None), (FoodMissStatus.OPEN, None)
    ]


async def test_a_failing_record_leaves_the_session_usable(session):
    repo, foods = SQLAlchemyFoodMissRepository(session), SQLAlchemyFoodCatalogRepository(session)
    await foods.add(make_food("before"))
    with pytest.raises(IntegrityError):
        await repo.record([("x", "X")], None, T0)  # language is NOT NULL
    await foods.add(make_food("after"))
    await session.commit()
    assert {f.slug for f in await foods.list_all()} == {"before", "after"}
