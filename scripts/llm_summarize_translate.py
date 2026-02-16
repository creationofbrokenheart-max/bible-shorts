import json
import os
import sys
from pathlib import Path

from openai import OpenAI  # OpenAI-compatible client

CURRENT_VERSE_JSON = Path("current_verse.json")

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_BASE_URL = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
# DeepSeek model on OpenRouter[web:130]
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek/deepseek-chat")


def load_current_verse():
    if not CURRENT_VERSE_JSON.exists():
        print("current_verse.json not found. Run previous steps first.", file=sys.stderr)
        sys.exit(1)
    with CURRENT_VERSE_JSON.open("r", encoding="utf-8") as f:
        return json.load(f)


def save_current_verse(data):
    with CURRENT_VERSE_JSON.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def build_prompt(verse_en: str, reference: str) -> str:
    return f"""
You are helping create YouTube Shorts for Telugu Christian teenagers.

I will give you a Bible verse in English and its reference.

1) First, write ONE short English summary sentence that explains the meaning in very simple language for a teenager in India.
   - No old-fashioned words.
   - Max 25 words.

2) Then write ONE short Telugu explanation sentence that encourages them in daily life.
   - Use simple, modern Telugu.
   - Max 25 words.

3) Then give ONE very short Telugu title (3–6 words) that can be used as a YouTube video title.

Format your answer as strict JSON with these fields only:
{{
  "summary_en": "...",
  "summary_te": "...",
  "title_te": "..."
}}

Bible reference: {reference}
Verse (English): {verse_en}
""".strip()


def call_deepseek_via_openrouter(prompt: str) -> dict:
    if not OPENROUTER_API_KEY:
        print("OPENROUTER_API_KEY environment variable is not set.", file=sys.stderr)
        sys.exit(1)

    client = OpenAI(
        base_url=OPENROUTER_BASE_URL,
        api_key=OPENROUTER_API_KEY,
    )

    try:
        completion = client.chat.completions.create(
            model=DEEPSEEK_MODEL,
            messages=[
                {"role": "system", "content": "You are a helpful assistant for Christian teen content creation."},
                {"role": "user", "content": prompt},
            ],
            max_tokens=400,
            temperature=0.4,
        )
    except Exception as e:
        print(f"Error calling DeepSeek via OpenRouter: {e}", file=sys.stderr)
        sys.exit(1)

    content = completion.choices[0].message.content

    # Strip Markdown fences if present (```json ... ```)
    content_stripped = content.strip()
    if content_stripped.startswith("```"):
        lines = content_stripped.splitlines()
        # drop first line if it's ``` or ```json
        if lines and lines.strip().startswith("```"):
            lines = lines[1:]
        # drop last line if it's ```
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        content_stripped = "\n".join(lines).strip()

    try:
        data = json.loads(content_stripped)
    except json.JSONDecodeError:
        print("Failed to parse LLM response as JSON. Raw content:", file=sys.stderr)
        print(content, file=sys.stderr)
        sys.exit(1)

    if not isinstance(data, dict):
        print("LLM JSON root is not an object. Got:", type(data), file=sys.stderr)
        sys.exit(1)

    required_keys = {"summary_en", "summary_te", "title_te"}
    if not required_keys.issubset(data.keys()):
        print("LLM JSON missing required keys. Got keys:", list(data.keys()), file=sys.stderr)
        sys.exit(1)

    return data


def main():
    current = load_current_verse()

    verse_en = current.get("verse_en")
    reference = current.get("reference")

    if not verse_en or not reference:
        print("current_verse.json must contain 'verse_en' and 'reference'.", file=sys.stderr)
        sys.exit(1)

    prompt = build_prompt(verse_en=verse_en, reference=reference)
    result = call_deepseek_via_openrouter(prompt)

    current["summary_en"] = result["summary_en"]
    current["summary_te"] = result["summary_te"]
    current["title_te"] = result["title_te"]

    save_current_verse(current)

    print("Updated current_verse.json with summary_en, summary_te, title_te.")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
