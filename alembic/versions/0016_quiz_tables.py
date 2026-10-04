"""quiz tables + quiz coin reasons

Revision ID: 0016
Revises: 0015
Create Date: 2026-10-03
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0016"
down_revision: str | None = "0015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_OLD_COIN_REASON = ("quest_completed", "streak_bonus", "purchase", "spend", "adjustment")
_NEW_COIN_REASON = (*_OLD_COIN_REASON, "quiz_daily", "quiz_practice")
_QUIZ_KIND = ("daily", "practice")


def _in_check(column: str, values: tuple[str, ...]) -> str:
    return f"{column} IN ({', '.join(repr(v) for v in values)})"


def upgrade() -> None:
    op.create_table(
        "quiz_topics",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("slug", sa.String(length=32), nullable=False),
        sa.Column("label", sa.String(length=64), nullable=False),
        sa.Column("active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_quiz_topics"),
        sa.UniqueConstraint("slug", name="uq_quiz_topics_slug"),
    )
    op.create_table(
        "quiz_questions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("topic_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("options", sa.JSON(), nullable=False),
        sa.Column("correct_option_id", sa.String(length=16), nullable=False),
        sa.Column("explanation", sa.Text(), nullable=False),
        sa.Column("active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_quiz_questions"),
        sa.ForeignKeyConstraint(
            ["topic_id"],
            ["quiz_topics.id"],
            name="fk_quiz_questions_topic_id_quiz_topics",
            ondelete="CASCADE",
        ),
    )
    op.create_table(
        "quizzes",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(length=8), nullable=False),
        sa.Column("topic_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("quiz_date", sa.Date(), nullable=False),
        sa.Column("question_ids", sa.JSON(), nullable=False),
        sa.Column("answers", sa.JSON(none_as_null=True), nullable=True),
        sa.Column("correct_count", sa.Integer(), nullable=True),
        sa.Column("coins_earned", sa.Integer(), nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_quizzes"),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_quizzes_user_id_users", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["topic_id"],
            ["quiz_topics.id"],
            name="fk_quizzes_topic_id_quiz_topics",
            ondelete="SET NULL",
        ),
        sa.CheckConstraint(_in_check("kind", _QUIZ_KIND), name="quiz_kind"),
    )
    op.create_index(
        "uq_quizzes_user_daily_date",
        "quizzes",
        ["user_id", "quiz_date"],
        unique=True,
        postgresql_where=sa.text("kind = 'daily'"),
    )

    op.drop_constraint("coin_reason", "coin_transactions", type_="check")
    op.create_check_constraint(
        "coin_reason", "coin_transactions", _in_check("reason", _NEW_COIN_REASON)
    )


def downgrade() -> None:
    op.drop_constraint("coin_reason", "coin_transactions", type_="check")
    op.execute("DELETE FROM coin_transactions WHERE reason IN ('quiz_daily', 'quiz_practice')")
    op.create_check_constraint(
        "coin_reason", "coin_transactions", _in_check("reason", _OLD_COIN_REASON)
    )
    op.drop_table("quizzes")
    op.drop_table("quiz_questions")
    op.drop_table("quiz_topics")
