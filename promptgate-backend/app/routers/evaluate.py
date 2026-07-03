import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.evaluator import judge
from app.models import Run

router = APIRouter()


class EvaluateResponse(BaseModel):
    run_id: uuid.UUID
    prompt_id: uuid.UUID
    score: float
    passed: bool
    judge_reasoning: str


class BatchEvaluateResponse(BaseModel):
    prompt_id: uuid.UUID
    runs_evaluated: int
    mean_score: float
    passed: bool
    results: list[EvaluateResponse]


@router.post("/evaluate/run/{run_id}", response_model=EvaluateResponse)
def evaluate_single_run(run_id: uuid.UUID, db: Session = Depends(get_db)) -> EvaluateResponse:
    """
    Run LLM-as-judge for a single run only.
    Scores the run against all golden set entries for its prompt and writes
    score + judge_reasoning back to that run. Does not touch other runs.
    """
    run = db.get(Run, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found")

    score, reasoning = judge(run.id, db)
    return EvaluateResponse(
        run_id=run.id,
        prompt_id=run.prompt_id,
        score=score,
        passed=score >= 4.0,
        judge_reasoning=reasoning,
    )


@router.post("/evaluate/{prompt_id}", response_model=BatchEvaluateResponse)
def evaluate_prompt(prompt_id: uuid.UUID, db: Session = Depends(get_db)) -> BatchEvaluateResponse:
    """
    Run LLM-as-judge over every run for this prompt_id.
    Scores each run against all golden set entries for that prompt.
    """
    runs = (
        db.execute(select(Run).where(Run.prompt_id == prompt_id))
        .scalars()
        .all()
    )
    if not runs:
        raise HTTPException(
            status_code=404,
            detail=f"No runs found for prompt_id '{prompt_id}'",
        )

    results: list[EvaluateResponse] = []
    for run in runs:
        score, reasoning = judge(run.id, db)
        results.append(EvaluateResponse(
            run_id=run.id,
            prompt_id=prompt_id,
            score=score,
            passed=score >= 4.0,
            judge_reasoning=reasoning,
        ))

    # NOTE: unlike judge()'s per-run poisoning (one failed golden entry forces
    # that run's score to exactly 0.0, never averaged away), this batch mean
    # averages across *runs* the naive way. Enough good runs could still
    # outvote one poisoned run above the 4.0 threshold here. Deliberately not
    # fixed — build_verdict() never reads this field, it reads each run's
    # Run.score directly. Only revisit if a CI gate ever consumes this batch
    # endpoint's `passed` directly instead of checking individual runs (see
    # PROMPTGATE_CONTEXT.md Step 4 "Open question for Step 8" — eval_gate.py
    # avoided this by calling POST /v1/evaluate per run_id, not this field).
    mean_score = sum(r.score for r in results) / len(results)
    return BatchEvaluateResponse(
        prompt_id=prompt_id,
        runs_evaluated=len(results),
        mean_score=round(mean_score, 2),
        passed=mean_score >= 4.0,
        results=results,
    )
