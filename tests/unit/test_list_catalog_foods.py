"""ListCatalogFoodsUseCase: ``server_time`` must be taken before the repository query runs."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime

from src.application.use_cases.list_catalog_foods import ListCatalogFoodsUseCase
from catalog_foods import make_food


class _SlowRepo:
    """Stamps the moment the query starts, then takes a while to answer."""

    def __init__(self) -> None:
        self.started: datetime | None = None
        self.asked_since: datetime | None = ...

    async def list_changed(self, since):
        self.started, self.asked_since = datetime.now(UTC), since
        await asyncio.sleep(0.05)
        return [make_food()]


async def test_server_time_is_taken_before_the_query_runs():
    repo = _SlowRepo()
    since = datetime(2026, 11, 1, tzinfo=UTC)
    dto = await ListCatalogFoodsUseCase(foods=repo).execute(since)
    assert dto.server_time <= repo.started  # taken after the query it would be ~50 ms later
    assert repo.asked_since == since
    assert [f.slug for f in dto.foods] == ["pho-bo"]
