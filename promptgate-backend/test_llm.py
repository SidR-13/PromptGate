"""
Manual CLI test for call_llm.

Run with:
    AI_MOCK=true python test_llm.py
    AI_MOCK=false python test_llm.py   # requires ANTHROPIC_API_KEY
"""

import os
import sys

# Allow running from repo root
sys.path.insert(0, os.path.dirname(__file__))

# Force UTF-8 output on Windows
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from app.llm import call_llm, call_llm_json

LOCALES = ["en-US", "ar-SA", "ja-JP", "de-DE", "fr-FR"]

TEST_PROMPT = (
    "Tell me the date of a fictional upcoming team meeting and the cost "
    "of the catering budget. Use locale-appropriate date and number formatting."
)


def main() -> None:
    ai_mock = os.environ.get("AI_MOCK", "true").lower() in ("true", "1", "yes")
    mode = "MOCK" if ai_mock else "REAL API"
    print(f"\n=== PromptGate — call_llm test [{mode}] ===\n")

    for locale in LOCALES:
        print(f"--- Locale: {locale} ---")
        response = call_llm(TEST_PROMPT, locale=locale)
        print(response)
        print()

    print("--- call_llm_json (en-US) ---")
    json_prompt = (
        'Respond ONLY with valid JSON: {"score": 4, "reasoning": "looks good"}'
    )
    result = call_llm_json(json_prompt, locale="en-US")
    print(result)
    print()

    print("All tests passed.")


if __name__ == "__main__":
    main()
