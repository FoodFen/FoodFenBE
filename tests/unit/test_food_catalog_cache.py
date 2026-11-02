"""FoodCatalogCache: one repo read per ttl window, forced reload on invalidate()."""

from __future__ import annotations

from catalog_foods import make_food

from src.application.food_catalog_cache import FoodCatalogCache


class _Repo:
    def __init__(self) -> None:
        self.loads = 0

    async def list_active(self):
        self.loads += 1
        return [make_food("a"), make_food("b")]

    async def get_by_slug(self, slug):
        raise AssertionError("not used")


async def test_loads_once_across_two_gets_in_slug_order():
    repo, cache = _Repo(), FoodCatalogCache()

    first = await cache.get(repo)
    await cache.get(repo)

    assert repo.loads == 1
    assert list(first) == ["a", "b"]


async def test_invalidate_forces_a_reload():
    repo, cache = _Repo(), FoodCatalogCache()
    await cache.get(repo)

    cache.invalidate()
    await cache.get(repo)

    assert repo.loads == 2


async def test_zero_ttl_reloads_every_time():
    repo, cache = _Repo(), FoodCatalogCache(ttl_seconds=0)

    await cache.get(repo)
    await cache.get(repo)

    assert repo.loads == 2


async def test_a_failed_load_is_not_cached():
    class Flaky(_Repo):
        async def list_active(self):
            self.loads += 1
            if self.loads == 1:
                raise RuntimeError("db down")
            return [make_food("a")]

    repo, cache = Flaky(), FoodCatalogCache()
    try:
        await cache.get(repo)
    except RuntimeError:
        pass

    assert list(await cache.get(repo)) == ["a"]
