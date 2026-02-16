import json
import subprocess
from pathlib import Path

CURRENT_VERSE_PATH = Path("current_verse.json")
VIDEOS_DIR = Path("outputs/videos")

# Make sure this matches the font path on Actions (you also set VIDEO_FONT_PATH in main.yml)
DEFAULT_FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"


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
    summary_en = data.get("summary_en")

    if not bg_path or not audio_path:
        raise ValueError(
            "current_verse.json must contain 'background_image_path' and 'audio_path'."
        )
    if not summary_en:
        raise ValueError("current_verse.json must contain 'summary_en'.")

    image_path = Path(bg_path)
    audio_file = Path(audio_path)

    if not image_path.exists():
        raise FileNotFoundError(f"Background image not found: {image_path}")
    if not audio_file.exists():
        raise FileNotFoundError(f"Audio file not found: {audio_file}")

    VIDEOS_DIR.mkdir(parents=True, exist_ok=True)

    out_name = f"{safe_ref(ref)}.mp4"
    video_path = VIDEOS_DIR / out_name

    font_path = Path(
        data.get("video_font_path")
        or DEFAULT_FONT
    )

    # Text fade timings (seconds)
    fade_in_start = 0.0
    fade_in_duration = 0.8
    fade_out_start = 4.5
    fade_out_duration = 0.8

    # Escape for drawtext
    text = (
        summary_en
        .replace("\\", "\\\\")
        .replace(":", "\\:")
        .replace("'", "\\'")
        .replace("\n", "\\n")
    )

    # Drawtext with box and alpha fade over the image
    drawtext_filter = (
        f"drawtext=fontfile='{font_path}':"
        f"text='{text}':"
        "fontcolor=white:"
        "fontsize=52:"
        "line_spacing=10:"
        "box=1:boxcolor=black@0.6:boxborderw=20:"
        "x=(w-text_w)/2:"
        "y=h*0.65:"
        f"enable='between(t,{fade_in_start},{fade_out_start + fade_out_duration})'"
    )

    # Filter_complex: video -> drawtext; audio -> atempo (slightly slower voice)
    filter_complex = (
        f"[0:v]{drawtext_filter}[v];"
        f"[1:a]atempo=0.9[a]"  # 0.9 = ~10% slower voice[web:208][web:211]
    )

    cmd = [
        "ffmpeg",
        "-y",
        "-loop",
        "1",
        "-i",
        str(image_path),   # 0:v
        "-i",
        str(audio_file),   # 1:a
        "-filter_complex",
        filter_complex,
        "-map",
        "[v]",
        "-map",
        "[a]",
        "-c:v",
        "libx264",
        "-tune",
        "stillimage",
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "aac",
        "-b:a",
        "192k",
        "-shortest",
        str(video_path),
    ]

    print("Running ffmpeg:", " ".join(cmd))
    subprocess.run(cmd, check=True)

    data["video_path"] = str(video_path)
    save_current_verse(data)

    print(f"Saved video with text overlay to {video_path}")
    print("Updated current_verse.json with video_path.")


if __name__ == "__main__":
    main()
