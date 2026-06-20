"""
LLM call abstraction with mock support.

AI_MOCK=true  → returns deterministic canned responses (all development)
AI_MOCK=false → calls Claude API (final e2e testing only, max 20 calls)
"""

import os
import json
import hashlib
from typing import Optional

MOCK_RESPONSES: dict[str, str] = {
    "default": (
        "This is a mock LLM response. Set AI_MOCK=false to call the real Claude API. "
        "The response would normally contain the AI-generated text for your prompt."
    ),
    "en-US": (
        "The meeting is scheduled for June 20, 2026 at 2:30 PM. "
        "The total cost is $1,234.56."
    ),
    "ar-SA": (
        "الاجتماع مقرر في 20 يونيو 2026 الساعة 2:30 مساءً. "
        "التكلفة الإجمالية هي 1.234,56 ر.س."
    ),
    "ja-JP": (
        "会議は2026年6月20日午後2時30分に予定されています。"
        "合計費用は¥1,234,560です。"
    ),
    "de-DE": (
        "Das Meeting ist für den 20. Juni 2026 um 14:30 Uhr geplant. "
        "Die Gesamtkosten betragen 1.234,56 €."
    ),
    "fr-FR": (
        "La réunion est prévue le 20 juin 2026 à 14h30. "
        "Le coût total est de 1 234,56 €."
    ),
}


def _mock_response(prompt: str, locale: str) -> str:
    """Return a deterministic mock response based on locale."""
    return MOCK_RESPONSES.get(locale, MOCK_RESPONSES["default"])


def _real_response(prompt: str, locale: str, model: Optional[str] = None) -> str:
    """Call the real Claude API. Only used for final e2e testing."""
    import anthropic

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise EnvironmentError("ANTHROPIC_API_KEY is not set")

    model = model or os.environ.get("CLAUDE_MODEL", "claude-haiku-4-5")

    system_prompt = (
        f"You are a helpful assistant. Respond in the locale/language appropriate for: {locale}. "
        "Format dates and numbers according to the locale conventions."
    )

    client = anthropic.Anthropic(api_key=api_key)
    response = client.messages.create(
        model=model,
        max_tokens=1024,
        system=system_prompt,
        messages=[{"role": "user", "content": prompt}],
    )

    for block in response.content:
        if block.type == "text":
            return block.text

    return ""


def call_llm(prompt: str, locale: str = "en-US") -> str:
    """
    Call the LLM with a prompt and locale context.

    Returns the text response. Uses mock when AI_MOCK=true.
    """
    ai_mock = os.environ.get("AI_MOCK", "true").lower() in ("true", "1", "yes")

    if ai_mock:
        return _mock_response(prompt, locale)
    else:
        return _real_response(prompt, locale)


def call_llm_json(prompt: str, locale: str = "en-US") -> dict:
    """
    Call the LLM expecting a JSON response.

    Wraps call_llm and parses the result. Used by evaluator and moderator.
    """
    raw = call_llm(prompt, locale)

    # Strip markdown code fences if present
    if "```json" in raw:
        raw = raw.split("```json")[1].split("```")[0].strip()
    elif "```" in raw:
        raw = raw.split("```")[1].split("```")[0].strip()

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        # Return raw text under a key so callers can handle gracefully
        return {"raw_text": raw, "parse_error": True}
