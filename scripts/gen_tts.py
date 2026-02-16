import json
import os
import sys
from pathlib import Path

import requests

CURRENT_VERSE_JSON = Path("current_verse.json")
OUTPUT_DIR = Path("outputs/audio")

TTS_API_KEY = os.getenv("TTS_API_KEY")
TTS_API_URL = os.getenv("TTS_API_URL")  # e.g. https://client.camb.ai/apis/tts
TTS_VOICE_ID = os.getenv("TTS_VOICE_ID")  # required (147332 for your English voice)
TTS_LANGUAGE = os.getenv("TTS_LANGUAGE")  # optional; default to 1 below


def load_current_verse():
    if not CURRENT_VERSE_JSON.exists():
        print("current_verse.json not found. Run previous steps first.", file=sys.stderr)
        sys.exit(1)
    with CURRENT_VERSE_JSON.open("r", encoding="utf-8") as f:
        return json.load(f)


def save_current_verse(data):
    with CURRENT_VERSE_JSON.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def build_tts_payload(text_en: str) -> dict:
    """
    CAMB /apis/tts payload: requires text, voice_id, language.
    We use English text (summary_en) for now.
    """
    if not TTS_VOICE_ID:
        print("TTS_VOICE_ID must be set for CAMB.AI TTS.", file=sys.stderr)
        sys.exit(1)

    # Default English language id to 1 if not provided
    language_id = int(TTS_LANGUAGE) if TTS_LANGUAGE else 1

    payload = {
        "text": text_en,
        "voice_id": int(TTS_VOICE_ID),
        "language": language_id,
        "project_name": "Bible English Shorts",
        "project_description": "Automated Bible verse English voiceover",
        "folder_id": 0,
        "gender": 0,
        "age": "adult",
    }
    print(f"TTS payload being sent: {payload}")
    return payload


def call_tts_api(text_en: str) -> bytes:
    if not TTS_API_KEY or not TTS_API_URL:
        print("TTS_API_KEY or TTS_API_URL not set in environment.", file=sys.stderr)
        sys.exit(1)

    headers = {
        "Content-Type": "application/json",
        "x-api-key": TTS_API_KEY,
    }

    payload = build_tts_payload(text_en)
    print(f"Calling TTS API at: {TTS_API_URL}")

    try:
        resp = requests.post(TTS_API_URL, headers=headers, json=payload, timeout=60)
    except requests.RequestException as e:
        print(f"Error calling TTS API: {e}", file=sys.stderr)
        sys.exit(1)

    if resp.status_code != 200:
        print(f"TTS API error {resp.status_code}: {resp.text}", file=sys.stderr)
        sys.exit(1)

    # For now, assume CAMB returns raw audio bytes or a direct audio file;
    # if they return JSON with URL, we can extend this later.
    content_type = resp.headers.get("Content-Type", "")
    if "application/json" in content_type.lower():
        data = resp.json()
        audio_url = data.get("audio_url") or data.get("url")
        if not audio_url:
            print("No audio URL found in TTS JSON response.", file=sys.stderr)
            sys.exit(1)
        try:
            audio_resp = requests.get(audio_url, timeout=60)
        except requests.RequestException as e:
            print(f"Error downloading audio file: {e}", file=sys.stderr)
            sys.exit(1)
        if audio_resp.status_code != 200:
            print(f"Error downloading audio: {audio_resp.status_code}", file=sys.stderr)
            sys.exit(1)
        return audio_resp.content

    return resp.content


def main():
    data = load_current_verse()
    reference = data.get("reference")
    summary_en = data.get("summary_en")

    if not reference:
        print("current_verse.json must contain 'reference'.", file=sys.stderr)
        sys.exit(1)
    if not summary_en:
        print("current_verse.json must contain 'summary_en' (English text).", file=sys.stderr)
        sys.exit(1)

    audio_bytes = call_tts_api(summary_en)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    safe_ref = reference.replace(" ", "_").replace(":", "-")
    out_path = OUTPUT_DIR / f"{safe_ref}.mp3"

    with open(out_path, "wb") as f:
        f.write(audio_bytes)

    print(f"Saved TTS audio to {out_path}")

    data["audio_path"] = str(out_path)
    save_current_verse(data)
    print("Updated current_verse.json with audio_path.")


if __name__ == "__main__":
    main()
