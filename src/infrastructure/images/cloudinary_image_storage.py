"""Cloudinary implementation of ``ImageStorageProtocol``."""

from __future__ import annotations

import asyncio
import io
from urllib.parse import urlparse

import cloudinary
import cloudinary.uploader


class CloudinaryImageStorage:
    def __init__(self, *, cloudinary_url: str) -> None:
        # The SDK only auto-parses CLOUDINARY_URL from the real process
        # environment at import time (cloudinary.BaseConfig._load_config_from_env);
        # pydantic-settings' parsed value never reaches os.environ, and
        # cloudinary.config(cloudinary_url=...) is not a real parameter it
        # understands either — it silently no-ops, leaving api_key unset. So
        # this parses the "cloudinary://<api_key>:<api_secret>@<cloud_name>"
        # shape by hand and passes the three real fields explicitly.
        # cloudinary.config() is process-global (the SDK has no per-instance
        # client), so this just sets it once at construction.
        parsed = urlparse(cloudinary_url)
        cloudinary.config(
            cloud_name=parsed.hostname, api_key=parsed.username, api_secret=parsed.password
        )

    async def upload(self, data: bytes, content_type: str) -> str:
        # content_type unused: Cloudinary sniffs the format from the bytes.
        # The SDK is sync (requests-based) — offload so it doesn't block the loop.
        result = await asyncio.to_thread(
            cloudinary.uploader.upload, io.BytesIO(data), resource_type="image"
        )
        return result["secure_url"]
