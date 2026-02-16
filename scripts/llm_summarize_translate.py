import json
import os
from pathlib import Path
import requests

CURRENT_VERSE_PATH = Path("current_verse.json")

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
MODEL = "deepseek/deepseek-r1"


def load_current_verse():
    if not CURRENT_VERSE_PATH.exists():
        raise FileNotFoundError(
            f"{CURRENT_VERSE_PATH} not found. Run select_verse.py and fetch_verse_text.py first."
        )
    with CURRENT_VERSE_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)


def save_current_verse(data: dict):
    with CURRENT_VERSE_PATH.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def strip_code_fence(content):
    """
    Accept either a string or a list and remove leading/trailing ``` fences.
    """
    # Normalize list -> string
    if isinstance(content, list):
        content = "\n".join(str(x) for x in content)

    if not isinstance(content, str):
        return str(content)

    text = content.strip()

    if text.startswith("```"):
        lines = text.splitlines()

        # drop first line (``` or ```json)
        if lines:
            lines = lines[1:]

        # drop last line if it looks like ```
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]

        return "\n".join(lines).strip()

    return text


def build_prompt(verse_ref: str, verse_text: str) -> str:
    return f"""
You are helping create a 30–60 second Bible short.

Given this verse:

Reference: {verse_ref}
Verse: {verse_text}

1) Write ONE short-sentence summary in simple English, max 22 words, directly encouraging the viewer (use “you”, not “we”).
2) Translate ONLY that summary into Telugu.
3) Create a short Telugu title (max 20 characters) that fits as a YouTube Short title.

Respond ONLY in strict JSON with keys:
- "summary_en"
- "summary_te"
- "title_te"
""".strip()


def call_deepseek_via_openrouter(prompt: str) -> dict:
    if not OPENROUTER_API_KEY:
        raise RuntimeError("OPENROUTER_API_KEY is not set.")

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
    }

    body = {
        "model": MODEL,
        "messages": [
            {
                "role": "system",
                "content": "You are a helpful assistant for creating Bible video shorts.",
            },
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.7,
    }

    resp = requests.post(OPENROUTER_URL, headers=headers, json=body, timeout=120)
    resp.raise_for_status()
    data = resp.json()

    choices = data.get("choices") or []
    if not choices:
        raise ValueError(f"No choices in OpenRouter response: {data}")

    first = choices[0]

    # Standard OpenRouter / OpenAI-like shape: {"message": {...}}
    if isinstance(first, dict) and "message" in first:
        message_obj = first["message"]
    # Fallback: if somehow it's nested as a list of dicts
    elif isinstance(first, list) and first and isinstance(first[0], dict) and "message" in first[0]:
        message_obj = first[0]["message"]
    else:
        # Last resort: treat first as the content itself
        content_stripped = strip_code_fence(first)
        return json.loads(content_stripped)

    content = message_obj.get("content")

    # If content is a list of chunks, normalize to a string
    if isinstance(content, list):
        chunks = []
        for c in content:
            if isinstance(c, dict) and "text" in c:
                chunks.append(c["text"])
            elif isinstance(c, str):
                chunks.append(c)
        content = "\n".join(chunks)

    content_stripped = strip_code_fence(content)

    try:
        parsed = json.loads(content_stripped)
    except json.JSONDecodeError as e:
        raise ValueError(
            f"Failed to parse JSON from model response: {e}\nRaw content:\n{content_stripped}"
        ) from e

    return parsed


def main():
    data = load_current_verse()

    verse_ref = data.get("verse_ref") or data.get("reference") or data.get("verse_reference")
    verse_en = data.get("verse_en") or data.get("verse_text")

    if not verse_ref or not verse_en:
        raise ValueError(
            "current_verse.json must contain 'verse_ref' (or similar) and 'verse_en'."
        )

    print(f"Summarizing and translating verse: {verse_ref}")
    prompt = build_prompt(verse_ref, verse_en)
    result = call_deepseek_via_openrouter(prompt)

    summary_en = result.get("summary_en")
    summary_te = result.get("summary_te")
    title_te = result.get("title_te")

    if not summary_en or not summary_te or not title_te:
        raise ValueError(f"Missing keys in model result: {result}")

    data["summary_en"] = summary_en
    data["summary_te"] = summary_te
    data["title_te"] = title_te

    save_current_verse(data)

    print("Updated current_verse.json with summary_en, summary_te, title_te.")
    print(
        json.dumps(
            {
                "summary_en": summary_en,
                "summary_te": summary_te,
                "title_te": title_te,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
