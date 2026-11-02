"""SQLAlchemyFoodCatalogRepository against the seeded 670-food catalog."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest_asyncio
from sqlalchemy import insert, update
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from src.infrastructure.db.base import Base
import src.infrastructure.db.models  # noqa: F401 — registers every table
from src.infrastructure.db.models.food_model import FoodORM
from src.infrastructure.db.repositories.food_catalog_repository import SQLAlchemyFoodCatalogRepository

_ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location("m0033", _ROOT / "alembic/versions/0033_food_catalog.py")
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
_FOODS = json.loads((_ROOT / "alembic/data/foods.json").read_text(encoding="utf-8"))


@pytest_asyncio.fixture
async def session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with async_sessionmaker(engine, expire_on_commit=False)() as s:
        await s.execute(insert(FoodORM.__table__), _mod._rows(_FOODS))
        await s.flush()
        yield s
    await engine.dispose()


async def test_list_active_returns_every_seeded_food_ordered_by_slug(session):
    foods = await SQLAlchemyFoodCatalogRepository(session).list_active()
    assert len(foods) == 670
    assert [f.slug for f in foods] == sorted(f.slug for f in foods)


async def test_archived_food_leaves_the_list_but_stays_readable(session):
    repo = SQLAlchemyFoodCatalogRepository(session)
    await session.execute(update(FoodORM).where(FoodORM.slug == "banh-bao").values(archived=True))
    assert len(await repo.list_active()) == 669
    food = await repo.get_by_slug("banh-bao")
    assert food is not None and food.archived is True


async def test_unknown_slug_is_none(session):
    assert await SQLAlchemyFoodCatalogRepository(session).get_by_slug("does-not-exist") is None


async def test_legacy_and_verified_foods(session):
    repo = SQLAlchemyFoodCatalogRepository(session)
    yakult = await repo.get_by_slug("yakult")
    assert yakult.verified is False and yakult.source_ref is None
    nin = next(f for f in _FOODS if f.get("sourceRef", "").startswith("nin:"))
    food = await repo.get_by_slug(nin["id"])
    assert food.verified is True and food.source_ref == nin["sourceRef"]


async def test_missing_fiber_is_none(session):
    slug = next(f["id"] for f in _FOODS if "fiberG" not in f["per100g"])
    assert (await SQLAlchemyFoodCatalogRepository(session).get_by_slug(slug)).fiber_g is None
