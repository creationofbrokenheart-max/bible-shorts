#!/usr/bin/env python3
# scripts/gen_video.py

import os
import sys
import json
import shlex
import logging
import subprocess
from pathlib import Path
from typing import Dict, Any

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("gen_video")

BASE_DIR = Path(__file__).resolve().parents[1]  # repo root
CURRENT_VERSE_JSON = BASE_DIR / "current_verse.json"
OUTPUT_VIDEOS_DIR = BASE_DIR / "outputs" / "videos"
TMP_DIR = BASE_DIR / "outputs" / "tmp"

VIDEO_FONT_PATH = os.getenv(
    "VIDEO_FONT_PATH",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
)

VIDEO_WIDTH = 1080
VIDEO_HEIGHT = 1920


def load_current_verse() -> Dict[str, Any]:
    if not CURRENT_VERSE_JSON.exists():
        raise FileNotFoundError(f"{CURRENT_VERSE_JSON} not found")
    with CURRENT_VERSE_JSON.open("r", encoding="utf-8") as f:
        return json.load(f)


def run_ffmpeg(cmd):
    logger.info("Running ffmpeg: %s", " ".join(shlex.quote(c) for c in cmd))
    subprocess.run(cmd, check=True)


def ffmpeg_escape_text(text: str) -> str:
    """
    Minimal escaping so text is safe in drawtext's single-quoted text value.[web:387][web:411]
    """
    if not text:
        return ""
    text = text.replace("\\", "\\\\")   # backslashes
    text = text.replace("'", r"\'")     # single quotes
    text = text.replace("%", r"\%")     # percent
    text = text.replace("\n", " ")      # newlines -> space
    return text


def main() -> int:
    try:
        data = load_current_verse()

        required_keys = ["background_image_path", "audio_path", "reference"]
        missing = [k for k in required_keys if k not in data or not data[k]]
        if missing:
            raise ValueError(
                f"current_verse.json must contain {required_keys}. Missing: {missing}"
            )

        bg_path = str((BASE_DIR / data["background_image_path"]).resolve())
        audio_path = str((BASE_DIR / data["audio_path"]).resolve())
        reference = data["reference"]

        # Text to display: summary_en or summary
        text = data.get("summary_en") or data.get("summary") or ""
        if not text:
            raise ValueError("current_verse.json has no text field (summary_en/summary missing)")

        OUTPUT_VIDEOS_DIR.mkdir(parents=True, exist_ok=True)
        TMP_DIR.mkdir(parents=True, exist_ok=True)

        safe_ref = reference.replace(" ", "_").replace(":", "-")
        main_out = OUTPUT_VIDEOS_DIR / f"{safe_ref}.mp4"
        tmp_main = TMP_DIR / f"{safe_ref}_main.mp4"

        overlay_text = ffmpeg_escape_text(text)
        logger.info("[gen_video] overlay text: %s", overlay_text)

        # Scale + pad background, then caption in center, plus audio.[web:394][web:412]
        filter_complex = (
            f"[0:v]scale={VIDEO_WIDTH}:{VIDEO_HEIGHT}:force_original_aspect_ratio=decrease,"
            f"pad={VIDEO_WIDTH}:{VIDEO_HEIGHT}:(ow-iw)/2:(oh-ih)/2:color=black@0.0[base];"
            f"[base]drawtext=fontfile='{VIDEO_FONT_PATH}':"
            f"text='{overlay_text}':"
            "fontcolor=white:fontsize=52:line_spacing=10:box=1:boxcolor=black@0.6:boxborderw=20:"
            "x=(w-text_w)/2:y=(h-text_h)/2[vmain];"
            "[1:a]anull[a]"
        )

        cmd_main = [
            "ffmpeg",
            "-y",
            "-loop", "1",
            "-i", bg_path,
            "-i", audio_path,
            "-filter_complex", filter_complex,
            "-map", "[vmain]",
            "-map", "[a]",
            "-c:v", "libx264",
            "-tune", "stillimage",
            "-pix_fmt", "yuv420p",
            "-c:a", "aac",
            "-b:a", "192k",
            "-shortest",
            str(tmp_main),
        ]

        run_ffmpeg(cmd_main)
        os.replace(tmp_main, main_out)

        data["video_path"] = str(main_out.relative_to(BASE_DIR))
        with CURRENT_VERSE_JSON.open("w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        logger.info("[gen_video] saved %s and updated current_verse.json", main_out)
        return 0

    except subprocess.CalledProcessError as e:
        logger.error("[gen_video] ffmpeg failed with code %s", e.returncode)
        return 1
    except Exception as e:
        logger.exception("[gen_video] fatal error: %s", e)
        return 1


if __name__ == "__main__":
    sys.exit(main())
