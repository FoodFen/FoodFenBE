"""The upload check shared by every image endpoint."""

from __future__ import annotations

from fastapi import UploadFile

from src.domain.exceptions import UnreadableImageException

# Browser-renderable only (no HEIC): these images are shown on the web and in the app.
_ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}
_MAX_IMAGE_BYTES = 5 * 1024 * 1024


async def read_image(image: UploadFile) -> bytes:
    """The file's bytes, or ``UnreadableImageException`` (400) if it isn't a JPEG/PNG/WebP under 5 MB."""
    if image.content_type not in _ALLOWED_IMAGE_TYPES:
        raise UnreadableImageException(f"unsupported image type: {image.content_type!r}")
    data = await image.read(_MAX_IMAGE_BYTES + 1)
    if len(data) > _MAX_IMAGE_BYTES:
        raise UnreadableImageException("image is larger than 5 MB")
    if not (
        data.startswith((b"\xff\xd8\xff", b"\x89PNG"))
        or (data[:4] == b"RIFF" and data[8:12] == b"WEBP")
    ):
        raise UnreadableImageException("file is not a JPEG, PNG or WebP image")
    return data
