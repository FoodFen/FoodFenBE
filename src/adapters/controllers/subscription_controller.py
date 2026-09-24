"""Subscription endpoints. HTTP <-> application DTO translation only."""

from __future__ import annotations

from fastapi import APIRouter

from src.adapters.schemas.subscription_schemas import MySubscriptionResponse
from src.infrastructure.di import CurrentUserDep, GetMySubscriptionUseCaseDep

router = APIRouter(prefix="/subscriptions", tags=["subscriptions"])


@router.get("/me", response_model=MySubscriptionResponse)
async def get_my_subscription(
    user: CurrentUserDep, use_case: GetMySubscriptionUseCaseDep
) -> MySubscriptionResponse:
    result = await use_case.execute(user.id)
    return MySubscriptionResponse.from_dto(result)
