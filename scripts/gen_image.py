# scripts/gen_image.py

import os
import sys
import json
import random
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional

import requests

# --- Logging -----------------------------------------------------------------

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("gen_image")

# --- Paths -------------------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parents[1]  # repo root
CURRENT_VERSE_JSON = BASE_DIR / "current_verse.json"
OUTPUT_IMAGES_DIR = BASE_DIR / "outputs" / "images"
CACHE_DIR = BASE_DIR / "cache" / "pexels"

CACHE_DIR.mkdir(parents=True, exist_ok=True)

# --- Pexels config -----------------------------------------------------------

PEXELS_API_KEY_ENV = "PEXELS_API_KEY"
PEXELS_SEARCH_URL = "https://api.pexels.com/v1/search"


# --- Helpers -----------------------------------------------------------------


def load_current_verse() -> Dict[str, Any]:
    if not CURRENT_VERSE_JSON.exists():
        raise FileNotFoundError(f"{CURRENT_VERSE_JSON} not found")
    with CURRENT_VERSE_JSON.open("r", encoding="utf-8") as f:
        return json.load(f)


def save_current_verse(data: Dict[str, Any]) -> None:
    with CURRENT_VERSE_JSON.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def get_reference_key(data: Dict[str, Any]) -> str:
    if "reference_key" in data and data["reference_key"]:
        return data["reference_key"]

    ref = data.get("reference", "unknown_ref")
    ref_key = (
        ref.replace(" ", "")
           .replace(":", "_")
           .replace(",", "_")
           .replace(";", "_")
    )
    return ref_key


# --- Simple Pexels client with cache ----------------------------------------


def _cache_path(query: str) -> Path:
    safe = query.replace(" ", "_").replace(",", "_")
    return CACHE_DIR / f"{safe}.json"


def _load_cache(query: str) -> Optional[List[Dict[str, Any]]]:
    path = _cache_path(query)
    if not path.exists():
        return None
    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("photos")
    except Exception:
        return None


def _save_cache(query: str, photos: List[Dict[str, Any]]) -> None:
    path = _cache_path(query)
    with path.open("w", encoding="utf-8") as f:
        json.dump({"photos": photos}, f)


def search_pexels(query: str, api_key: str) -> List[Dict[str, Any]]:
    cached = _load_cache(query)
    if cached:
        logger.info("[pexels] using cache for query='%s' (%d photos)", query, len(cached))
        return cached

    headers = {"Authorization": api_key}
    params = {
        "query": query,
        "per_page": 30,
        "orientation": "portrait",
    }

    resp = requests.get(PEXELS_SEARCH_URL, headers=headers, params=params, timeout=15)
    if resp.status_code == 429:
        logger.error("[pexels] rate limited (429) for query='%s'", query)
        resp.raise_for_status()
    resp.raise_for_status()

    data = resp.json()
    photos = data.get("photos", [])
    _save_cache(query, photos)
    return photos


def pick_photo_url(query: str, api_key: str) -> str:
    photos = search_pexels(query, api_key)
    if not photos:
        raise RuntimeError(f"No Pexels photos for query='{query}'")

    photo = random.choice(photos)
    srcs = photo.get("src", {})
    url = srcs.get("large2x") or srcs.get("original") or srcs.get("large")
    if not url:
        raise RuntimeError("Selected Pexels photo has no usable src URL")
    return url


# --- Main --------------------------------------------------------------------


def main() -> int:
    try:
        verse_data = load_current_verse()
        ref_key = get_reference_key(verse_data)

        api_key = os.getenv(PEXELS_API_KEY_ENV)
        if not api_key:
            raise RuntimeError(f"{PEXELS_API_KEY_ENV} not set in environment")

        # You can later make this dynamic from verse topic if you want
        query = verse_data.get(
            "image_theme",
            "dark forest night, cinematic, mystical"
        )

        logger.info("[gen_image] reference_key=%s query=%s", ref_key, query)

        img_url = pick_photo_url(query, api_key)
        logger.info("[gen_image] selected Pexels URL: %s", img_url)

        OUTPUT_IMAGES_DIR.mkdir(parents=True, exist_ok=True)
        out_path = OUTPUT_IMAGES_DIR / f"{ref_key}.jpg"

        resp = requests.get(img_url, timeout=30)
        resp.raise_for_status()
        with out_path.open(mode="wb") as f:
             f.write(resp.content)


        verse_data["image_path"] = str(out_path)
        save_current_verse(verse_data)
        logger.info("[gen_image] saved %s and updated current_verse.json", out_path)

        return 0
    except Exception as e:
        logger.exception("[gen_image] fatal error: %s", e)
        return 1


if __name__ == "__main__":
    sys.exit(main())
