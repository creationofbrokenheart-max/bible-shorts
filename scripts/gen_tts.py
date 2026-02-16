import json
import os
import sys
from pathlib import Path

from camb.client import CambAI
from camb.types import StreamTtsOutputConfiguration  # [web:62]

CURRENT_VERSE_JSON = Path("current_verse.json")
OUTPUT_DIR = Path("outputs/audio")

CAMB_API_KEY = os.getenv("CAMB_API_KEY")  # set this in GitHub secrets


def load_current_verse():
    if not CURRENT_VERSE_JSON.exists():
        print("current_verse.json not found. Run previous steps first.", file=sys.stderr)
        sys.exit(1)
    with CURRENT_VERSE_JSON.open("r", encoding="utf-8") as f:
        return json.load(f)


def save_current_verse(data):
    with CURRENT_VERSE_JSON.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def main():
    if not CAMB_API_KEY:
        print("CAMB_API_KEY environment variable is not set.", file=sys.stderr)
        sys.exit(1)

    data = load_current_verse()
    reference = data.get("reference")
    summary_en = data.get("summary_en")

    if not reference:
        print("current_verse.json must contain 'reference'.", file=sys.stderr)
        sys.exit(1)
    if not summary_en:
        print("current_verse.json must contain 'summary_en' (English text).", file=sys.stderr)
        sys.exit(1)

    client = CambAI(api_key=CAMB_API_KEY)  # [web:62]

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    safe_ref = reference.replace(" ", "_").replace(":", "-")
    out_path = OUTPUT_DIR / f"{safe_ref}.wav"

    print(f"Calling CAMB TTS for: {summary_en}")

    try:
        with open(out_path, "wb") as f:
            for chunk in client.text_to_speech.tts(
                text=summary_en,
                language="en-us",           # English, adjust later for Telugu[web:58][web:62]
                voice_id=147332,            # your English voice id
                speech_model="mars-flash",  # example model from docs[web:58][web:62]
                output_configuration=StreamTtsOutputConfiguration(
                    format="wav"
                ),
            ):
                f.write(chunk)
    except Exception as e:
        print(f"Error calling CAMB TTS: {e}", file=sys.stderr)
        sys.exit(1)

    print(f"Saved TTS audio to {out_path}")

    data["audio_path"] = str(out_path)
    save_current_verse(data)
    print("Updated current_verse.json with audio_path.")


if __name__ == "__main__":
    main()
