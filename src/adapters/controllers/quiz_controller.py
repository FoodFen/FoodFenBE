"""Quiz endpoints. HTTP <-> application DTO translation only."""

from __future__ import annotations

from datetime import date
from uuid import UUID

from fastapi import APIRouter

from src.adapters.schemas.quiz_schemas import (
    QuizResponse,
    QuizResultResponse,
    QuizTopicsResponse,
    StartPracticeRequest,
    SubmitQuizRequest,
)
from src.application.dtos.quiz import QuizAnswerInputDTO
from src.infrastructure.di import (
    CurrentUserDep,
    GetDailyQuizUseCaseDep,
    GetQuizUseCaseDep,
    ListQuizTopicsUseCaseDep,
    StartPracticeQuizUseCaseDep,
    SubmitQuizUseCaseDep,
)

router = APIRouter(prefix="/quizzes", tags=["quizzes"])


@router.get("/topics", response_model=QuizTopicsResponse)
async def list_topics(user: CurrentUserDep, use_case: ListQuizTopicsUseCaseDep) -> QuizTopicsResponse:
    return QuizTopicsResponse.from_dtos(await use_case.execute())


@router.get("/daily", response_model=QuizResponse)
async def get_daily_quiz(
    date: date, user: CurrentUserDep, use_case: GetDailyQuizUseCaseDep
) -> QuizResponse:
    return QuizResponse.from_dto(await use_case.execute(user.id, date))


@router.post("/practice", response_model=QuizResponse)
async def start_practice_quiz(
    body: StartPracticeRequest, user: CurrentUserDep, use_case: StartPracticeQuizUseCaseDep
) -> QuizResponse:
    return QuizResponse.from_dto(await use_case.execute(user.id, body.topic, body.date))


@router.get("/{quiz_id}", response_model=QuizResponse)
async def get_quiz(
    quiz_id: UUID, user: CurrentUserDep, use_case: GetQuizUseCaseDep
) -> QuizResponse:
    return QuizResponse.from_dto(await use_case.execute(user.id, quiz_id))


@router.post("/{quiz_id}/submit", response_model=QuizResultResponse)
async def submit_quiz(
    quiz_id: UUID,
    body: SubmitQuizRequest,
    user: CurrentUserDep,
    use_case: SubmitQuizUseCaseDep,
) -> QuizResultResponse:
    answers = [QuizAnswerInputDTO(a.question_id, a.option_id) for a in body.answers]
    return QuizResultResponse.from_dto(await use_case.execute(user.id, quiz_id, answers))
