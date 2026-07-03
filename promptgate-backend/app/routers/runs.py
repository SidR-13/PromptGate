import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.db import get_db
from app.models import Run

router = APIRouter()


class RunResponse(BaseModel):
    id: uuid.UUID
    prompt_id: uuid.UUID
    prompt_name: str
    version: int
    input: str
    output: str
    locale: str
    score: Optional[float]
    judge_reasoning: Optional[str]
    blocked: bool
    block_reason: Optional[str]
    created_at: datetime


def _run_to_response(r: Run) -> RunResponse:
    return RunResponse(
        id=r.id,
        prompt_id=r.prompt_id,
        prompt_name=r.prompt.name,
        version=r.prompt.version,
        input=r.input,
        output=r.output,
        locale=r.locale,
        score=r.score,
        judge_reasoning=r.judge_reasoning,
        blocked=r.blocked,
        block_reason=r.block_reason,
        created_at=r.created_at,
    )


@router.get("/runs", response_model=list[RunResponse])
def list_runs(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
) -> list[RunResponse]:
    rows = (
        db.execute(
            select(Run)
            .options(joinedload(Run.prompt))
            .order_by(Run.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        .scalars()
        .all()
    )
    return [_run_to_response(r) for r in rows]


@router.get("/runs/{run_id}", response_model=RunResponse)
def get_run(run_id: uuid.UUID, db: Session = Depends(get_db)) -> RunResponse:
    run = db.execute(
        select(Run).options(joinedload(Run.prompt)).where(Run.id == run_id)
    ).scalar_one_or_none()
    if run is None:
        raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found")
    return _run_to_response(run)
