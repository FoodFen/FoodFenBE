"""Public nutrition tips for the app's loading screens. No auth."""

from __future__ import annotations

from fastapi import APIRouter

from src.adapters.schemas.nutrition_tip_schemas import NutritionTipResponse, NutritionTipsResponse
from src.infrastructure.di import ListNutritionTipsUseCaseDep

router = APIRouter(prefix="/nutrition-tips", tags=["nutrition-tips"])


@router.get("", response_model=NutritionTipsResponse)
async def list_nutrition_tips(use_case: ListNutritionTipsUseCaseDep) -> NutritionTipsResponse:
    """Active tips, newest first."""
    return NutritionTipsResponse(
        items=[NutritionTipResponse.from_entity(t) for t in await use_case.execute(active_only=True)]
    )
