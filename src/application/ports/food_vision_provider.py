"""Port: extract a meal name + ingredient list from a photo or description.

Standard library only. `image_url` on the returned DTO is always None here —
persisting the image is a separate concern (ImageStorageProtocol), not this
port's job.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from src.application.dtos.food_analysis import FoodAnalysisDTO
from src.domain.entities.catalog_food import CatalogFood


class FoodVisionProviderProtocol(Protocol):
    """``catalog`` None or empty = ungrounded: the model estimates the numbers itself."""

    async def analyze_image(
        self,
        image_bytes: bytes,
        content_type: str,
        language: str,
        catalog: Sequence[CatalogFood] | None = None,
    ) -> FoodAnalysisDTO: ...

    async def analyze_text(
        self, description: str, language: str, catalog: Sequence[CatalogFood] | None = None
    ) -> FoodAnalysisDTO: ...
