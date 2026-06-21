"""
Combined ship/no-ship verdict.

build_verdict(run_id, db) aggregates the three independent fail-closed
signals already computed by Steps 4-6 (judge score, moderation, locale
checks) into a single can_ship boolean.

This function only READS existing data — it never triggers judge(),
moderate(), or locale checks itself. moderate() already runs automatically
at generation time (Step 5), but judge() and locale checks require explicit
calls to POST /v1/evaluate/{prompt_id} and POST /v1/evaluate-locale/{prompt_id}
first. If a run hasn't been evaluated yet (score=NULL) or had locale checks
run (no LocaleCheck rows), can_ship is False — unevaluated is not safe to
ship, matching the fail-closed pattern used everywhere else in this system.

Reads raw rows directly (Run.score, Run.blocked, LocaleCheck rows) rather
than any pre-aggregated summary field — none exists in the schema, by design,
so there is no cached value that could have silently absorbed a dilution bug
like the ones found and fixed in judge() (Step 4) and the locale checker
(Step 6).
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import LocaleCheck, Run

SCORE_THRESHOLD = 4.0


def build_verdict(run_id: uuid.UUID, db: Session) -> dict:
    run = db.get(Run, run_id)
    if run is None:
        raise ValueError(f"Run {run_id} not found")

    locale_checks = (
        db.execute(select(LocaleCheck).where(LocaleCheck.run_id == run_id))
        .scalars()
        .all()
    )

    reasons: list[str] = []

    if run.score is None:
        reasons.append("not yet evaluated by judge (score is NULL)")
    elif run.score < SCORE_THRESHOLD:
        reasons.append(f"eval score {run.score} below threshold {SCORE_THRESHOLD}")

    if run.blocked:
        reasons.append(f"blocked by moderation: {run.block_reason}")

    if not locale_checks:
        reasons.append("no locale checks have been run for this run")
    else:
        failed = [c for c in locale_checks if not c.passed]
        if failed:
            details = "; ".join(f"{c.check_type}: {c.details}" for c in failed)
            reasons.append(f"locale check(s) failed: {details}")

    can_ship = len(reasons) == 0

    return {
        "run_id": run.id,
        "eval_score": run.score,
        "blocked": run.blocked,
        "block_reason": run.block_reason,
        "locale_results": [
            {"check_type": c.check_type, "passed": c.passed, "details": c.details}
            for c in locale_checks
        ],
        "can_ship": can_ship,
        "reasons": reasons,
    }
