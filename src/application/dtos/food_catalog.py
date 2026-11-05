"""Catalog sync DTO — the public food list plus the server clock the client stores as its next cursor."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from src.application.dtos.food_admin import AdminFoodDTO


@dataclass(frozen=True)
class CatalogSyncDTO:
    foods: list[AdminFoodDTO]  # ``updated_by_email`` is never filled here
    server_time: datetime
