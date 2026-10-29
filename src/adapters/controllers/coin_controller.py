"""Quest and coin endpoints. HTTP <-> application DTO translation only."""

from __future__ import annotations

from datetime import date
from typing import Annotated, Literal

from fastapi import APIRouter, Query

from src.adapters.schemas.coin_schemas import (
    CoinBundlesResponse,
    CoinTransactionsResponse,
    CursorQuery,
    QuestsResponse,
    RedeemRequest,
    RedeemResponse,
)
from src.infrastructure.di import (
    CurrentUserDep,
    GetQuestsUseCaseDep,
    ListCoinBundlesUseCaseDep,
    ListCoinTransactionsUseCaseDep,
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
    return RedeemResponse.from_dto(await use_case.execute(user.id, body.days, body.client_id))


@router.get("/coins/transactions", response_model=CoinTransactionsResponse)
async def list_coin_transactions(
    user: CurrentUserDep,
    use_case: ListCoinTransactionsUseCaseDep,
    before: CursorQuery | None = None,
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
) -> CoinTransactionsResponse:
    return CoinTransactionsResponse.from_dto(await use_case.execute(user.id, before, limit))
