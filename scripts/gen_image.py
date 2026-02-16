import json
import os
from pathlib import Path

import replicate  # pip install replicate

CURRENT_VERSE_PATH = Path("current_verse.json")
IMAGES_DIR = Path("outputs/images")

REPLICATE_API_TOKEN = os.getenv("REPLICATE_API_TOKEN")
# SDXL version ID from Replicate docs[web:287][web:293]
SDXL_VERSION = os.getenv(
    "REPLICATE_SDXL_VERSION",
    "stability-ai/sdxl:39ed52f2a78e934b3ba6e2a89f5b1c712de7dfea535525255b1aa35c5565e08b",
)


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
        f"cinematic bible illustration, ultra detailed, 4k, "
        f"scene inspired by {reference} from the Bible, "
        f"theme: {summary_en}, "
        f"dark background, rich shadows, high contrast, moody lighting, "
        f"dramatic light rays, volumetric lighting, no text, no watermark"
    )
    return prompt


def call_replicate_sdxl(prompt: str, output_path: Path):
    if not REPLICATE_API_TOKEN:
        raise RuntimeError("REPLICATE_API_TOKEN is not set.")

    client = replicate.Client(api_token=REPLICATE_API_TOKEN)

    print("Calling Replicate SDXL with prompt:")
    print(prompt)

    # SDXL input options from Replicate examples[web:292][web:295]
    output = client.run(
        SDXL_VERSION,
        input={
            "prompt": prompt,
            "negative_prompt": "text, watermark, logo, words, letters, caption, lowres, blurry, distorted, ugly, oversaturated",
            "width": 768,
            "height": 1344,  # ~9:16
            "num_inference_steps": 30,
            "guidance_scale": 7.5,
        },
    )

    # output is typically a list of URLs; download the first
    if not output:
        raise RuntimeError(f"Replicate SDXL returned empty output: {output}")

    image_url = output[0]
    print("Downloading image from:", image_url)

    import requests

    resp = requests.get(image_url, timeout=120)
    resp.raise_for_status()

    with output_path.open("wb") as f:
        f.write(resp.content)


def main():
    data = load_current_verse()

    ref = data.get("reference") or data.get("verse_ref")
    if not ref:
        raise ValueError("current_verse.json must contain 'reference' or 'verse_ref'.")

    IMAGES_DIR.mkdir(parents=True, exist_ok=True)
    out_name = f"{safe_ref(ref)}.png"
    out_path = IMAGES_DIR / out_name

    prompt = build_prompt(data)
    print("Generating verse-relevant image with Replicate SDXL...")
    call_replicate_sdxl(prompt, out_path)

    data["background_image_path"] = str(out_path)
    save_current_verse(data)

    print(f"Saved background image to {out_path}")
    print("Updated current_verse.json with background_image_path.")


if __name__ == "__main__":
    main()
