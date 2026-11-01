"""Wire models shared by every image upload (restaurant photos, mascot artwork)."""

from __future__ import annotations

from typing import Annotated
from urllib.parse import urlparse

from pydantic import AfterValidator

from src.adapters.schemas.base import CamelModel
from src.infrastructure.config import settings  # a leaf module: just the cloud name, no wiring


def _cloudinary_only(url: str) -> str:
    """Only images uploaded through this app: ``POST /restaurants/mine/images`` and ``POST /admin/images`` hand out these URLs.
    Fails closed: no ``CLOUDINARY_URL`` configured means no image URL is accepted (``null`` still is)."""
    cloud = urlparse(settings.cloudinary_url).hostname  # same parse as CloudinaryImageStorage
    if not cloud or not url.startswith(f"https://res.cloudinary.com/{cloud}/image/upload/"):
        raise ValueError("must be an image uploaded through this app's image upload")
    return url


CloudinaryImageUrl = Annotated[str, AfterValidator(_cloudinary_only)]


class ImageUploadResponse(CamelModel):
    url: str  # absolute (Cloudinary secure_url)
