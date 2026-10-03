"""HTTP wire models for the quiz endpoints."""

from __future__ import annotations

import datetime as dt
from dataclasses import asdict
from typing import Literal
from uuid import UUID

from src.adapters.schemas.base import CamelModel
from src.application.dtos.quiz import QuizOutputDTO, QuizResultDTO, QuizTopicOutputDTO
from src.domain.enums import QuizKind


class QuizTopicResponse(CamelModel):
    id: str
    label: str


class QuizTopicsResponse(CamelModel):
    topics: list[QuizTopicResponse]

    @classmethod
    def from_dtos(cls, dtos: list[QuizTopicOutputDTO]) -> QuizTopicsResponse:
        return cls(topics=[QuizTopicResponse(id=t.id, label=t.label) for t in dtos])


class QuizOptionResponse(CamelModel):
    id: str
    text: str


class QuizQuestionResponse(CamelModel):
    id: UUID
    text: str
    options: list[QuizOptionResponse]


class QuizAnswerResultResponse(CamelModel):
    question_id: UUID
    selected_option_id: str
    correct_option_id: str
    correct: bool
    explanation: str


class QuizResultResponse(CamelModel):
    quiz_id: UUID
    correct_count: int
    total: int
    answers: list[QuizAnswerResultResponse]
    coins_earned: int
    balance: int
    coins_remaining_today: int | None

    @classmethod
    def from_dto(cls, dto: QuizResultDTO) -> QuizResultResponse:
        return cls.model_validate(asdict(dto))


class QuizResponse(CamelModel):
    id: UUID
    kind: QuizKind
    topic: str | None
    date: dt.date
    coins_per_correct: int
    coins_remaining_today: int | None
    status: Literal["available", "completed"]
    result: QuizResultResponse | None
    questions: list[QuizQuestionResponse]

    @classmethod
    def from_dto(cls, dto: QuizOutputDTO) -> QuizResponse:
        data = asdict(dto)  # nested dataclasses become dicts keyed by field name
        data["date"] = data.pop("quiz_date")
        return cls.model_validate(data)


class StartPracticeRequest(CamelModel):
    topic: str
    date: dt.date


class QuizAnswerRequest(CamelModel):
    question_id: UUID
    option_id: str


class SubmitQuizRequest(CamelModel):
    answers: list[QuizAnswerRequest]
