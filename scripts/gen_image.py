import json
import os
from pathlib import Path
import base64
import requests

CURRENT_VERSE_PATH = Path("current_verse.json")
IMAGES_DIR = Path("outputs/images")

STABILITY_API_KEY = os.getenv("STABILITY_API_KEY")
STABILITY_URL = "https://api.stability.ai/v2beta/stable-image/generate/sd3"


def load_current_verse():
    if not CURRENT_VERSE_PATH.exists():
        raise FileNotFoundError(
            f"{CURRENT_VERSE_PATH} not found. Run select_verse.py and fetch_verse_text.py first."
        )
    with CURRENT_VERSE_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)


def save_current_verse(data: dict):
    with CURRENT_VERSE_PATH.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def safe_ref(ref: str) -> str:
    return (
        ref.replace(" ", "_")
        .replace(":", "-")
        .replace("/", "_")
    )


def build_prompt(data: dict) -> str:
    reference = data.get("reference") or data.get("verse_ref") or ""
    summary_en = data.get("summary_en") or data.get("verse_en") or ""

    prompt = (
        f"Cinematic Bible artwork, ultra detailed, 4K look. "
        f"Scene inspired by {reference} from the Bible. "
        f"Theme: {summary_en} "
        f"dark background, rich shadows, high contrast, moody lighting, "
        f"dramatic light rays, volumetric lighting, no text, no watermark."
    )
    return prompt


def call_stability_t2i(prompt: str) -> bytes:
    if not STABILITY_API_KEY:
        raise RuntimeError("STABILITY_API_KEY is not set.")

    headers = {
        "Authorization": f"Bearer {STABILITY_API_KEY}",
        # DO NOT set Content-Type here; requests sets it for multipart
        "Accept": "application/json",
    }

    # sd3 endpoint expects multipart/form-data with a 'prompt' field.[web:279]
    data = {
        "prompt": prompt,
        "output_format": "png",
        "aspect_ratio": "9:16",
        "negative_prompt": "text, watermark, logo, words, letters, caption, lowres, blurry, distorted, ugly, oversaturated",
    }

    resp = requests.post(
        STABILITY_URL,
        headers=headers,
        data=data,
        files={},  # no image upload, but multipart is still required
        timeout=120,
    )

    if resp.status_code != 200:
        print("Stability status:", resp.status_code)
        print("Stability body:", resp.text)
        resp.raise_for_status()

    resp_json = resp.json()
    if "image" in resp_json:
        b64 = resp_json["image"]
    else:
        images = resp_json.get("images") or []
        if not images or "image" not in images[0]:
            raise RuntimeError(f"Unexpected Stability response: {resp_json}")
        b64 = images[0]["image"]

    return base64.b64decode(b64)


def main():
    data = load_current_verse()

    ref = data.get("reference") or data.get("verse_ref")
    if not ref:
        raise ValueError("current_verse.json must contain 'reference' or 'verse_ref'.")

    IMAGES_DIR.mkdir(parents=True, exist_ok=True)
    out_name = f"{safe_ref(ref)}.png"
    out_path = IMAGES_DIR / out_name

    prompt = build_prompt(data)
    print("Requesting dark cinematic image from Stability SD3")
    print("Prompt:", prompt)

    image_bytes = call_stability_t2i(prompt)

    with out_path.open("wb") as f:
        f.write(image_bytes)

    data["background_image_path"] = str(out_path)
    save_current_verse(data)

    print(f"Saved background image to {out_path}")
    print("Updated current_verse.json with background_image_path.")


if __name__ == "__main__":
    main()
