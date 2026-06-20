"""
Manual CLI test for call_llm.

Run with:
    AI_MOCK=true python test_llm.py
    AI_MOCK=false python test_llm.py   # requires ANTHROPIC_API_KEY
"""

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from app.llm import call_llm, call_llm_json

LOCALES = ["en-US", "ar-SA", "ja-JP", "de-DE", "fr-FR"]

TEST_PROMPT = (
    "Tell me the date of a fictional upcoming team meeting and the cost "
    "of the catering budget. Use locale-appropriate date and number formatting."
)

# Deliberate defects in mock data — confirms Step 6 checker has real failures to catch:
#   ar-SA: no RTL control characters → RTL check should FAIL
#   ja-JP: Western date "June 20" + Western decimal "1234.56" → date/number checks should FAIL
EXPECTED_DEFECTS = {
    "ar-SA": "no RTL control chars (\u202B/\u200F) — Step 6 RTL check should flag this",
    "ja-JP": "Western date format and decimal separator — Step 6 date/number checks should flag this",
}


def main() -> None:
    ai_mock = os.environ.get("AI_MOCK", "true").lower() in ("true", "1", "yes")
    mode = "MOCK" if ai_mock else "REAL API"
    print(f"\n=== PromptGate — call_llm test [{mode}] ===\n")

    for locale in LOCALES:
        print(f"--- Locale: {locale} ---")
        response = call_llm(TEST_PROMPT, locale=locale)
        print(response)
        if locale in EXPECTED_DEFECTS:
            print(f"  [intentional defect: {EXPECTED_DEFECTS[locale]}]")
        print()

    # call_llm_json: valid JSON path (uses a hardcoded mock that returns JSON-shaped text)
    print("--- call_llm_json: valid JSON mock ---")
    # In mock mode the LLM returns text, not JSON, so we test the JSON path
    # directly by monkey-patching call_llm temporarily
    import app.llm as llm_module
    original = llm_module._mock_response

    llm_module._mock_response = lambda prompt, locale: '{"score": 4, "reasoning": "looks good"}'
    result = call_llm_json("any prompt", locale="en-US")
    assert result == {"score": 4, "reasoning": "looks good"}, f"Unexpected: {result}"
    print(f"  Parsed correctly: {result}")

    # call_llm_json: invalid JSON path must raise, not silently return
    print("--- call_llm_json: non-JSON raises ValueError ---")
    llm_module._mock_response = lambda prompt, locale: "not json garbage"
    try:
        call_llm_json("any prompt", locale="en-US")
        raise AssertionError("Expected ValueError — got nothing")
    except ValueError as e:
        print(f"  Raised ValueError as expected: {e}")

    llm_module._mock_response = original
    print()
    print("All tests passed.")


if __name__ == "__main__":
    main()
