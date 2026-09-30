"""Quest and coin endpoints. HTTP <-> application DTO translation only."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter

from src.adapters.schemas.coin_schemas import (
    QuestsResponse,
    RedeemRequest,
    RedeemResponse,
)
from src.infrastructure.di import CurrentUserDep, GetQuestsUseCaseDep, RedeemCoinsUseCaseDep

router = APIRouter(tags=["coins"])


@router.get("/quests", response_model=QuestsResponse)
async def get_quests(
    date: date, user: CurrentUserDep, use_case: GetQuestsUseCaseDep
) -> QuestsResponse:
    return QuestsResponse.from_dto(await use_case.execute(user.id, date))


@router.post("/coins/redeem", response_model=RedeemResponse)
async def redeem_coins(
    body: RedeemRequest, user: CurrentUserDep, use_case: RedeemCoinsUseCaseDep
) -> RedeemResponse:
    return RedeemResponse.from_dto(await use_case.execute(user.id, body.days))
