"""Diner tab: public dishes ordered by what the caller can still eat. HTTP <-> DTO only."""

from __future__ import annotations

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Query

from src.adapters.schemas.restaurant_schemas import PublicDishListResponse
from src.application.dish_fit import DishFilter
from src.infrastructure.di import CurrentUserDep, ListPublicDishesUseCaseDep

router = APIRouter(tags=["dishes"])


@router.get("/dishes", response_model=PublicDishListResponse)
async def list_dishes(
    user: CurrentUserDep,
    use_case: ListPublicDishesUseCaseDep,
    day: Annotated[date | None, Query(alias="date")] = None,
    q: Annotated[str | None, Query(max_length=100)] = None,
    fits: bool | None = None,
    kcal_min: Annotated[float | None, Query(alias="kcalMin", ge=0)] = None,
    kcal_max: Annotated[float | None, Query(alias="kcalMax", ge=0)] = None,
    price_min: Annotated[int | None, Query(alias="priceMin", ge=0)] = None,
    price_max: Annotated[int | None, Query(alias="priceMax", ge=0)] = None,
    protein_min: Annotated[float | None, Query(alias="proteinMin", ge=0)] = None,
    cursor: Annotated[str | None, Query(pattern=r"^\d{1,9}$")] = None,
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
) -> PublicDishListResponse:
    """``date`` is the client's local day; omitted -> the Vietnam (UTC+7) day. ``cursor`` is opaque:
    pass back the previous page's ``nextCursor``."""
    filters = DishFilter(q, fits, kcal_min, kcal_max, price_min, price_max, protein_min)
    page = await use_case.execute(user.id, day, filters, int(cursor or 0), limit)
    return PublicDishListResponse.from_dto(page)
