import os
import json
import random
import requests
from pathlib import Path
from typing import Dict, Any

from dotenv import load_dotenv

load_dotenv()

PEXELS_API_KEY = os.getenv("PEXELS_API_KEY")
PEXELS_SEARCH_URL = "https://api.pexels.com/v1/search"

BASE_DIR = Path(__file__).resolve().parent
OUTPUT_IMAGES_DIR = BASE_DIR / "outputs" / "images"
CURRENT_VERSE_JSON = BASE_DIR / "current_verse.json"


def load_current_verse() -> Dict[str, Any]:
    if not CURRENT_VERSE_JSON.exists():
        raise FileNotFoundError(f"{CURRENT_VERSE_JSON} not found")
    with CURRENT_VERSE_JSON.open("r", encoding="utf-8") as f:
        return json.load(f)


def save_current_verse(data: Dict[str, Any]) -> None:
    with CURRENT_VERSE_JSON.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def get_reference_key(verse_data: Dict[str, Any]) -> str:
    # Prefer an explicit key if you already store it
    ref_key = verse_data.get("reference_key")
    if ref_key:
        return ref_key

    # Fallback: sanitize the reference, e.g. "John 3:16" -> "John3_16"
    ref = verse_data.get("reference", "unknown_ref")
    ref_key = (
        ref.replace(" ", "")
           .replace(":", "_")
           .replace(",", "_")
           .replace(";", "_")
    )
    return ref_key


def fetch_pexels_forest_image(ref_key: str) -> str:
    """
    Download one vertical forest image from Pexels
    and save to outputs/images/<ref_key>.jpg
    """
    if not PEXELS_API_KEY:
        raise RuntimeError("PEXELS_API_KEY not set in environment")

    headers = {
        "Authorization": PEXELS_API_KEY
    }

    params = {
        "query": "dark forest night, cinematic, mystical",  # you can tweak this
        "per_page": 15,
        "orientation": "portrait"  # better for 9:16 reels
    }

    resp = requests.get(PEXELS_SEARCH_URL, headers=headers, params=params, timeout=10)
    resp.raise_for_status()
    data = resp.json()
    photos = data.get("photos", [])
    if not photos:
        raise RuntimeError("No Pexels photos found for query")

    photo = random.choice(photos)
    src = photo["src"].get("large2x") or photo["src"].get("original")
    if not src:
        raise RuntimeError("Selected Pexels photo has no usable src URL")

    img_resp = requests.get(src, timeout=20)
    img_resp.raise_for_status()

    OUTPUT_IMAGES_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUTPUT_IMAGES_DIR / f"{ref_key}.jpg"
    with out_path.open("wb") as f:
        f.write(img_resp.content)

    return str(out_path)


def main():
    verse_data = load_current_verse()
    ref_key = get_reference_key(verse_data)

    print(f"Using reference key: {ref_key}")

    image_path = fetch_pexels_forest_image(ref_key)
    print(f"Saved Pexels forest image to: {image_path}")

    # Store image_path back into current_verse.json for the video step
    verse_data["image_path"] = image_path
    save_current_verse(verse_data)
    print("Updated current_verse.json with image_path")


if __name__ == "__main__":
    main()
