"""
Plant / flower classifier.

Primary backend: PlantNet REST API (https://my.plantnet.org/)
  - ~30,000 plant species worldwide, the same model used by the PlantNet app.
  - Requires a free API key in .env:  PLANTNET_API_KEY=<your_key>
  - Free tier: 500 requests / day.

Fallback backend: google/vit-base-patch16-224 via HuggingFace Transformers.
  - Used automatically when PLANTNET_API_KEY is not set.
  - Covers ImageNet-1k classes (~1000), good for common flowers.

In both cases, predictions below CONFIDENCE_THRESHOLD are returned as
"Unknown" so the app never confidently shows a wrong species name.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

import io

import requests
from PIL import Image as PILImage

logger = logging.getLogger(__name__)

# PlantNet rejects images larger than ~5 MB; resize to this max dimension first.
PLANTNET_MAX_PX = 1500

PLANTNET_API_URL = "https://my-api.plantnet.org/v2/identify/all"

# Fallback HuggingFace model (used when no PlantNet API key is configured).
FALLBACK_MODEL_ID = "google/vit-base-patch16-224"

# Predictions below this threshold are labelled "Unknown".
CONFIDENCE_THRESHOLD = 0.15

_hf_pipeline = None  # lazy singleton for the fallback model


# ── PlantNet API ──────────────────────────────────────────────────────────────

def _classify_plantnet(image_path: Path) -> list[dict]:
    api_key = os.getenv("PLANTNET_API_KEY", "")

    # Resize image in-memory so it stays under PlantNet's upload limit (~5 MB).
    img = PILImage.open(image_path).convert("RGB")
    img.thumbnail((PLANTNET_MAX_PX, PLANTNET_MAX_PX), PILImage.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=85)
    buf.seek(0)

    response = requests.post(
        PLANTNET_API_URL,
        params={"api-key": api_key, "lang": "en"},
        files=[("images", (image_path.stem + ".jpg", buf, "image/jpeg"))],
        data={"organs": ["auto"]},
        timeout=30,
    )

    response.raise_for_status()
    data = response.json()

    results = []
    for item in data.get("results", [])[:5]:
        score = float(item.get("score", 0))
        species = item.get("species", {})
        sci_name = species.get("scientificNameWithoutAuthor", "Unknown")
        common = species.get("commonNames", [])
        common_name = common[0] if common else None
        
        # Show common name first if available, with scientific name in parentheses
        if common_name:
            label = f"{common_name} ({sci_name})"
        else:
            label = sci_name
        
        results.append({
            "label": label if score >= CONFIDENCE_THRESHOLD else "Unknown",
            "common_name": common_name if score >= CONFIDENCE_THRESHOLD else None,
            "scientific_name": sci_name if score >= CONFIDENCE_THRESHOLD else "Unknown",
            "score": score,
            "percent": f"{score * 100:.1f}%",
            "low_confidence": score < CONFIDENCE_THRESHOLD,
        })
    return results


# ── HuggingFace fallback ──────────────────────────────────────────────────────

def _get_hf_pipeline():
    global _hf_pipeline
    if _hf_pipeline is None:
        try:
            from transformers import pipeline as hf_pipeline
        except ImportError as exc:
            raise RuntimeError(
                "transformers not installed. Run: pip install transformers"
            ) from exc
        logger.info("Loading fallback model '%s'…", FALLBACK_MODEL_ID)
        _hf_pipeline = hf_pipeline(
            "image-classification",
            model=FALLBACK_MODEL_ID,
            top_k=5,
        )
    return _hf_pipeline


def _classify_hf(image_path: Path) -> list[dict]:
    image = PILImage.open(image_path).convert("RGB")
    raw = _get_hf_pipeline()(image)
    results = []
    for item in raw:
        score = float(item["score"])
        label = item["label"].replace("_", " ").title() if score >= CONFIDENCE_THRESHOLD else "Unknown"
        results.append({
            "label": label,
            "common_name": None,  # HuggingFace fallback doesn't have scientific names
            "scientific_name": label if score >= CONFIDENCE_THRESHOLD else "Unknown",
            "score": score,
            "percent": f"{score * 100:.1f}%",
            "low_confidence": score < CONFIDENCE_THRESHOLD,
        })
    return results


# ── Public API ────────────────────────────────────────────────────────────────

def classify_image(image_path: str | Path) -> list[dict]:
    """
    Classify a plant/flower image. Uses PlantNet API if PLANTNET_API_KEY is set,
    otherwise falls back to the local HuggingFace model.

    Returns a list of up to 5 predictions, each dict:
      - "label"          : str   – display name
      - "score"          : float – confidence in [0, 1]
      - "percent"        : str   – e.g. "87.3%"
      - "low_confidence" : bool  – True when score < CONFIDENCE_THRESHOLD
    """
    image_path = Path(image_path)
    if not image_path.exists():
        raise FileNotFoundError(f"Image not found: {image_path}")

    if os.getenv("PLANTNET_API_KEY"):
        logger.info("Using PlantNet API for '%s'", image_path.name)
        return _classify_plantnet(image_path)
    else:
        logger.info("PLANTNET_API_KEY not set — using local HuggingFace fallback.")
        return _classify_hf(image_path)


def top_prediction(image_path: str | Path) -> dict:
    """Return only the single highest-confidence prediction."""
    preds = classify_image(image_path)
    return preds[0] if preds else {
        "label": "Unknown", "score": 0.0, "percent": "0.0%", "low_confidence": True
    }
