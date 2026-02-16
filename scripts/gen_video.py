import json
import subprocess
from pathlib import Path

CURRENT_VERSE_PATH = Path("current_verse.json")
VIDEOS_DIR = Path("outputs/videos")


def load_current_verse():
    if not CURRENT_VERSE_PATH.exists():
        raise FileNotFoundError(
            f"{CURRENT_VERSE_PATH} not found. Run previous scripts first."
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


def main():
    data = load_current_verse()

    ref = data.get("reference") or data.get("verse_ref")
    if not ref:
        raise ValueError("current_verse.json must contain 'reference' or 'verse_ref'.")

    bg_path = data.get("background_image_path")
    audio_path = data.get("audio_path")

    if not bg_path or not audio_path:
        raise ValueError(
            "current_verse.json must contain 'background_image_path' and 'audio_path'."
        )

    image_path = Path(bg_path)
    audio_file = Path(audio_path)

    if not image_path.exists():
        raise FileNotFoundError(f"Background image not found: {image_path}")
    if not audio_file.exists():
        raise FileNotFoundError(f"Audio file not found: {audio_file}")

    VIDEOS_DIR.mkdir(parents=True, exist_ok=True)

    out_name = f"{safe_ref(ref)}.mp4"
    video_path = VIDEOS_DIR / out_name

    cmd = [
        "ffmpeg",
        "-y",
        "-loop",
        "1",
        "-i",
        str(image_path),
        "-i",
        str(audio_file),
        "-c:v",
        "libx264",
        "-tune",
        "stillimage",
        "-c:a",
        "aac",
        "-b:a",
        "192k",
        "-pix_fmt",
        "yuv420p",
        "-shortest",
        str(video_path),
    ]

    print("Running ffmpeg:", " ".join(cmd))
    subprocess.run(cmd, check=True)

    data["video_path"] = str(video_path)
    save_current_verse(data)

    print(f"Saved video to {video_path}")
    print("Updated current_verse.json with video_path.")


if __name__ == "__main__":
    main()
