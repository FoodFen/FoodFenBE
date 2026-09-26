"""Port: extract a meal name + ingredient list from a photo or description.

Standard library only. `image_url` on the returned DTO is always None here —
persisting the image is a separate concern (ImageStorageProtocol), not this
port's job.
"""

from __future__ import annotations

from typing import Protocol

from src.application.dtos.food_analysis import FoodAnalysisDTO


class FoodVisionProviderProtocol(Protocol):
    async def analyze_image(self, image_bytes: bytes, content_type: str) -> FoodAnalysisDTO: ...

    async def analyze_text(self, description: str) -> FoodAnalysisDTO: ...
