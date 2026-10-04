"""QuestDefinition entity — the catalog row a user's daily/weekly Quest is issued from."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from src.domain.enums import QuestCadence, QuestType


@dataclass
class QuestDefinition:
    """Editable (by a future admin) parameters of one quest type. What "progress"
    means for each ``quest_type`` lives in code, in the quest repository's evaluator."""

    id: UUID
    quest_type: QuestType
    target: int
    reward_coins: int
    cadence: QuestCadence
    completion_ratio: float
    active: bool
    title_vi: str
    title_en: str
    description_vi: str
    description_en: str

    def text(self, language: str) -> tuple[str, str]:
        """``(title, description)`` in ``language`` ("vi" unless "en")."""
        if language == "en":
            return self.title_en, self.description_en
        return self.title_vi, self.description_vi
