"""Schema-shape checks for the quiz tables. No I/O."""

from __future__ import annotations

import src.infrastructure.db.models  # noqa: F401 — registers every table on Base.metadata
from src.infrastructure.db.base import Base


def test_quizzes_are_indexed_by_user_for_the_per_player_queries():
    # seen_question_ids, practice_coins_earned and every quiz read filter `quizzes` by user_id,
    # and practice rows are unbounded (one per POST), so without this each is a table scan.
    indexes = {i.name: [c.name for c in i.columns] for i in Base.metadata.tables["quizzes"].indexes}
    assert indexes.get("ix_quizzes_user_id_created_at") == ["user_id", "created_at"]
