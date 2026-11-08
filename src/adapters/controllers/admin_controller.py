"""Admin endpoints: moderation and dashboard. HTTP <-> DTO translation only.

Every route is admin-only via the router-level dependency.
"""

from __future__ import annotations

from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, File, Query, UploadFile, status

from src.adapters.image_upload import read_image
from src.adapters.schemas.ad_schemas import AdPackageResponse, CreateAdPackageRequest, UpdateAdPackageRequest
from src.adapters.schemas.admin_food_schemas import (
    AdminFoodListResponse,
    AdminFoodResponse,
    CreateFoodRequest,
    FoodChangeResponse,
    FoodMissListResponse,
    FoodMissResponse,
    UpdateFoodRequest,
)
from src.adapters.schemas.admin_schemas import (
    AdminQuestResponse,
    AdminQuizQuestionResponse,
    AdminRestaurantDetailResponse,
    AdminPaymentListResponse,
    AdminRestaurantListResponse,
    AdminUserListResponse,
    DashboardResponse,
    ReviewRequest,
)
from src.adapters.schemas.ai_trial_limits_schemas import AiTrialLimitsRequest, AiTrialLimitsResponse
from src.adapters.schemas.image_schemas import ImageUploadResponse
from src.adapters.schemas.mascot_schemas import AdminMascotResponse, CreateMascotRequest, UpdateMascotRequest
from src.adapters.schemas.restaurant_schemas import DishResponse, RestaurantResponse
from src.application.dtos.food_admin import FoodServingDTO
from src.application.dtos.restaurant import ReviewNoticeDTO
from src.application.ports.email_verification_notifier import EmailVerificationNotifierProtocol
from src.domain.enums import (
    FoodCategory,
    FoodMissStatus,
    ModerationStatus,
    PaymentProvider,
    PaymentStatus,
    PlanType,
    SubscriptionTier,
)
from src.infrastructure.di import (
    CreateAdPackageUseCaseDep,
    CreateFoodUseCaseDep,
    CurrentAdminDep,
    GetAdminFoodUseCaseDep,
    ListAdminFoodsUseCaseDep,
    ListFoodChangesUseCaseDep,
    ListFoodMissesUseCaseDep,
    SetFoodArchivedUseCaseDep,
    SetFoodMissStatusUseCaseDep,
    UpdateFoodUseCaseDep,
    invalidate_food_catalog_after_write,
    CreateMascotUseCaseDep,
    DeleteMascotUseCaseDep,
    EmailVerificationNotifierDep,
    GetAiTrialLimitsUseCaseDep,
    UpdateAiTrialLimitsUseCaseDep,
    ListAdPackagesUseCaseDep,
    ListAdminMascotsUseCaseDep,
    UpdateAdPackageUseCaseDep,
    UpdateMascotUseCaseDep,
    UploadRestaurantImageUseCaseDep,
    GetAdminDashboardUseCaseDep,
    GetAdminRestaurantUseCaseDep,
    ListAdminQuestDefinitionsUseCaseDep,
    ListAdminQuizQuestionsUseCaseDep,
    ListAdminRestaurantsUseCaseDep,
    ListAdminPaymentsUseCaseDep,
    ListAdminUsersUseCaseDep,
    ReviewDishUseCaseDep,
    ReviewRestaurantUseCaseDep,
    get_current_admin,
)

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(get_current_admin)])


async def _send_notice(notifier: EmailVerificationNotifierProtocol, n: ReviewNoticeDTO) -> None:
    await notifier.send_review_result(n.email, n.name, n.restaurant_name, n.approved, n.reason, n.dish_name)


@router.get("/restaurants", response_model=AdminRestaurantListResponse)
async def list_restaurants(
    use_case: ListAdminRestaurantsUseCaseDep,
    needs_review: Annotated[bool, Query(alias="needsReview")] = False,
    status: ModerationStatus | None = None,
    q: Annotated[str | None, Query(max_length=100)] = None,
    cursor: Annotated[str | None, Query(pattern=r"^\d{1,9}$")] = None,
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
) -> AdminRestaurantListResponse:
    """``q`` matches the restaurant name, owner name or owner email (case-insensitive substring).
    ``cursor`` is opaque: pass back the previous page's ``nextCursor``."""
    return AdminRestaurantListResponse.from_dto(
        await use_case.execute(needs_review, status, q, int(cursor or 0), limit)
    )


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


@router.get("/payments", response_model=AdminPaymentListResponse)
async def list_payments(
    use_case: ListAdminPaymentsUseCaseDep,
    q: Annotated[str | None, Query(max_length=100)] = None,
    status: PaymentStatus | None = None,
    plan_type: Annotated[PlanType | None, Query(alias="planType")] = None,
    provider: PaymentProvider | None = None,
    from_: Annotated[date | None, Query(alias="from")] = None,
    to: Annotated[date | None, Query()] = None,
    cursor: Annotated[str | None, Query(pattern=r"^\d{1,9}$")] = None,
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
) -> AdminPaymentListResponse:
    """``q`` matches the payer's email or an exact order code. ``from``/``to`` are Vietnam days (UTC+7),
    inclusive, on ``createdAt``. ``cursor`` is opaque: pass back the previous page's ``nextCursor``."""
    return AdminPaymentListResponse.from_dto(
        await use_case.execute(q, status, plan_type, provider, from_, to, int(cursor or 0), limit)
    )


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


@router.get("/mascots", response_model=list[AdminMascotResponse])
async def list_mascots(use_case: ListAdminMascotsUseCaseDep) -> list[AdminMascotResponse]:
    """Every mascot, inactive ones included, cheapest first. ``ownerCount`` / ``equippedCount`` tell the web
    what hiding or deleting would affect."""
    return [AdminMascotResponse.from_dto(m) for m in await use_case.execute()]


@router.post("/mascots", response_model=AdminMascotResponse, status_code=status.HTTP_201_CREATED)
async def create_mascot(body: CreateMascotRequest, use_case: CreateMascotUseCaseDep) -> AdminMascotResponse:
    return AdminMascotResponse.from_dto(
        await use_case.execute(body.id, body.name, body.coin_cost, body.active, body.images, body.body_color)
    )


@router.patch("/mascots/{mascot_id}", response_model=AdminMascotResponse)
async def update_mascot(
    mascot_id: str, body: UpdateMascotRequest, use_case: UpdateMascotUseCaseDep
) -> AdminMascotResponse:
    return AdminMascotResponse.from_dto(
        await use_case.execute(
            mascot_id,
            body.name,
            body.coin_cost,
            body.active,
            body.images,
            # Absent = keep (...), explicit null = reset to the app default.
            body.body_color if "body_color" in body.model_fields_set else ...,
        )
    )


@router.delete("/mascots/{mascot_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_mascot(mascot_id: str, use_case: DeleteMascotUseCaseDep) -> None:
    """409 ``mascot_in_use`` while anyone owns or has it equipped: hide it instead."""
    await use_case.execute(mascot_id)


@router.get("/ai/trial-limits", response_model=AiTrialLimitsResponse)
async def get_ai_trial_limits(use_case: GetAiTrialLimitsUseCaseDep) -> AiTrialLimitsResponse:
    """Free AI analyses per input method per day: guests and signed-in free users."""
    return AiTrialLimitsResponse.from_entity(await use_case.execute())


@router.put("/ai/trial-limits", response_model=AiTrialLimitsResponse)
async def put_ai_trial_limits(
    body: AiTrialLimitsRequest, use_case: UpdateAiTrialLimitsUseCaseDep
) -> AiTrialLimitsResponse:
    """Both required, each 0..100 (422 ``limit_out_of_range`` with the offending ``field`` otherwise)."""
    return AiTrialLimitsResponse.from_entity(await use_case.execute(body.guest_limit, body.signed_in_limit))


@router.post("/images", response_model=ImageUploadResponse)
async def upload_image(
    use_case: UploadRestaurantImageUseCaseDep, image: Annotated[UploadFile, File()]
) -> ImageUploadResponse:
    """Same checks as ``POST /restaurants/mine/images``, but no rate limit: an admin drops a dozen files at once."""
    data = await read_image(image)
    return ImageUploadResponse(url=await use_case.execute(data, image.content_type))


# Catalog writes: the cache is dropped after the response, i.e. after the session committed (see the dependency).
_invalidates_catalog = [Depends(invalidate_food_catalog_after_write)]


@router.get("/foods", response_model=AdminFoodListResponse)
async def list_foods(
    use_case: ListAdminFoodsUseCaseDep,
    q: Annotated[str | None, Query(max_length=100)] = None,
    category: FoodCategory | None = None,
    verified: bool | None = None,
    archived: bool = False,
    cursor: Annotated[str | None, Query(pattern=r"^\d{1,9}$")] = None,
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
) -> AdminFoodListResponse:
    """``q`` matches the name, English name, an alias or the slug (accent- and case-insensitive); ``archived=true``
    lists only archived foods. Sorted by name. ``cursor`` is opaque: pass back the previous page's ``nextCursor``."""
    return AdminFoodListResponse.from_dto(await use_case.execute(q, category, verified, archived, int(cursor or 0), limit))


@router.post("/foods", response_model=AdminFoodResponse, status_code=status.HTTP_201_CREATED, dependencies=_invalidates_catalog)
async def create_food(body: CreateFoodRequest, use_case: CreateFoodUseCaseDep, admin: CurrentAdminDep) -> AdminFoodResponse:
    """409 ``food_name_taken`` when any food (archived too) has the same name once accents and case are ignored.
    ``missId`` marks that unmatched name resolved; an unknown or not-open one is ignored."""
    return AdminFoodResponse.from_dto(
        await use_case.execute(
            admin.id, body.name, body.name_en, body.aliases, body.category, body.kcal, body.carbs_g, body.protein_g,
            body.fat_g, body.fiber_g, [FoodServingDTO(**vars(s)) for s in body.servings], body.miss_id,
        )
    )


@router.get("/foods/{slug}", response_model=AdminFoodResponse)
async def get_food(slug: str, use_case: GetAdminFoodUseCaseDep) -> AdminFoodResponse:
    return AdminFoodResponse.from_dto(await use_case.execute(slug))


@router.patch("/foods/{slug}", response_model=AdminFoodResponse, dependencies=_invalidates_catalog)
async def update_food(
    slug: str, body: UpdateFoodRequest, use_case: UpdateFoodUseCaseDep, admin: CurrentAdminDep
) -> AdminFoodResponse:
    return AdminFoodResponse.from_dto(await use_case.execute(admin.id, slug, body.to_dto()))


@router.post("/foods/{slug}/archive", response_model=AdminFoodResponse, dependencies=_invalidates_catalog)
async def archive_food(slug: str, use_case: SetFoodArchivedUseCaseDep, admin: CurrentAdminDep) -> AdminFoodResponse:
    """Idempotent: a change row only when the state flips."""
    return AdminFoodResponse.from_dto(await use_case.execute(admin.id, slug, True))


@router.post("/foods/{slug}/unarchive", response_model=AdminFoodResponse, dependencies=_invalidates_catalog)
async def unarchive_food(slug: str, use_case: SetFoodArchivedUseCaseDep, admin: CurrentAdminDep) -> AdminFoodResponse:
    """409 ``food_name_taken`` while another active food has the same name."""
    return AdminFoodResponse.from_dto(await use_case.execute(admin.id, slug, False))


@router.get("/foods/{slug}/changes", response_model=list[FoodChangeResponse])
async def list_food_changes(slug: str, use_case: ListFoodChangesUseCaseDep) -> list[FoodChangeResponse]:
    """Newest first, with the admin's email and the before / after snapshots (``before`` null for a create)."""
    return [FoodChangeResponse.from_dto(c) for c in await use_case.execute(slug)]


@router.get("/food-misses", response_model=FoodMissListResponse)
async def list_food_misses(
    use_case: ListFoodMissesUseCaseDep,
    status: FoodMissStatus = FoodMissStatus.OPEN,
    cursor: Annotated[str | None, Query(pattern=r"^\d{1,9}$")] = None,
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
) -> FoodMissListResponse:
    """Names the AI could not match, most frequent first. ``existingFood`` is the active food that already answers
    to the name (computed now, not stored). ``cursor`` is opaque: pass back the previous page's ``nextCursor``."""
    return FoodMissListResponse.from_dto(await use_case.execute(status, int(cursor or 0), limit))


@router.post("/food-misses/{miss_id}/ignore", response_model=FoodMissResponse)
async def ignore_food_miss(miss_id: UUID, use_case: SetFoodMissStatusUseCaseDep) -> FoodMissResponse:
    return FoodMissResponse.from_dto(await use_case.execute(miss_id, FoodMissStatus.IGNORED))


@router.post("/food-misses/{miss_id}/reopen", response_model=FoodMissResponse)
async def reopen_food_miss(miss_id: UUID, use_case: SetFoodMissStatusUseCaseDep) -> FoodMissResponse:
    return FoodMissResponse.from_dto(await use_case.execute(miss_id, FoodMissStatus.OPEN))
