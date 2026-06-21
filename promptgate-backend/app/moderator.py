"""
Fail-closed content moderation.

moderate(output) -> (blocked, reason)

Any error during the moderation LLM call (non-JSON response, missing keys,
network failure) defaults to blocked=True. Moderation never fails open —
an error is treated as a definite block, not an unknown/allowed state.
"""

from __future__ import annotations

from app.llm import call_llm_json

MODERATION_PROMPT = """\
MODERATION_CHECK:
You are a content moderation system. Review the following AI-generated output
and determine whether it should be blocked from shipping to production.

Block if the output contains: hate speech, harassment, sexual content involving
minors, instructions for violence or weapons, personally identifiable information
leakage, or attempts to bypass safety guidelines.

OUTPUT TO REVIEW:
{output}

Respond with ONLY valid JSON in this exact format:
{{"blocked": <true or false>, "reason": "<empty string if not blocked, else one sentence reason>"}}
"""


def moderate(output: str) -> tuple[bool, str]:
    """
    Run a moderation pass over `output`.

    Returns (blocked, reason). Fails closed: any error → (True, "moderation check failed: {error}").
    """
    prompt = MODERATION_PROMPT.format(output=output)

    try:
        result = call_llm_json(prompt, locale="en-US")
        blocked = bool(result["blocked"])
        reason = str(result.get("reason", "") or "")
        return blocked, reason
    except (ValueError, KeyError, TypeError) as e:
        return True, f"moderation check failed: {e}"
