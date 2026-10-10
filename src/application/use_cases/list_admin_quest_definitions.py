"""Use case: every quest definition, active or not, for the admin content screen."""

from __future__ import annotations

from dataclasses import dataclass

from src.application.dish_fit import fold
from src.application.dtos.admin import AdminQuestDTO
from src.application.ports.quest_repository import QuestRepositoryProtocol


@dataclass
class ListAdminQuestDefinitionsUseCase:
    quests: QuestRepositoryProtocol

    async def execute(self) -> list[AdminQuestDTO]:
        return [
            AdminQuestDTO(
                id=d.id, title=d.title_vi, target=d.target, reward_coins=d.reward_coins,
                cadence=d.cadence, active=d.active,
            )
            # folded sort: a DB collation would put "Ăn" after "Uống"
            for d in sorted(await self.quests.all_definitions(), key=lambda d: (d.cadence, fold(d.title_vi)))
        ]
