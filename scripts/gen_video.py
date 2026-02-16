#!/usr/bin/env python3
# scripts/gen_video.py

import os
import sys
import json
import shlex
import logging
import subprocess
from pathlib import Path
from typing import Dict, Any, List, Tuple

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


def run_subprocess(cmd: List[str]) -> subprocess.CompletedProcess:
    logger.info("Running: %s", " ".join(shlex.quote(c) for c in cmd))
    return subprocess.run(cmd, check=True, capture_output=True, text=True)


def get_audio_duration(audio_path: str) -> float:
    """
    Use ffprobe to get audio duration in seconds.
    """
    cmd = [
        "ffprobe",
        "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        audio_path,
    ]
    result = run_subprocess(cmd)
    dur_str = result.stdout.strip()
    try:
        return float(dur_str)
    except ValueError:
        logger.warning("Could not parse duration '%s', defaulting to 5s", dur_str)
        return 5.0


def ffmpeg_escape_text(text: str) -> str:
    if not text:
        return ""
    text = text.replace("\\", "\\\\")
    text = text.replace("'", r"\'")
    text = text.replace("%", r"\%")
    text = text.replace("\n", " ")
    return text


def build_word_segments(text: str, total_duration: float) -> List[Tuple[str, float, float]]:
    """
    Split text into words and assign equal time slices across total_duration.
    """
    words = [w for w in text.split() if w.strip()]
    if not words:
        return []

    per_word = total_duration / len(words)
    segments: List[Tuple[str, float, float]] = []
    t = 0.0
    for w in words:
        start = t
        end = min(total_duration, t + per_word)
        segments.append((w, start, end))
        t = end
    return segments


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

        text = data.get("summary_en") or data.get("summary") or ""
        if not text:
            raise ValueError("current_verse.json has no text field (summary_en/summary missing)")

        OUTPUT_VIDEOS_DIR.mkdir(parents=True, exist_ok=True)
        TMP_DIR.mkdir(parents=True, exist_ok=True)

        safe_ref = reference.replace(" ", "_").replace(":", "-")
        main_out = OUTPUT_VIDEOS_DIR / f"{safe_ref}.mp4"
        tmp_main = TMP_DIR / f"{safe_ref}_main.mp4"

        # Get audio duration and build karaoke word segments
        duration = get_audio_duration(audio_path)
        logger.info("[gen_video] audio duration: %.2fs", duration)
        segments = build_word_segments(text, duration)

        # Build drawtext chain: one word at a time
        draw_filters: List[str] = []
        for word, start, end in segments:
            w_esc = ffmpeg_escape_text(word)
            draw_filters.append(
                f"drawtext=fontfile='{VIDEO_FONT_PATH}':"
                f"text='{w_esc}':"
                "fontcolor=white:fontsize=80:box=1:boxcolor=black@0.7:boxborderw=20:"
                "x=(w-text_w)/2:y=(h-text_h)/2:"
                f"enable='between(t,{start:.2f},{end:.2f})'"
            )
        draw_chain = ",".join(draw_filters) if draw_filters else "null"

        # Filter graph: scale bg -> base, apply karaoke drawtexts -> vmain, audio passthrough
        filter_complex = (
            f"[0:v]scale={VIDEO_WIDTH}:{VIDEO_HEIGHT}:force_original_aspect_ratio=decrease,"
            f"pad={VIDEO_WIDTH}:{VIDEO_HEIGHT}:(ow-iw)/2:(oh-ih)/2:color=black@0.0[base];"
            f"[base]{draw_chain}[vmain];"
            "[1:a]anull[a]"
        )

        cmd_main = [
            "ffmpeg",
            "-y",
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
            "-t", f"{duration + 1:.2f}",  # a little tail after audio
            "-shortest",
            str(tmp_main),
        ]

        run_subprocess(cmd_main)
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
