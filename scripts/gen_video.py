import json
import subprocess
from pathlib import Path

CURRENT_VERSE_PATH = Path("current_verse.json")
VIDEOS_DIR = Path("outputs/videos")
TMP_DIR = Path("outputs/tmp")

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


def escape_drawtext(text: str) -> str:
    return (
        text.replace("\\", "\\\\")
        .replace(":", "\\:")
        .replace("'", "\\'")
        .replace("\n", "\\n")
    )


def run_ffmpeg(cmd: list[str]):
    print("Running ffmpeg:", " ".join(cmd))
    subprocess.run(cmd, check=True)


def main():
    data = load_current_verse()

    ref = data.get("reference") or data.get("verse_ref")
    verse_en = data.get("verse_en") or data.get("verse_text")
    summary_en = data.get("summary_en")
    if not ref or not verse_en or not summary_en:
        raise ValueError(
            "current_verse.json must contain 'reference', 'verse_en', and 'summary_en'."
        )

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
    TMP_DIR.mkdir(parents=True, exist_ok=True)

    font_path = Path(data.get("video_font_path") or DEFAULT_FONT)

    safe = safe_ref(ref)
    main_video = TMP_DIR / f"{safe}_main.mp4"
    tail_video = TMP_DIR / f"{safe}_tail.mp4"
    final_video = VIDEOS_DIR / f"{safe}.mp4"

    # 1) Main segment: darken + summary text over audio
    summary_text = escape_drawtext(summary_en)

    # Darken background with black overlay then draw summary text
    dark_bg = (
        "color=black@0.5:size=1080x1920 [blk];"
        "[0:v][blk]overlay=0:0:shortest=1[base]"
    )

    summary_draw = (
        f"[base]drawtext=fontfile='{font_path}':"
        f"text='{summary_text}':"
        "fontcolor=white:"
        "fontsize=52:"
        "line_spacing=10:"
        "box=1:boxcolor=black@0.6:boxborderw=20:"
        "x=(w-text_w)/2:"
        "y=h*0.65"
        "[vmain]"
    )

    filter_complex_main = f"{dark_bg};{summary_draw};[1:a]anull[a]"

    cmd_main = [
        "ffmpeg",
        "-y",
        "-loop", "1",
        "-i", str(image_path),  # 0:v
        "-i", str(audio_file),  # 1:a
        "-filter_complex", filter_complex_main,
        "-map", "[vmain]",
        "-map", "[a]",
        "-c:v", "libx264",
        "-tune", "stillimage",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        "-b:a", "192k",
        "-shortest",
        str(main_video),
    ]
    run_ffmpeg(cmd_main)

    # 2) Tail segment: dark background + full verse text, 5 seconds, no audio
    verse_text = escape_drawtext(verse_en)

    dark_bg_tail = (
        "color=black@0.5:size=1080x1920 [blk];"
        "[0:v][blk]overlay=0:0:shortest=1[base]"
    )

    tail_draw = (
        f"[base]drawtext=fontfile='{font_path}':"
        f"text='{verse_text}':"
        "fontcolor=white:"
        "fontsize=44:"
        "line_spacing=12:"
        "box=1:boxcolor=black@0.7:boxborderw=30:"
        "x=(w-text_w)/2:"
        "y=h*0.5"
        "[vout]"
    )

    filter_complex_tail = f"{dark_bg_tail};{tail_draw}"

    cmd_tail = [
        "ffmpeg",
        "-y",
        "-loop", "1",
        "-i", str(image_path),
        "-filter_complex", filter_complex_tail,
        "-map", "[vout]",
        "-t", "5",
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        str(tail_video),
    ]
    run_ffmpeg(cmd_tail)

    # 3) Concatenate main + tail
    concat_file = TMP_DIR / f"{safe}_files.txt"
    concat_file.write_text(
        f"file '{main_video.as_posix()}'\nfile '{tail_video.as_posix()}'\n",
        encoding="utf-8",
    )

    cmd_concat = [
        "ffmpeg",
        "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", str(concat_file),
        "-c", "copy",
        str(final_video),
    ]
    run_ffmpeg(cmd_concat)

    data["video_path"] = str(final_video)
    save_current_verse(data)

    print(f"Saved final video to {final_video}")
    print("Updated current_verse.json with video_path.")


if __name__ == "__main__":
    main()
