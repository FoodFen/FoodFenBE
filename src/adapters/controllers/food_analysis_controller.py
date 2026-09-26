"""AI food capture endpoints. HTTP <-> application DTO translation only."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, File, UploadFile

from src.adapters.schemas.food_analysis_schemas import (
    AnalyzeFoodTextRequest,
    FoodAnalysisResponse,
)
from src.domain.exceptions import UnreadableImageException
from src.infrastructure.di import (
    AnalyzeFoodImageUseCaseDep,
    AnalyzeFoodTextUseCaseDep,
    CurrentUserDep,
    get_current_user,
)

router = APIRouter(prefix="/ai/food", tags=["ai-food"], dependencies=[Depends(get_current_user)])

_ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/heic", "image/heif"}


@router.post("/analyze-image", response_model=FoodAnalysisResponse)
async def analyze_image(
    _: CurrentUserDep,
    use_case: AnalyzeFoodImageUseCaseDep,
    image: Annotated[UploadFile, File()],
) -> FoodAnalysisResponse:
    if image.content_type not in _ALLOWED_IMAGE_TYPES:
        raise UnreadableImageException(f"unsupported image type: {image.content_type!r}")
    data = await image.read()
    result = await use_case.execute(data, image.content_type)
    return FoodAnalysisResponse.from_dto(result)


@router.post("/analyze-text", response_model=FoodAnalysisResponse)
async def analyze_text(
    body: AnalyzeFoodTextRequest,
    _: CurrentUserDep,
    use_case: AnalyzeFoodTextUseCaseDep,
) -> FoodAnalysisResponse:
    result = await use_case.execute(body.description)
    return FoodAnalysisResponse.from_dto(result)
