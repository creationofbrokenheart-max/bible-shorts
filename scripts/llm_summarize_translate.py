import json
import os
import sys
from pathlib import Path

from huggingface_hub import InferenceClient  # [web:22][web:24][web:110]

CURRENT_VERSE_JSON = Path("current_verse.json")

HF_TOKEN = os.getenv("HF_TOKEN")
# Standard HF model id (you can change via env HF_MODEL if you like).[web:110]
HF_MODEL = os.getenv("HF_MODEL", "meta-llama/Llama-3.1-8B-Instruct")


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


def call_hf_llm(prompt: str) -> dict:
    if not HF_TOKEN:
        print("HF_TOKEN environment variable is not set.", file=sys.stderr)
        sys.exit(1)

    client = InferenceClient(
        model=HF_MODEL,
        token=HF_TOKEN,
    )  # uses HF Inference API, not router[web:22][web:24][web:110]

    try:
        completion = client.chat_completion(
            messages=[
                {"role": "system", "content": "You are a helpful assistant for Christian teen content creation."},
                {"role": "user", "content": prompt},
            ],
            max_tokens=400,
            temperature=0.4,
        )
    except Exception as e:
        print(f"Error calling Hugging Face LLM: {e}", file=sys.stderr)
        sys.exit(1)

    content = completion.choices[0].message["content"]

    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        print("Failed to parse LLM response as JSON. Raw content:", file=sys.stderr)
        print(content, file=sys.stderr)
        sys.exit(1)

    required_keys = {"summary_en", "summary_te", "title_te"}
    if not required_keys.issubset(data.keys()):
        print("LLM JSON missing required keys. Got:", data.keys(), file=sys.stderr)
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
    result = call_hf_llm(prompt)

    current["summary_en"] = result["summary_en"]
    current["summary_te"] = result["summary_te"]
    current["title_te"] = result["title_te"]

    save_current_verse(current)

    print("Updated current_verse.json with summary_en, summary_te, title_te.")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
