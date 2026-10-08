"""Use case: store a restaurant or dish photo; returns its absolute URL."""

from __future__ import annotations

from dataclasses import dataclass

from src.application.ports.image_storage import ImageStorageProtocol


@dataclass
class UploadRestaurantImageUseCase:
    images: ImageStorageProtocol

    async def execute(self, data: bytes, content_type: str) -> str:
        return await self.images.upload(data, content_type)
