"""Public food catalog for Mobile sync. No auth: the catalog is public data. HTTP <-> DTO translation only."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query
from pydantic import AwareDatetime

from src.adapters.schemas.food_catalog_schemas import CatalogFoodsResponse
from src.infrastructure.di import ListCatalogFoodsUseCaseDep

router = APIRouter(prefix="/foods", tags=["foods"])


@router.get("", response_model=CatalogFoodsResponse)
async def list_foods(
    use_case: ListCatalogFoodsUseCaseDep,
    updated_since: Annotated[AwareDatetime | None, Query(alias="updatedSince")] = None,
) -> CatalogFoodsResponse:
    """Every food (archived included), or those with ``updated_at >= updatedSince``. ``updatedSince`` needs an offset."""
    return CatalogFoodsResponse.from_dto(await use_case.execute(updated_since))
