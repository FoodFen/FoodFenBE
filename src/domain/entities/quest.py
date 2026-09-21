"""Quest entity — one daily challenge assigned to a user."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime
from uuid import UUID, uuid4

from src.domain.enums import QuestCadence, QuestType
from src.domain.exceptions import InvalidAttributeException
from src.domain.validation import require_non_negative, require_positive


@dataclass
class Quest:
    id: UUID
    user_id: int
    quest_type: QuestType
    target: int
    reward_coins: int
    progress: int = 0
    completed: bool = False
    quest_date: date | None = None
    cadence: QuestCadence = QuestCadence.DAILY
    # The fraction of `target` that counts as complete, copied onto the row at
    # issuance so a later change to a quest's definition can't rewrite what a
    # past quest actually required. 1 means "complete only at progress >= target".
    completion_ratio: float = 1.0

    def __post_init__(self) -> None:
        require_positive(self.target, "target")
        require_non_negative(self.progress, "progress")
        require_non_negative(self.reward_coins, "reward_coins")
        if self.completion_ratio <= 0 or self.completion_ratio > 1:
            raise InvalidAttributeException(
                f"completion_ratio must be in (0, 1], got {self.completion_ratio!r}"
            )
        if self.quest_date is None:
            self.quest_date = datetime.now(UTC).date()

    @property
    def is_achieved(self) -> bool:
        """Progress has reached `target * completion_ratio`, whether or not the
        reward was paid out."""
        return self.progress >= self.target * self.completion_ratio

    @classmethod
    def create(
        cls,
        user_id: int,
        quest_type: QuestType,
        target: int,
        reward_coins: int,
        quest_date: date | None = None,
        cadence: QuestCadence = QuestCadence.DAILY,
        completion_ratio: float = 1.0,
    ) -> Quest:
        return cls(
            id=uuid4(),
            user_id=user_id,
            quest_type=quest_type,
            target=target,
            reward_coins=reward_coins,
            progress=0,
            completed=False,
            quest_date=quest_date or datetime.now(UTC).date(),
            cadence=cadence,
            completion_ratio=completion_ratio,
        )
