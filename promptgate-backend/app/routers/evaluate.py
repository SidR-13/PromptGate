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

    mean_score = sum(r.score for r in results) / len(results)
    return BatchEvaluateResponse(
        prompt_id=prompt_id,
        runs_evaluated=len(results),
        mean_score=round(mean_score, 2),
        passed=mean_score >= 4.0,
        results=results,
    )
