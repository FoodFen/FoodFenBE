"""CloudinaryImageStorage must translate the cloudinary:// URL into the SDK's
real config fields — cloudinary.config(cloudinary_url=...) is not a parameter
the installed SDK understands and silently no-ops, leaving uploads unauthenticated.
"""

from __future__ import annotations

import cloudinary

from src.infrastructure.images.cloudinary_image_storage import CloudinaryImageStorage


def test_constructor_parses_the_url_into_cloud_name_api_key_and_secret():
    CloudinaryImageStorage(cloudinary_url="cloudinary://mykey:mysecret@mycloud")

    cfg = cloudinary.config()
    assert cfg.cloud_name == "mycloud"
    assert cfg.api_key == "mykey"
    assert cfg.api_secret == "mysecret"
