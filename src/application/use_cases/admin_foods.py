"""Use cases: admin food catalog (list / read / create / edit / archive, the change log) and the AI's
unmatched names. Field rules live in ``CatalogFood``; every write also appends a ``FoodChange``."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import UTC, datetime
from uuid import UUID

from src.application.dish_fit import fold
from src.application.dtos.food_admin import (
    AdminFoodDTO,
    AdminFoodListDTO,
    ExistingFoodDTO,
    FoodChangeDTO,
    FoodEditDTO,
    FoodMissDTO,
    FoodMissListDTO,
    FoodServingDTO,
)
from src.application.food_names import food_keys, slugify
from src.application.ports.food_catalog_repository import FoodCatalogRepositoryProtocol
from src.application.ports.food_change_repository import FoodChangeRepositoryProtocol
from src.application.ports.food_miss_repository import FoodMissRepositoryProtocol
from src.application.ports.user_repository import UserRepositoryProtocol
from src.domain.entities.catalog_food import CatalogFood, CatalogServing
from src.domain.entities.food_change import FoodChange
from src.domain.entities.food_miss import FoodMiss
from src.domain.enums import FoodCategory, FoodChangeAction, FoodMissStatus, FoodSourceKind
from src.domain.exceptions import FoodMissNotFoundException, FoodNameTakenException, FoodNotFoundException

_NUMBERS = ("kcal", "carbs_g", "protein_g", "fat_g", "fiber_g")


def snapshot(f: CatalogFood) -> dict:
    """The editable fields plus source and archived: what a change row stores as before / after."""
    return {
        "name": f.name, "name_en": f.name_en, "aliases": list(f.aliases), "category": f.category.value,
        "kcal": f.kcal, "carbs_g": f.carbs_g, "protein_g": f.protein_g, "fat_g": f.fat_g, "fiber_g": f.fiber_g,
        "servings": [{"label": s.label, "grams": s.grams, "default": s.default} for s in f.servings],
        "source_kind": f.source_kind.value, "source_ref": f.source_ref, "archived": f.archived,
    }


async def _detail(users: UserRepositoryProtocol, f: CatalogFood) -> AdminFoodDTO:
    admin = await users.get_by_id(f.updated_by_admin_id) if f.updated_by_admin_id is not None else None
    return AdminFoodDTO.from_entity(f, admin.email if admin else None)


async def _get(foods: FoodCatalogRepositoryProtocol, slug: str) -> CatalogFood:
    food = await foods.get_by_slug(slug)
    if food is None:
        raise FoodNotFoundException(f"no food {slug!r}")
    return food


def _servings(servings: list[FoodServingDTO]) -> list[CatalogServing]:
    return [CatalogServing(s.label, s.grams, s.default) for s in servings]


@dataclass
class ListAdminFoodsUseCase:
    foods: FoodCatalogRepositoryProtocol

    async def execute(
        self,
        q: str | None,
        category: FoodCategory | None,
        verified: bool | None,
        archived: bool = False,
        offset: int = 0,
        limit: int = 20,
    ) -> AdminFoodListDTO:
        """By folded name (slug breaks ties), filter, then slice ``[offset, offset + limit)``."""
        needle = fold(q.strip()) if q else ""
        # ponytail: every food is loaded and filtered in memory (~700 rows); move to SQL if the catalog grows large.
        shown = sorted(
            (
                f for f in await self.foods.list_all()
                if f.archived == archived
                and (category is None or f.category == category)
                and (verified is None or f.verified == verified)
                and (not needle or any(needle in fold(t) for t in (f.name, f.name_en or "", f.slug, *f.aliases)))
            ),
            key=lambda f: (fold(f.name), f.slug),
        )
        end = offset + limit
        return AdminFoodListDTO(
            [AdminFoodDTO.from_entity(f) for f in shown[offset:end]], len(shown), str(end) if end < len(shown) else None
        )


@dataclass
class GetAdminFoodUseCase:
    foods: FoodCatalogRepositoryProtocol
    users: UserRepositoryProtocol

    async def execute(self, slug: str) -> AdminFoodDTO:
        return await _detail(self.users, await _get(self.foods, slug))


@dataclass
class CreateFoodUseCase:
    foods: FoodCatalogRepositoryProtocol
    changes: FoodChangeRepositoryProtocol
    misses: FoodMissRepositoryProtocol
    users: UserRepositoryProtocol

    async def execute(
        self,
        admin_id: int,
        name: str,
        name_en: str | None,
        aliases: list[str],
        category: FoodCategory,
        kcal: int,
        carbs_g: float,
        protein_g: float,
        fat_g: float,
        fiber_g: float | None,
        servings: list[FoodServingDTO],
        miss_id: UUID | None,
    ) -> AdminFoodDTO:
        existing = await self.foods.list_all()
        if fold(name.strip()) in {fold(f.name) for f in existing}:
            raise FoodNameTakenException(f"a food named {name.strip()!r} already exists")
        taken = {f.slug for f in existing}
        slug = base = slugify(name)
        for n in range(2, len(taken) + 3):
            if slug not in taken:
                break
            slug = f"{base}-{n}"
        now = datetime.now(UTC)
        food = CatalogFood.create(
            slug, name, name_en, aliases, category, kcal, carbs_g, protein_g, fat_g, fiber_g, _servings(servings),
            admin_id, now,
        )
        await self.foods.add(food)
        await self.changes.add(FoodChange.create(food.id, admin_id, FoodChangeAction.CREATE, None, snapshot(food), now))
        await self.misses.resolve_open(food_keys(food), food.id)
        if miss_id is not None and (miss := await self.misses.get(miss_id)) and miss.status == FoodMissStatus.OPEN:
            miss.resolve(food.id)
            await self.misses.update(miss)
        return await _detail(self.users, food)


@dataclass
class UpdateFoodUseCase:
    foods: FoodCatalogRepositoryProtocol
    changes: FoodChangeRepositoryProtocol
    misses: FoodMissRepositoryProtocol
    users: UserRepositoryProtocol

    async def execute(self, admin_id: int, slug: str, edit: FoodEditDTO) -> AdminFoodDTO:
        before = await _get(self.foods, slug)
        fields = {k: v for k, v in vars(edit).items() if v is not ...}
        if "servings" in fields:
            fields["servings"] = _servings(fields["servings"])
        after = replace(before, **fields)  # re-runs the entity's validation
        if fold(after.name) != fold(before.name):
            if fold(after.name) in {fold(f.name) for f in await self.foods.list_all() if f.id != before.id}:
                raise FoodNameTakenException(f"a food named {after.name!r} already exists")
        if any(getattr(after, f) != getattr(before, f) for f in _NUMBERS):
            after = replace(after, source_kind=FoodSourceKind.TEAM, source_ref="team")
        if snapshot(after) == snapshot(before):
            return await _detail(self.users, before)
        now = datetime.now(UTC)
        after = replace(after, updated_at=now, updated_by_admin_id=admin_id)
        await self.foods.update(after)
        await self.changes.add(
            FoodChange.create(after.id, admin_id, FoodChangeAction.UPDATE, snapshot(before), snapshot(after), now)
        )
        if (after.name, after.name_en, after.aliases) != (before.name, before.name_en, before.aliases):
            await self.misses.resolve_open(food_keys(after), after.id)
        return await _detail(self.users, after)


@dataclass
class SetFoodArchivedUseCase:
    foods: FoodCatalogRepositoryProtocol
    changes: FoodChangeRepositoryProtocol
    users: UserRepositoryProtocol

    async def execute(self, admin_id: int, slug: str, archived: bool) -> AdminFoodDTO:
        before = await _get(self.foods, slug)
        if before.archived == archived:
            return await _detail(self.users, before)
        if not archived and fold(before.name) in {
            fold(f.name) for f in await self.foods.list_active() if f.id != before.id
        }:
            raise FoodNameTakenException(f"another food named {before.name!r} exists; rename one first")
        now = datetime.now(UTC)
        after = replace(before, archived=archived, updated_at=now, updated_by_admin_id=admin_id)
        await self.foods.update(after)
        action = FoodChangeAction.ARCHIVE if archived else FoodChangeAction.UNARCHIVE
        await self.changes.add(FoodChange.create(after.id, admin_id, action, snapshot(before), snapshot(after), now))
        return await _detail(self.users, after)


@dataclass
class ListFoodChangesUseCase:
    foods: FoodCatalogRepositoryProtocol
    changes: FoodChangeRepositoryProtocol

    async def execute(self, slug: str) -> list[FoodChangeDTO]:
        food = await _get(self.foods, slug)
        return [
            FoodChangeDTO(c.id, c.action, email, c.created_at, c.before, c.after)
            for c, email in await self.changes.list_for_food(food.id)
        ]


def _miss_dto(m: FoodMiss, existing: dict[str, ExistingFoodDTO]) -> FoodMissDTO:
    return FoodMissDTO(
        m.id, m.key, m.name, m.language, m.count, m.first_seen_at, m.last_seen_at, m.status, existing.get(m.key)
    )


async def _existing_foods(foods: FoodCatalogRepositoryProtocol) -> dict[str, ExistingFoodDTO]:
    """miss key -> the active food that already answers to it (computed per read, never stored)."""
    existing: dict[str, ExistingFoodDTO] = {}
    for f in await foods.list_active():
        for key in food_keys(f):
            existing.setdefault(key, ExistingFoodDTO(f.slug, f.name))
    return existing


@dataclass
class ListFoodMissesUseCase:
    foods: FoodCatalogRepositoryProtocol
    misses: FoodMissRepositoryProtocol

    async def execute(
        self, status: FoodMissStatus = FoodMissStatus.OPEN, offset: int = 0, limit: int = 20
    ) -> FoodMissListDTO:
        page, total = await self.misses.list(status, offset, limit)
        existing = await _existing_foods(self.foods)
        end = offset + limit
        return FoodMissListDTO([_miss_dto(m, existing) for m in page], total, str(end) if end < total else None)


@dataclass
class SetFoodMissStatusUseCase:
    foods: FoodCatalogRepositoryProtocol
    misses: FoodMissRepositoryProtocol

    async def execute(self, miss_id: UUID, status: FoodMissStatus) -> FoodMissDTO:
        """``ignored`` or ``open`` (reopen); a miss becomes ``resolved`` only by adding its food."""
        miss = await self.misses.get(miss_id)
        if miss is None:
            raise FoodMissNotFoundException(f"no food miss {miss_id}")
        if status == FoodMissStatus.IGNORED:
            miss.ignore()
        else:
            miss.reopen()
        await self.misses.update(miss)
        return _miss_dto(miss, await _existing_foods(self.foods))
