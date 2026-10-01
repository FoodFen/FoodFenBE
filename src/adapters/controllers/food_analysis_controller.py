"""AI food capture endpoints. HTTP <-> application DTO translation only.

Open to anonymous callers (``X-Device-Id``) for a few free tries per input method — see
``AiCallerDep`` for identity and ``AiTrialUseCase`` for the quota.
"""

from __future__ import annotations

from typing import Annotated, Literal

from fastapi import APIRouter, File, Form, UploadFile

from src.adapters.schemas.food_analysis_schemas import (
    AiQuotaResponse,
    AnalyzeFoodTextRequest,
    FoodAnalysisResponse,
)
from src.domain.enums import AiTrialMethod
from src.domain.exceptions import UnreadableImageException
from src.infrastructure.di import (
    AiCallerDep,
    AiTrialUseCaseDep,
    AnalyzeFoodImageUseCaseDep,
    AnalyzeFoodTextUseCaseDep,
)

router = APIRouter(prefix="/ai/food", tags=["ai-food"])

_ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/heic", "image/heif"}
# Bounds the paid-AI input per call. Generous on purpose: the app doesn't downscale photos yet.
_MAX_IMAGE_BYTES = 15 * 1024 * 1024


@router.post("/analyze-image", response_model=FoodAnalysisResponse)
async def analyze_image(
    caller: AiCallerDep,
    use_case: AnalyzeFoodImageUseCaseDep,
    image: Annotated[UploadFile, File()],
    language: Annotated[Literal["vi", "en"], Form()] = "vi",
) -> FoodAnalysisResponse:
    if image.content_type not in _ALLOWED_IMAGE_TYPES:
        raise UnreadableImageException(f"unsupported image type: {image.content_type!r}")
    data = await image.read(_MAX_IMAGE_BYTES + 1)
    if len(data) > _MAX_IMAGE_BYTES:
        raise UnreadableImageException("image is larger than 15 MB")
    result = await use_case.execute(caller, data, image.content_type, language)
    return FoodAnalysisResponse.from_dto(result)


@router.post("/analyze-text", response_model=FoodAnalysisResponse)
async def analyze_text(
    body: AnalyzeFoodTextRequest,
    caller: AiCallerDep,
    use_case: AnalyzeFoodTextUseCaseDep,
) -> FoodAnalysisResponse:
    result = await use_case.execute(
        caller, AiTrialMethod(body.input_method), body.description, body.language
    )
    return FoodAnalysisResponse.from_dto(result)


@router.get("/quota", response_model=AiQuotaResponse)
async def get_quota(caller: AiCallerDep, use_case: AiTrialUseCaseDep) -> AiQuotaResponse:
    return AiQuotaResponse.from_remaining(await use_case.remaining(caller))
