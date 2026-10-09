"""Diner tab: public dishes ordered by what the caller can still eat. HTTP <-> DTO only."""

from __future__ import annotations

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Query

from src.adapters.schemas.restaurant_schemas import PublicDishListResponse
from src.infrastructure.di import CurrentUserDep, ListPublicDishesUseCaseDep

router = APIRouter(tags=["dishes"])


@router.get("/dishes", response_model=PublicDishListResponse)
async def list_dishes(
    user: CurrentUserDep,
    use_case: ListPublicDishesUseCaseDep,
    day: Annotated[date | None, Query(alias="date")] = None,
) -> PublicDishListResponse:
    """``date`` is the client's local day; omitted -> the Vietnam (UTC+7) day."""
    return PublicDishListResponse.from_dto(await use_case.execute(user.id, day))
