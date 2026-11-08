"""HTTP wire models for nutrition tips."""

from __future__ import annotations

from datetime import datetime

from src.adapters.schemas.base import CamelModel
from src.domain.entities.nutrition_tip import NutritionTip


class NutritionTipResponse(CamelModel):
    """Public shape: only what the app shows."""

    id: str
    text_vi: str
    text_en: str

    @classmethod
    def from_entity(cls, t: NutritionTip) -> NutritionTipResponse:
        return cls(id=str(t.id), text_vi=t.text_vi, text_en=t.text_en)


class NutritionTipsResponse(CamelModel):
    items: list[NutritionTipResponse]


class AdminNutritionTipResponse(CamelModel):
    id: str
    text_vi: str
    text_en: str
    is_active: bool
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_entity(cls, t: NutritionTip) -> AdminNutritionTipResponse:
        return cls(
            id=str(t.id), text_vi=t.text_vi, text_en=t.text_en, is_active=t.is_active,
            created_at=t.created_at, updated_at=t.updated_at,
        )


class AdminNutritionTipsResponse(CamelModel):
    items: list[AdminNutritionTipResponse]


# No pydantic length bounds: the entity enforces them and answers with a coded 422.
class CreateNutritionTipRequest(CamelModel):
    text_vi: str
    text_en: str
    is_active: bool = True


class UpdateNutritionTipRequest(CamelModel):
    text_vi: str | None = None
    text_en: str | None = None
    is_active: bool | None = None
