import json
import os
import sys
from pathlib import Path
from urllib.parse import quote

import requests

# Paths (relative to repo root)
CURRENT_VERSE_JSON = Path("current_verse.json")

# You can change this base URL if you prefer another free Bible API.
BIBLE_API_BASE = os.getenv("BIBLE_API_BASE", "https://bible-api.com")  # [web:14][web:16]


def load_current_verse():
    if not CURRENT_VERSE_JSON.exists():
        print("current_verse.json not found. Run select_verse.py first.", file=sys.stderr)
        sys.exit(1)
    with CURRENT_VERSE_JSON.open("r", encoding="utf-8") as f:
        return json.load(f)


def save_current_verse(data):
    with CURRENT_VERSE_JSON.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def fetch_verse_text(reference: str) -> str:
    """
    Fetch verse text from Bible API using a reference string like
    'John 3:16' or 'Book of Ruth 4:12'.
    """
    # Basic normalization: remove 'Book of ' prefix if present
    ref_norm = reference.replace("Book of ", "").strip()

    # URL-encode the reference for the API call
    url = f"{BIBLE_API_BASE}/{quote(ref_norm)}"
    print(f"Fetching verse from: {url}")

    try:
        resp = requests.get(url, timeout=10)
    except requests.RequestException as e:
        print(f"Error calling Bible API: {e}", file=sys.stderr)
        sys.exit(1)

    if resp.status_code != 200:
        print(f"Bible API error: HTTP {resp.status_code} - {resp.text}", file=sys.stderr)
        sys.exit(1)

    data = resp.json()

    # bible-api.com returns 'text' as the verse text field.[web:14]
    verse_text = data.get("text")
    if not verse_text:
        print("Verse text not found in API response.", file=sys.stderr)
        sys.exit(1)

    return verse_text.strip()


def main():
    current = load_current_verse()
    reference = current.get("reference")

    if not reference:
        print("No 'reference' field in current_verse.json.", file=sys.stderr)
        sys.exit(1)

    verse_text = fetch_verse_text(reference)
    print(f"Fetched verse text for '{reference}':\n{verse_text}\n")

    # Merge into current_verse.json
    current["verse_en"] = verse_text
    save_current_verse(current)
    print("Updated current_verse.json with verse_en.")


if __name__ == "__main__":
    main()
