"""
LLM-as-judge evaluation against golden test cases.

judge(run_id, db) scores a run's output 1.0–5.0 against every golden set
entry for its prompt. Returns the mean score across all cases.

On any failure (non-JSON response, missing keys, network error):
  score = 0.0, judge_reasoning = "judge call failed: {error}"
This keeps score=NULL meaning "not yet evaluated" — never a failure state.
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.llm import call_llm_json
from app.models import GoldenSet, Run

JUDGE_PROMPT = """\
You are an expert evaluator assessing the quality of an AI assistant's response.

PROMPT TEMPLATE:
{template}

TEST INPUT:
{input}

LOCALE: {locale}
The response above was generated for a customer in this locale. It is expected
to be in the appropriate language for this locale (e.g. German for de-DE,
Japanese for ja-JP, Arabic for ar-SA). Evaluate the response as if you are a
fluent speaker of that locale's language. Do not penalise the response for not
being in English.

EXPECTED BEHAVIOR:
{expected_behavior}

ACTUAL OUTPUT:
{output}

Score the actual output on a scale of 1 to 5:
  5 = Fully meets the expected behavior, no issues
  4 = Mostly meets expected behavior, minor gaps
  3 = Partially meets expected behavior, notable gaps
  2 = Falls short of expected behavior significantly
  1 = Does not meet expected behavior at all

Respond with ONLY valid JSON in this exact format:
{{"score": <number 1-5>, "reasoning": "<one sentence explanation>"}}
"""


def _judge_single(
    template: str,
    input_text: str,
    expected_behavior: str,
    output: str,
    locale: str = "en-US",
) -> tuple[float, str]:
    """
    Judge a single (input, expected_behavior, output) triple.
    Returns (score, reasoning). On failure returns (0.0, error message).
    """
    # The judge runs in the same locale as the run being evaluated.
    # Without this, the judge (an English-biased LLM) consistently scores
    # non-English responses 2.0 regardless of quality — it reads German/
    # Japanese/Arabic output against an English prompt template and penalises
    # the language difference instead of evaluating content quality. Passing
    # the locale and an explicit instruction to evaluate as a native speaker
    # corrects this bias.
    prompt = JUDGE_PROMPT.format(
        template=template,
        input=input_text,
        locale=locale,
        expected_behavior=expected_behavior,
        output=output,
    )

    try:
        result = call_llm_json(prompt, locale=locale)
        score = float(result["score"])
        reasoning = str(result["reasoning"])
        # Clamp to valid range in case the LLM drifts
        score = max(1.0, min(5.0, score))
        return score, reasoning
    except (ValueError, KeyError, TypeError) as e:
        return 0.0, f"judge call failed: {e}"


def judge(run_id: uuid.UUID, db: Session) -> tuple[float, str]:
    """
    Score a run against all golden set entries for its prompt.

    Returns (mean_score, combined_reasoning).
    If there are no golden set entries, returns (0.0, "no golden set entries").
    If every individual case fails, the mean is 0.0.
    """
    run = db.get(Run, run_id)
    if run is None:
        raise ValueError(f"Run {run_id} not found")

    # Filter golden entries to those matching the run's actual input.
    # Without this filter, every run would be evaluated against every golden
    # entry for the prompt regardless of topic or locale, causing
    # cross-contamination: a French "refund" response scored against an
    # English "order tracking" entry always produces a low score unrelated
    # to quality. Golden entries are per-scenario, not per-prompt.
    golden_entries = (
        db.execute(
            select(GoldenSet)
            .where(GoldenSet.prompt_id == run.prompt_id)
            .where(GoldenSet.input == run.input)
        )
        .scalars()
        .all()
    )

    if not golden_entries:
        score = 0.0
        reasoning = "no golden set entries — cannot evaluate"
        _write_score(run, score, reasoning, db)
        return score, reasoning

    scores: list[float] = []
    reasonings: list[str] = []

    for entry in golden_entries:
        template = run.prompt.template if run.prompt else ""
        s, r = _judge_single(
            template=template,
            input_text=entry.input,
            expected_behavior=entry.expected_behavior,
            output=run.output,
            locale=run.locale,
        )
        scores.append(s)
        reasonings.append(f"[case {entry.id}] {r}")

    # _judge_single clamps legitimate scores to [1.0, 5.0]; 0.0 is only ever
    # produced by its except branch (a judge call failure). Fail-closed,
    # matching moderate(): a single failed judge call poisons the whole run's
    # score rather than being averaged away by other golden entries' good
    # scores. A failure is missing data, not a low-quality signal — it must
    # never be diluted into a passing mean.
    if any(s == 0.0 for s in scores):
        final_score = 0.0
    else:
        final_score = sum(scores) / len(scores)

    combined_reasoning = " | ".join(reasonings)

    _write_score(run, final_score, combined_reasoning, db)
    return final_score, combined_reasoning


def _write_score(run: Run, score: float, reasoning: str, db: Session) -> None:
    run.score = score
    run.judge_reasoning = reasoning
    db.commit()
