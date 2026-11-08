"""NutritionTip entity: a short bilingual tip the app shows on its loading screens."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from uuid import UUID, uuid4

from src.domain.exceptions import InvalidNutritionTipException

MAX_TIP_LENGTH = 300


@dataclass
class NutritionTip:
    id: UUID
    text_vi: str
    text_en: str
    is_active: bool = True
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        self.text_vi = self._clean(self.text_vi, "text_vi")
        self.text_en = self._clean(self.text_en, "text_en")

    @staticmethod
    def _clean(value: str, field_name: str) -> str:
        text = (value or "").strip()
        if not text:
            raise InvalidNutritionTipException(f"{field_name} must not be empty", "text_required", field_name)
        if len(text) > MAX_TIP_LENGTH:
            raise InvalidNutritionTipException(
                f"{field_name} must be at most {MAX_TIP_LENGTH} characters", "text_too_long", field_name
            )
        return text

    @classmethod
    def create(cls, text_vi: str, text_en: str, is_active: bool = True) -> NutritionTip:
        now = datetime.now(UTC)
        return cls(uuid4(), text_vi, text_en, is_active, created_at=now, updated_at=now)

    def update(self, text_vi: str | None = None, text_en: str | None = None, is_active: bool | None = None) -> None:
        """Only the given fields change; invalid text raises before anything does."""
        changed = replace(
            self,
            text_vi=self.text_vi if text_vi is None else text_vi,
            text_en=self.text_en if text_en is None else text_en,
            is_active=self.is_active if is_active is None else is_active,
            updated_at=datetime.now(UTC),
        )  # replace() re-runs __post_init__
        self.text_vi, self.text_en, self.is_active, self.updated_at = (
            changed.text_vi, changed.text_en, changed.is_active, changed.updated_at
        )
