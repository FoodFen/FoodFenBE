"""Quest and coin endpoints. HTTP <-> application DTO translation only."""

from __future__ import annotations

from datetime import date
from typing import Literal

from fastapi import APIRouter

from src.adapters.schemas.coin_schemas import (
    CoinBundlesResponse,
    QuestsResponse,
    RedeemRequest,
    RedeemResponse,
)
from src.infrastructure.di import (
    CurrentUserDep,
    GetQuestsUseCaseDep,
    ListCoinBundlesUseCaseDep,
    RedeemCoinsUseCaseDep,
)

router = APIRouter(tags=["coins"])


@router.get("/quests", response_model=QuestsResponse)
async def get_quests(
    date: date,
    user: CurrentUserDep,
    use_case: GetQuestsUseCaseDep,
    language: Literal["vi", "en"] = "vi",
) -> QuestsResponse:
    return QuestsResponse.from_dto(await use_case.execute(user.id, date, language))


# Public price list: nothing user-specific, and redeeming still needs a login.
@router.get("/coins/bundles", response_model=CoinBundlesResponse)
async def list_coin_bundles(use_case: ListCoinBundlesUseCaseDep) -> CoinBundlesResponse:
    return CoinBundlesResponse.from_dtos(await use_case.execute())


@router.post("/coins/redeem", response_model=RedeemResponse)
async def redeem_coins(
    body: RedeemRequest, user: CurrentUserDep, use_case: RedeemCoinsUseCaseDep
) -> RedeemResponse:
    return RedeemResponse.from_dto(await use_case.execute(user.id, body.days))
