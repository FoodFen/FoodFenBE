"""Quest unit and localized copy: pure domain behaviour, no I/O."""

from __future__ import annotations

from uuid import uuid4

from src.domain.entities.quest import Quest
from src.domain.entities.quest_definition import QuestDefinition
from src.domain.enums import QuestCadence, QuestType, QuestUnit

_PERCENT = {QuestType.HIT_CALORIE_GOAL, QuestType.HIT_PROTEIN_GOAL, QuestType.DRINK_WATER}


def test_goal_quests_are_measured_in_percent_and_the_rest_in_counts():
    for quest_type in QuestType:
        expected = QuestUnit.PERCENT if quest_type in _PERCENT else QuestUnit.COUNT
        assert Quest.create(1, quest_type, 1, 1).unit is expected, quest_type


def test_definition_text_follows_the_language():
    definition = QuestDefinition(
        id=uuid4(), quest_type=QuestType.LOG_WEIGHT, target=1, reward_coins=1,
        cadence=QuestCadence.DAILY, completion_ratio=1.0, active=True,
        title_vi="Tiêu đề", title_en="Title", description_vi="Mô tả", description_en="Description",
    )
    assert definition.text("vi") == ("Tiêu đề", "Mô tả")
    assert definition.text("en") == ("Title", "Description")
