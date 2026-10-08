"""Admin endpoints: moderation and dashboard. HTTP <-> DTO translation only.

Every route is admin-only via the router-level dependency.
"""

from __future__ import annotations

from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from src.adapters.schemas.admin_schemas import (
    AdminRestaurantDetailResponse,
    AdminRestaurantRowResponse,
    DashboardResponse,
    ReviewRequest,
)
from src.adapters.schemas.restaurant_schemas import DishResponse, RestaurantResponse
from src.domain.enums import ModerationStatus
from src.infrastructure.di import (
    GetAdminDashboardUseCaseDep,
    GetAdminRestaurantUseCaseDep,
    ListAdminRestaurantsUseCaseDep,
    ReviewDishUseCaseDep,
    ReviewRestaurantUseCaseDep,
    get_current_admin,
)

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(get_current_admin)])


@router.get("/restaurants", response_model=list[AdminRestaurantRowResponse])
async def list_restaurants(
    use_case: ListAdminRestaurantsUseCaseDep,
    needs_review: Annotated[bool, Query(alias="needsReview")] = False,
    status: ModerationStatus | None = None,
) -> list[AdminRestaurantRowResponse]:
    return [AdminRestaurantRowResponse.from_dto(r) for r in await use_case.execute(needs_review, status)]


@router.get("/restaurants/{restaurant_id}", response_model=AdminRestaurantDetailResponse)
async def get_restaurant(
    restaurant_id: UUID, use_case: GetAdminRestaurantUseCaseDep
) -> AdminRestaurantDetailResponse:
    return AdminRestaurantDetailResponse.from_dto(await use_case.execute(restaurant_id))


@router.post("/restaurants/{restaurant_id}/review", response_model=RestaurantResponse)
async def review_restaurant(
    restaurant_id: UUID, body: ReviewRequest, use_case: ReviewRestaurantUseCaseDep
) -> RestaurantResponse:
    return RestaurantResponse.from_dto(await use_case.execute(restaurant_id, body.decision, body.reason))


@router.post("/dishes/{dish_id}/review", response_model=DishResponse)
async def review_dish(dish_id: UUID, body: ReviewRequest, use_case: ReviewDishUseCaseDep) -> DishResponse:
    return DishResponse.from_dto(await use_case.execute(dish_id, body.decision, body.reason))


@router.get("/dashboard", response_model=DashboardResponse)
async def dashboard(
    use_case: GetAdminDashboardUseCaseDep,
    from_: Annotated[date | None, Query(alias="from")] = None,
    to: Annotated[date | None, Query()] = None,
) -> DashboardResponse:
    """Vietnam days (UTC+7), inclusive, zero-filled. Default: the last 30 days."""
    return DashboardResponse.from_dto(await use_case.execute(from_, to))
