"""Use case: today's quests for a user — issue, evaluate, and pay out, all on read."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from src.application.dtos.coin import QuestOutputDTO, QuestsOutputDTO
from src.application.ports.coin_repository import CoinRepositoryProtocol
from src.application.ports.quest_repository import QuestRepositoryProtocol
from src.domain.entities.coin_transaction import CoinTransaction
from src.domain.entities.quest import Quest
from src.domain.entities.quest_definition import QuestDefinition
from src.domain.enums import CoinReason, QuestCadence


@dataclass
class GetQuestsUseCase:
    quests: QuestRepositoryProtocol
    coins: CoinRepositoryProtocol

    async def execute(self, user_id: int, day: date, language: str = "vi") -> QuestsOutputDTO:
        """``day`` is the client's local day. Weekly quests are keyed on that week's Monday.
        ``language`` picks the quest copy ("vi" or "en")."""
        issued: list[tuple[Quest, QuestDefinition]] = []
        for definition in await self.quests.active_definitions():
            quest_date = (
                day - timedelta(days=day.weekday())
                if definition.cadence is QuestCadence.WEEKLY
                else day
            )
            quest = await self.quests.get_or_issue(
                Quest.create(
                    user_id,
                    definition.quest_type,
                    definition.target,
                    definition.reward_coins,
                    quest_date=quest_date,
                    cadence=definition.cadence,
                    completion_ratio=definition.completion_ratio,
                )
            )
            if not quest.completed:
                quest.progress = await self.quests.measure(user_id, quest.quest_type, quest_date)
                quest.completed = quest.is_achieved
                if await self.quests.record(quest) and quest.reward_coins:
                    await self.coins.add(
                        CoinTransaction.create(user_id, quest.reward_coins, CoinReason.QUEST_COMPLETED)
                    )
            issued.append((quest, definition))
        return QuestsOutputDTO(
            balance=await self.coins.balance(user_id),
            quests=[QuestOutputDTO.from_entity(q, *d.text(language)) for q, d in issued],
        )
