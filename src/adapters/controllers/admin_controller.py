"""Admin endpoints: moderation and dashboard. HTTP <-> DTO translation only.

Every route is admin-only via the router-level dependency.
"""

from __future__ import annotations

from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, Query, status

from src.adapters.schemas.ad_schemas import AdPackageResponse, CreateAdPackageRequest, UpdateAdPackageRequest
from src.adapters.schemas.admin_schemas import (
    AdminQuestResponse,
    AdminQuizQuestionResponse,
    AdminRestaurantDetailResponse,
    AdminRestaurantRowResponse,
    AdminUserListResponse,
    DashboardResponse,
    ReviewRequest,
)
from src.adapters.schemas.restaurant_schemas import DishResponse, RestaurantResponse
from src.application.dtos.restaurant import ReviewNoticeDTO
from src.application.ports.email_verification_notifier import EmailVerificationNotifierProtocol
from src.domain.enums import ModerationStatus, SubscriptionTier
from src.infrastructure.di import (
    CreateAdPackageUseCaseDep,
    EmailVerificationNotifierDep,
    ListAdPackagesUseCaseDep,
    UpdateAdPackageUseCaseDep,
    GetAdminDashboardUseCaseDep,
    GetAdminRestaurantUseCaseDep,
    ListAdminQuestDefinitionsUseCaseDep,
    ListAdminQuizQuestionsUseCaseDep,
    ListAdminRestaurantsUseCaseDep,
    ListAdminUsersUseCaseDep,
    ReviewDishUseCaseDep,
    ReviewRestaurantUseCaseDep,
    get_current_admin,
)

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(get_current_admin)])


async def _send_notice(notifier: EmailVerificationNotifierProtocol, n: ReviewNoticeDTO) -> None:
    await notifier.send_review_result(n.email, n.name, n.restaurant_name, n.approved, n.reason, n.dish_name)


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
    restaurant_id: UUID,
    body: ReviewRequest,
    use_case: ReviewRestaurantUseCaseDep,
    notifier: EmailVerificationNotifierDep,
    background_tasks: BackgroundTasks,
) -> RestaurantResponse:
    result = await use_case.execute(restaurant_id, body.decision, body.reason, body.expected_updated_at)
    if result.notice is not None:
        background_tasks.add_task(_send_notice, notifier, result.notice)
    return RestaurantResponse.from_dto(result.restaurant)


@router.post("/dishes/{dish_id}/review", response_model=DishResponse)
async def review_dish(
    dish_id: UUID,
    body: ReviewRequest,
    use_case: ReviewDishUseCaseDep,
    notifier: EmailVerificationNotifierDep,
    background_tasks: BackgroundTasks,
) -> DishResponse:
    result = await use_case.execute(dish_id, body.decision, body.reason, body.expected_updated_at)
    if result.notice is not None:
        background_tasks.add_task(_send_notice, notifier, result.notice)
    return DishResponse.from_dto(result.dish)


@router.get("/dashboard", response_model=DashboardResponse)
async def dashboard(
    use_case: GetAdminDashboardUseCaseDep,
    from_: Annotated[date | None, Query(alias="from")] = None,
    to: Annotated[date | None, Query()] = None,
) -> DashboardResponse:
    """Vietnam days (UTC+7), inclusive, zero-filled. Default: the last 30 days."""
    return DashboardResponse.from_dto(await use_case.execute(from_, to))


@router.get("/users", response_model=AdminUserListResponse)
async def list_users(
    use_case: ListAdminUsersUseCaseDep,
    q: Annotated[str | None, Query(max_length=100)] = None,
    tier: SubscriptionTier | None = None,
    cursor: Annotated[str | None, Query(pattern=r"^\d{1,9}$")] = None,
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
) -> AdminUserListResponse:
    """``q`` matches name or email; ``tier`` is the effective tier. ``cursor`` is opaque: pass back
    the previous page's ``nextCursor``."""
    return AdminUserListResponse.from_dto(await use_case.execute(q, tier, int(cursor or 0), limit))


@router.get("/quizzes", response_model=list[AdminQuizQuestionResponse])
async def list_quizzes(use_case: ListAdminQuizQuestionsUseCaseDep) -> list[AdminQuizQuestionResponse]:
    return [AdminQuizQuestionResponse.from_dto(q) for q in await use_case.execute()]


@router.get("/quests", response_model=list[AdminQuestResponse])
async def list_quests(use_case: ListAdminQuestDefinitionsUseCaseDep) -> list[AdminQuestResponse]:
    return [AdminQuestResponse.from_dto(q) for q in await use_case.execute()]


@router.get("/ad-packages", response_model=list[AdPackageResponse])
async def list_ad_packages(use_case: ListAdPackagesUseCaseDep) -> list[AdPackageResponse]:
    """Every package, inactive ones included."""
    return [AdPackageResponse.from_dto(p) for p in await use_case.execute()]


@router.post("/ad-packages", response_model=AdPackageResponse, status_code=status.HTTP_201_CREATED)
async def create_ad_package(body: CreateAdPackageRequest, use_case: CreateAdPackageUseCaseDep) -> AdPackageResponse:
    return AdPackageResponse.from_dto(await use_case.execute(body.days, body.price_vnd, body.active))


@router.patch("/ad-packages/{package_id}", response_model=AdPackageResponse)
async def update_ad_package(
    package_id: UUID, body: UpdateAdPackageRequest, use_case: UpdateAdPackageUseCaseDep
) -> AdPackageResponse:
    return AdPackageResponse.from_dto(await use_case.execute(package_id, body.days, body.price_vnd, body.active))
