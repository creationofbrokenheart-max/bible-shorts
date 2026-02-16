import json
import os
import sys
from pathlib import Path

import requests

CURRENT_VERSE_JSON = Path("current_verse.json")
OUTPUT_DIR = Path("outputs/audio")

# Generic TTS settings – customize for your provider.
# Example: for CAMB.AI or ElevenLabs, set these in GitHub Secrets / env.[web:17][web:20][web:63][web:64]
TTS_API_KEY = os.getenv("TTS_API_KEY")
TTS_API_URL = os.getenv("TTS_API_URL")  # e.g. https://client.camb.ai/apis/tts or your chosen TTS endpoint
TTS_VOICE_ID = os.getenv("TTS_VOICE_ID", "")  # optional, depending on provider


def load_current_verse():
    if not CURRENT_VERSE_JSON.exists():
        print("current_verse.json not found. Run previous steps first.", file=sys.stderr)
        sys.exit(1)
    with CURRENT_VERSE_JSON.open("r", encoding="utf-8") as f:
        return json.load(f)


def save_current_verse(data):
    with CURRENT_VERSE_JSON.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def build_tts_payload(text_te: str) -> dict:
    # Example CAMB.AI style – adjust keys as per their API docs.[web:58][web:60][web:99]
    payload = {
        "input": text_te,          # or "text": text_te
        "source_language": "te",   # Telugu code if required
        # "target_language": "te", # if using translated-tts endpoint
    }
    if TTS_VOICE_ID:
        payload["voice_id"] = TTS_VOICE_ID
    return payload



def call_tts_api(text_te: str) -> bytes:
    if not TTS_API_KEY or not TTS_API_URL:
        print("TTS_API_KEY or TTS_API_URL not set in environment.", file=sys.stderr)
        sys.exit(1)

    headers = {
        "Content-Type": "application/json",
        # Many providers use `x-api-key` or `Authorization: Bearer`.[web:58][web:60][web:61][web:64]
        "x-api-key": TTS_API_KEY,
    }

    payload = build_tts_payload(text_te)
    print(f"Calling TTS API at: {TTS_API_URL}")

    try:
        resp = requests.post(TTS_API_URL, headers=headers, json=payload, timeout=60)
    except requests.RequestException as e:
        print(f"Error calling TTS API: {e}", file=sys.stderr)
        sys.exit(1)

    if resp.status_code != 200:
        print(f"TTS API error {resp.status_code}: {resp.text}", file=sys.stderr)
        sys.exit(1)

    # Some APIs return audio bytes directly;
    # others return JSON with a URL to download.[web:58][web:60][web:63][web:64]
    content_type = resp.headers.get("Content-Type", "")
    if "application/json" in content_type.lower():
        data = resp.json()
        # Example: handle a `audio_url` field and download it
        audio_url = data.get("audio_url"
