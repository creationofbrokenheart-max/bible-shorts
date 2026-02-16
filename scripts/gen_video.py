import json
import os
import subprocess
import sys
from pathlib import Path

CURRENT_VERSE_JSON = Path("current_verse.json")
VIDEOS_DIR = Path("outputs/videos")
ASSETS_DIR = Path("assets")

# Path to background music (optional but recommended)
BG_MUSIC_PATH = ASSETS_DIR / "bg_music_low.mp3"

# FFmpeg binary (assume available in PATH)
FFMPEG_BIN = os.getenv("FFMPEG_BIN", "ffmpeg")


def load_current_verse():
    if not CURRENT_VERSE_JSON.exists():
        print("current_verse.json not found. Run previous steps first.", file=sys.stderr)
        sys.exit(1)
    with CURRENT_VERSE_JSON.open("r", encoding="utf-8") as f:
        return json.load(f)


def run_ffmpeg(cmd):
    print("Running FFmpeg command:")
    print(" ".join(cmd))
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if proc.returncode != 0:
        print("FFmpeg failed:")
        print(proc.stderr)
        sys.exit(1)
    else:
        print(proc.stderr)


def main():
    data = load_current_verse()

    reference = data.get("reference")
    summary_te = data.get("summary_te")
    bg_image_path = data.get("background_image_path")
    audio_path = data.get("audio_path")

    if not reference or not summary_te or not bg_image_path or not audio_path:
        print(
            "current_verse.json must contain 'reference', 'summary_te', "
            "'background_image_path', and 'audio_path'.",
            file=sys.stderr,
        )
        sys.exit(1)

    bg_image = Path(bg_image_path)
    audio_file = Path(audio_path)

    if not bg_image.exists():
        print(f"Background image not found: {bg_image}", file=sys.stderr)
        sys.exit(1)
    if not audio_file.exists():
        print(f"Audio file not found: {audio_file}", file=sys.stderr)
        sys.exit(1)

    # Prepare output
    VIDEOS_DIR.mkdir(parents=True, exist_ok=True)
    safe_ref = reference.replace(" ", "_").replace(":", "-")
    output_video = VIDEOS_DIR / f"{safe_ref}.mp4"

    # Basic settings
    duration = 15  # seconds
    fps = 30
    width = 1080
    height = 1920

    # Text to render (Telugu explanation)
    text_te = summary_te.replace("'", "’")  # avoid breaking drawtext with single quotes

    # Font: you must have a font that supports Telugu on the runner.
    # For now, we use a generic path; you can adjust later (e.g. Noto Sans Telugu).
    fontfile = os.getenv("VIDEO_FONT_PATH", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")

    # Build FFmpeg command:
    # - loop background image for `duration`
    # - overlay Telugu text in the lower part of the frame
    # - mix TTS audio with background music (if present)
    #
    # drawtext basics:[web:68][web:69]
    # x=(w-text_w)/2 centers horizontally
    # y=h*0.7 puts text near bottom.
    filter_complex_parts = []

    # Video chain: image -> scale -> drawtext
    video_chain = (
        f"[0:v]scale={width}:{height},format=yuv420p,"
        f"drawtext=fontfile='{fontfile}':"
        f"text='{text_te}':"
        "fontcolor=white:"
        "fontsize=48:"
        "box=1:boxcolor=black@0.4:boxborderw=20:"
        "x=(w-text_w)/2:"
        "y=h*0.7"
        "[v]"
    )
    filter_complex_parts.append(video_chain)

    # Audio chain: TTS (1) + optional bg music (2)
    if BG_MUSIC_PATH.exists():
        # Mix both audio inputs[web:71]
        audio_chain = (
            "[1:a]volume=1.0[a1];"
            "[2:a]volume=0.2[a2];"
            "[a1][a2]amix=inputs=2:duration=first[aout]"
        )
        filter_complex_parts.append(audio_chain)
        audio_map = "[aout]"
        audio_inputs = [
            "-i", str(audio_file),
            "-i", str(BG_MUSIC_PATH),
        ]
    else:
        # Only TTS audio
        audio_chain = "[1:a]volume=1.0[aout]"
        filter_complex_parts.append(audio_chain)
        audio_map = "[aout]"
        audio_inputs = ["-i", str(audio_file)]

    filter_complex = ";".join(filter_complex_parts)

    cmd 
