"""Persistence port for quests: the catalog, per-user issued quests, and progress measurement."""

from __future__ import annotations

from datetime import date
from typing import Protocol

from src.domain.entities.quest import Quest
from src.domain.entities.quest_definition import QuestDefinition
from src.domain.enums import QuestType


class QuestRepositoryProtocol(Protocol):
    async def active_definitions(self) -> list[QuestDefinition]: ...

    async def get_or_issue(self, quest: Quest) -> Quest:
        """Insert ``quest`` unless its ``(user, type, date)`` already exists; return the stored row."""
        ...

    async def measure(self, user_id: int, quest_type: QuestType, quest_date: date) -> int:
        """Progress in the quest type's own unit, computed from the user's synced data.
        Daily quests look at ``quest_date``; a weekly quest at the 7 days from it."""
        ...

    async def record(self, quest: Quest) -> bool:
        """Persist ``progress``/``completed``. True only if this call flipped the quest from
        incomplete to complete — the caller pays the reward iff it gets True, so concurrent
        requests can't pay twice. A quest already completed is never overwritten."""
        ...
