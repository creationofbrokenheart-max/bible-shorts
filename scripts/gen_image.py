import json
import os
from pathlib import Path
from io import BytesIO

from huggingface_hub import InferenceClient  # pip install huggingface_hub


CURRENT_VERSE_PATH = Path("current_verse.json")
IMAGES_DIR = Path("outputs/images")

HF_TOKEN = os.getenv("HF_TOKEN")
HF_T2I_MODEL = os.getenv("HF_T2I_MODEL", "Tongyi-MAI/Z-Image")


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


def build_prompt(data: dict) -> tuple[str, str]:
    reference = data.get("reference") or data.get("verse_ref") or ""
    summary_en = data.get("summary_en") or data.get("verse_en") or ""

    prompt = (
        f"Cinematic Bible artwork, ultra detailed, 4K, high dynamic range. "
        f"Scene inspired by {reference} from the Bible. "
        f"Theme: {summary_en} "
        f"dark background, rich shadows, high contrast, moody lighting, "
        f"dramatic light rays, volumetric lighting, no text, no watermark."
    )

    negative_prompt = (
        "text, watermark, logo, words, letters, caption, "
        "lowres, blurry, distorted, ugly, oversaturated"
    )

    return prompt, negative_prompt


def call_hf_t2i(prompt: str, negative_prompt: str) -> bytes:
    if not HF_TOKEN:
        raise RuntimeError("HF_TOKEN is not set.")

    client = InferenceClient(api_key=HF_TOKEN)

    # No `size` kwarg – use model default resolution
    image = client.text_to_image(
        prompt=prompt,
        model=HF_T2I_MODEL,
        negative_prompt=negative_prompt,
    )

    buf = BytesIO()
    image.save(buf, format="PNG")
    return buf.getvalue()


def main():
    data = load_current_verse()

    ref = data.get("reference") or data.get("verse_ref")
    if not ref:
        raise ValueError("current_verse.json must contain 'reference' or 'verse_ref'.")

    IMAGES_DIR.mkdir(parents=True, exist_ok=True)
    out_name = f"{safe_ref(ref)}.png"
    out_path = IMAGES_DIR / out_name

    prompt, neg_prompt = build_prompt(data)
    print("Requesting dark cinematic image from Hugging Face model:", HF_T2I_MODEL)
    print("Prompt:", prompt)
    print("Negative prompt:", neg_prompt)

    image_bytes = call_hf_t2i(prompt, neg_prompt)

    with out_path.open("wb") as f:
        f.write(image_bytes)

    data["background_image_path"] = str(out_path)
    save_current_verse(data)

    print(f"Saved background image to {out_path}")
    print("Updated current_verse.json with background_image_path.")


if __name__ == "__main__":
    main()
