import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter  # pip install pillow

CURRENT_VERSE_PATH = Path("current_verse.json")
IMAGES_DIR = Path("outputs/images")


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


def build_base_image(width=1080, height=1920) -> Image.Image:
    # Dark background with subtle vignette to highlight text
    img = Image.new("RGB", (width, height), (5, 5, 10))
    draw = ImageDraw.Draw(img)

    # Simple radial vignette
    for i in range(0, max(width, height), 80):
        alpha = int(255 * (i / max(width, height)))
        draw.rectangle(
            [i, i, width - i, height - i],
            fill=(0, 0, 0),
            outline=None,
        )

    img = img.filter(ImageFilter.GaussianBlur(radius=8))
    return img


def main():
    data = load_current_verse()

    ref = data.get("reference") or data.get("verse_ref")
    if not ref:
        raise ValueError("current_verse.json must contain 'reference' or 'verse_ref'.")

    IMAGES_DIR.mkdir(parents=True, exist_ok=True)
    out_name = f"{safe_ref(ref)}.png"
    out_path = IMAGES_DIR / out_name

    print("Creating local dark background image (no external API).")

    img = build_base_image()
    img.save(out_path, format="PNG", optimize=True)

    data["background_image_path"] = str(out_path)
    save_current_verse(data)

    print(f"Saved background image to {out_path}")
    print("Updated current_verse.json with background_image_path.")


if __name__ == "__main__":
    main()
