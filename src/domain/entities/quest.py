"""Quest entity — one daily challenge assigned to a user."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime
from uuid import UUID, uuid4

from src.domain.enums import QuestType
from src.domain.validation import require_non_negative, require_positive


@dataclass
class Quest:
    id: UUID
    user_id: UUID
    quest_type: QuestType
    target: int
    reward_coins: int
    progress: int = 0
    completed: bool = False
    quest_date: date | None = None

    def __post_init__(self) -> None:
        require_positive(self.target, "target")
        require_non_negative(self.progress, "progress")
        require_non_negative(self.reward_coins, "reward_coins")
        if self.quest_date is None:
            self.quest_date = datetime.now(UTC).date()

    @property
    def is_achieved(self) -> bool:
        """Progress has reached the target, whether or not the reward was paid out."""
        return self.progress >= self.target

    @classmethod
    def create(
        cls,
        user_id: UUID,
        quest_type: QuestType,
        target: int,
        reward_coins: int,
        quest_date: date | None = None,
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
        )
