import io
import json
import os
import sys
from pathlib import Path

import requests
from PIL import Image

CURRENT_VERSE_JSON = Path("current_verse.json")
OUTPUT_DIR = Path("outputs/images")

# Hugging Face text-to-image Inference API.[web:57]
HF_TOKEN = os.getenv("HF_TOKEN")
# You can change model id if you prefer another (e.g. sdxl, flux, etc.).
HF_T2I_MODEL = os.getenv(
    "HF_T2I_MODEL",
    "stabilityai/stable-diffusion-xl-base-1.0",
)
HF_T2I_URL = f"https://api-inference.huggingface.co/models/{HF_T2I_MODEL}"


def load_current_verse():
    if not CURRENT_VERSE_JSON.exists():
        print("current_verse.json not found. Run previous steps first.", file=sys.stderr)
        sys.exit(1)
    with CURRENT_VERSE_JSON.open("r", encoding="utf-8") as f:
        return json.load(f)


def build_image_prompt(reference: str, summary_en: str) -> str:
    """
    Build a short text prompt describing the background.
    No text in the image, just scenery suitable for a Bible verse reel.
    """
    base = (
        "Peaceful cinematic nature background for a Christian Bible verse video, "
        "soft warm sunrise light, gentle camera feel, no text, no people, "
        "vertical framing, high quality."
    )
    # Lightly condition on verse theme if summary is available
    if summary_en:
        return f"{base} Theme: {summary_en}"
    return base


def generate_image(prompt: str, out_path: Path):
    if not HF_TOKEN:
        print("HF_TOKEN environment variable is not set.", file=sys.stderr)
        sys.exit(1)

    headers = {
        "Authorization": f"Bearer {HF_TOKEN}",
        "Accept": "image/png",
    }

    payload = {"inputs": prompt}

    print(f"Requesting image from Hugging Face model: {HF_T2I_MODEL}")
    try:
        resp = requests.post(HF_T2I_URL, headers=headers, json=payload, timeout=60)
    except requests.RequestException as e:
        print(f"Error calling HF text-to-image API: {e}", file=sys.stderr)
        sys.exit(1)

    if resp.status_code != 200:
        print(f"HF text-to-image error {resp.status_code}: {resp.text}", file=sys.stderr)
        sys.exit(1)

    # resp.content is raw image bytes[web:57]
    image_bytes = io.BytesIO(resp.content)
    try:
        img = Image.open(image_bytes)
    except Exception as e:
        print(f"Failed to decode image bytes: {e}", file=sys.stderr)
        sys.exit(1)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    img.save(out_path, format="PNG")
    print(f"Saved background image to {out_path}")


def main():
    data = load_current_verse()
    reference = data.get("reference")
    summary_en = data.get("summary_en", "")

    if not reference:
        print("current_verse.json must contain 'reference'.", file=sys.stderr)
        sys.exit(1)

    prompt = build_image_prompt(reference, summary_en)
    safe_ref = reference.replace(" ", "_").replace(":", "-")
    out_path = OUTPUT_DIR / f"{safe_ref}.png"

    generate_image(prompt, out_path)

    # Optionally record path in JSON for downstream steps
    data["background_image_path"] = str(out_path)
    with CURRENT_VERSE_JSON.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print("Updated current_verse.json with background_image_path.")


if __name__ == "__main__":
    main()
