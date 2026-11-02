"""Mascot endpoints. HTTP <-> application DTO translation only."""

from __future__ import annotations

from fastapi import APIRouter

from src.adapters.schemas.mascot_schemas import (
    EquipMascotRequest,
    EquipMascotResponse,
    MascotsResponse,
)
from src.infrastructure.di import (
    CurrentUserDep,
    EquipMascotUseCaseDep,
    GetMascotsUseCaseDep,
    PurchaseMascotUseCaseDep,
)

router = APIRouter(prefix="/mascots", tags=["mascots"])


@router.get("", response_model=MascotsResponse)
async def get_mascots(user: CurrentUserDep, use_case: GetMascotsUseCaseDep) -> MascotsResponse:
    return MascotsResponse.from_dto(await use_case.execute(user.id))


@router.put("/equipped", response_model=EquipMascotResponse)
async def equip_mascot(
    body: EquipMascotRequest, user: CurrentUserDep, use_case: EquipMascotUseCaseDep
) -> EquipMascotResponse:
    return EquipMascotResponse(equipped_id=await use_case.execute(user.id, body.mascot_id))


@router.post("/{mascot_id}/purchase", response_model=MascotsResponse)
async def purchase_mascot(
    mascot_id: str, user: CurrentUserDep, use_case: PurchaseMascotUseCaseDep
) -> MascotsResponse:
    return MascotsResponse.from_dto(await use_case.execute(user.id, mascot_id))
