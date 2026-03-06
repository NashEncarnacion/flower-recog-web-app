"""
Facebook Graph API helper.

Publishes a photo (with a caption) to a Facebook Page using the
Page's permanent access token stored in the .env file.

Required .env keys:
    FB_PAGE_ID          – numeric Page ID (e.g. '123456789012345')
    FB_PAGE_ACCESS_TOKEN – a Page Access Token with pages_manage_posts
                           and pages_read_engagement permissions.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path

import requests

logger = logging.getLogger(__name__)

GRAPH_API_BASE = "https://graph.facebook.com/v22.0"


def _page_id() -> str:
    pid = os.getenv("FB_PAGE_ID", "")
    if not pid:
        raise EnvironmentError("FB_PAGE_ID is not set in the environment / .env file.")
    return pid


def _access_token() -> str:
    token = os.getenv("FB_PAGE_ACCESS_TOKEN", "")
    if not token:
        raise EnvironmentError(
            "FB_PAGE_ACCESS_TOKEN is not set in the environment / .env file."
        )
    return token


def post_photo_to_page(
    image_path: str | Path,
    caption: str,
    published: bool = True,
) -> dict:
    """
    Upload a photo to the configured Facebook Page.

    Parameters
    ----------
    image_path : str or Path
        Absolute path to the image file (JPEG or PNG).
    caption : str
        Text caption / message to accompany the photo.
    published : bool
        If False the post is saved as a draft. Default True.

    Returns
    -------
    dict
        The Graph API JSON response, e.g. {"id": "<post-id>"}.

    Raises
    ------
    requests.HTTPError
        When the Graph API returns a non-2xx status.
    """
    url = f"{GRAPH_API_BASE}/{_page_id()}/photos"
    image_path = Path(image_path)

    if not image_path.exists():
        raise FileNotFoundError(f"Image not found: {image_path}")

    mime = "image/jpeg" if image_path.suffix.lower() in (".jpg", ".jpeg") else "image/png"

    logger.info("Uploading '%s' to Facebook Page %s…", image_path.name, _page_id())

    with open(image_path, "rb") as fh:
        response = requests.post(
            url,
            data={
                "caption": caption,
                "access_token": _access_token(),
                "published": str(published).lower(),
            },
            files={"source": (image_path.name, fh, mime)},
            timeout=60,
        )

    try:
        response.raise_for_status()
    except requests.HTTPError:
        try:
            fb_error = response.json().get("error", {})
            logger.error(
                "Facebook API error %s: code=%s, type=%s, message=%s",
                response.status_code,
                fb_error.get("code"),
                fb_error.get("type"),
                fb_error.get("message"),
            )
        except Exception:
            logger.error("Facebook API error %s: %s", response.status_code, response.text)
        raise

    result = response.json()
    logger.info("Photo posted successfully. Post ID: %s", result.get("post_id") or result.get("id"))
    return result


def upload_photo_unpublished(image_path: str | Path, caption: str = None) -> str:
    """
    Upload a photo to the page without publishing it.

    Returns the Facebook photo ID, which can later be attached to a
    feed post via ``post_photos_to_page``.
    
    Parameters
    ----------
    image_path : str or Path
        Path to the image file.
    caption : str, optional
        Caption/description for this specific photo (used in multi-photo posts).
    """
    image_path = Path(image_path)
    if not image_path.exists():
        raise FileNotFoundError(f"Image not found: {image_path}")

    url = f"{GRAPH_API_BASE}/{_page_id()}/photos"
    mime = "image/jpeg" if image_path.suffix.lower() in (".jpg", ".jpeg") else "image/png"

    logger.info("Uploading '%s' as unpublished photo…", image_path.name)

    post_data = {
        "published": "false",
        "access_token": _access_token(),
    }
    
    if caption:
        post_data["caption"] = caption

    with open(image_path, "rb") as fh:
        response = requests.post(
            url,
            data=post_data,
            files={"source": (image_path.name, fh, mime)},
            timeout=60,
        )

    try:
        response.raise_for_status()
    except requests.HTTPError:
        try:
            fb_error = response.json().get("error", {})
            logger.error(
                "Facebook API error %s: code=%s, type=%s, message=%s",
                response.status_code,
                fb_error.get("code"),
                fb_error.get("type"),
                fb_error.get("message"),
            )
        except Exception:
            logger.error("Facebook API error %s: %s", response.status_code, response.text)
        raise

    photo_id = response.json().get("id")
    logger.info("Unpublished photo ID: %s", photo_id)
    return photo_id


def post_photos_to_page(
    image_paths: list,
    caption: str,
    photo_captions: list = None,
) -> dict:
    """
    Upload multiple images as a single Facebook Page post.

    Uploads each image as an unpublished photo, then publishes one
    feed post that attaches all of them at once.

    Parameters
    ----------
    image_paths : list of str or Path
        Paths to the image files.
    caption : str
        Post message shown above the photos.
    photo_captions : list of str, optional
        Individual captions for each photo (used in multi-photo posts).
        Must match the length of image_paths if provided.

    Returns
    -------
    dict
        Graph API JSON response, e.g. {"id": "<post-id>"}.
    """
    if not image_paths:
        raise ValueError("image_paths must not be empty.")
    
    if photo_captions and len(photo_captions) != len(image_paths):
        raise ValueError("photo_captions must match the length of image_paths")

    # Step 1: upload each photo as unpublished
    photo_ids = []
    for i, path in enumerate(image_paths):
        photo_caption = photo_captions[i] if photo_captions else None
        photo_id = upload_photo_unpublished(path, caption=photo_caption)
        photo_ids.append(photo_id)

    # Step 2: publish a single feed post that references all photo IDs
    url = f"{GRAPH_API_BASE}/{_page_id()}/feed"
    attached_media = [{"media_fbid": pid} for pid in photo_ids]

    logger.info("Creating multi-photo post with %d image(s)…", len(photo_ids))

    post_data = {
        "message": caption,
        "attached_media": json.dumps(attached_media),
        "access_token": _access_token(),
    }

    logger.debug("Post data (excluding token): %s", {k: v for k, v in post_data.items() if k != "access_token"})

    response = requests.post(
        url,
        data=post_data,
        timeout=60,
    )

    try:
        response.raise_for_status()
    except requests.HTTPError:
        try:
            fb_error = response.json().get("error", {})
            logger.error(
                "Facebook API error %s: code=%s, type=%s, message=%s",
                response.status_code,
                fb_error.get("code"),
                fb_error.get("type"),
                fb_error.get("message"),
            )
        except Exception:
            logger.error("Facebook API error %s: %s", response.status_code, response.text)
        raise

    result = response.json()
    logger.info("Multi-photo post created. Post ID: %s", result.get("id"))
    return result
