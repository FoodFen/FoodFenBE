"""Admin endpoints: moderation and dashboard. HTTP <-> DTO translation only.

Every route is admin-only via the router-level dependency.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from src.infrastructure.di import get_current_admin

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(get_current_admin)])


@router.get("/restaurants")
async def list_restaurants() -> list:
    return []  # replaced in Task 6
