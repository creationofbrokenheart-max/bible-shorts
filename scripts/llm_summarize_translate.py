import json
import os
from pathlib import Path

import requests

CURRENT_VERSE_PATH = Path("current_verse.json")

# Groq primary
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")

# OpenRouter fallback
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "deepseek/deepseek-r1")


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


def build_prompt(verse_ref: str, verse_text: str) -> str:
    return f"""
You are helping create a 30–60 second YouTube Short based on a Bible verse.

Verse reference: {verse_ref}
Verse text: {verse_text}

Tasks:
1) Write ONE short-sentence summary in simple English, max 22 words, directly encouraging the viewer (use “you”, not “we”).
2) Translate ONLY that summary into Telugu.
3) Create a short Telugu title (max 20 characters) that fits as a YouTube Short title.

Respond ONLY in strict JSON, no markdown, no extra text, with keys:
- "summary_en"
- "summary_te"
- "title_te"
""".strip()


def strip_code_fences(text: str) -> str:
    t = text.strip()
    if t.startswith("```"):
        lines = t.splitlines()
        if lines:
            lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        t = "\n".join(lines).strip()
    return t


def parse_json_from_content(content: str) -> dict:
    t = strip_code_fences(content)
    try:
        return json.loads(t)
    except json.JSONDecodeError as e:
        raise ValueError(f"Failed to parse JSON from model response: {e}\nRaw content:\n{t}") from e


def call_groq(prompt: str) -> dict:
    if not GROQ_API_KEY:
        raise RuntimeError("GROQ_API_KEY is not set.")

    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json",
    }

    body = {
        "model": GROQ_MODEL,
        "messages": [
            {
                "role": "system",
                "content": "You are a helpful assistant for creating Bible video shorts.",
            },
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.7,
    }

    resp = requests.post(GROQ_URL, headers=headers, json=body, timeout=60)
    if resp.status_code == 402:
        # Payment / quota issue: let caller decide to fall back
        raise RuntimeError(f"GROQ 402/Payment error: {resp.text}")
    resp.raise_for_status()
    data = resp.json()

    content = data["choices"][0]["message"]["content"]
    return parse_json_from_content(content)


def call_openrouter(prompt: str) -> dict:
    if not OPENROUTER_API_KEY:
        raise RuntimeError("OPENROUTER_API_KEY is not set (fallback unavailable).")

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
    }

    body = {
        "model": OPENROUTER_MODEL,
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
    if resp.status_code == 402:
        raise RuntimeError(f"OpenRouter 402/Payment error: {resp.text}")
    resp.raise_for_status()
    data = resp.json()

    content = data["choices"][0]["message"]["content"]
    # Handle potential list content from some providers
    if isinstance(content, list):
        chunks = []
        for c in content:
            if isinstance(c, dict) and "text" in c:
                chunks.append(c["text"])
            elif isinstance(c, str):
                chunks.append(c)
        content = "\n".join(chunks)

    return parse_json_from_content(content)


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

    # Try Groq first, then fall back to OpenRouter if Groq fails
    try:
        print("Calling Groq LLM...")
        result = call_groq(prompt)
    except Exception as e:
        print(f"Groq call failed or quota exceeded: {e}")
        print("Attempting OpenRouter fallback...")
        result = call_openrouter(prompt)

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
