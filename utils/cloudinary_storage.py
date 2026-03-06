"""
Cloudinary helper — upload images and return permanent CDN URLs.

Free tier: 25 GB storage, 25 GB bandwidth/month, no credit card needed.
Sign up at https://cloudinary.com/

Required .env key:
    CLOUDINARY_URL=cloudinary://API_KEY:API_SECRET@CLOUD_NAME

When CLOUDINARY_URL is not set the app falls back to serving images
from the local uploads/ folder (fine for local development).
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)


def is_configured() -> bool:
    """Return True if CLOUDINARY_URL is present in the environment."""
    return bool(os.getenv("CLOUDINARY_URL"))


def upload_image(local_path: Path, folder: str = "flower-recog") -> str:
    """
    Upload a local image to Cloudinary.

    Parameters
    ----------
    local_path : Path
        The local file to upload.
    folder : str
        Cloudinary folder to organise uploads under.

    Returns
    -------
    str
        Secure HTTPS URL of the uploaded image.
    """
    try:
        import cloudinary
        import cloudinary.uploader
    except ImportError as exc:
        raise RuntimeError(
            "cloudinary package not found. Run: pip install cloudinary"
        ) from exc

    # cloudinary.config() reads CLOUDINARY_URL automatically from the environment
    result = cloudinary.uploader.upload(
        str(local_path),
        folder=folder,
        resource_type="image",
        overwrite=False,
    )
    url = result.get("secure_url", "")
    logger.info("Uploaded '%s' → %s", local_path.name, url)
    return url
