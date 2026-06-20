import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Run

router = APIRouter()


class RunResponse(BaseModel):
    id: uuid.UUID
    prompt_id: uuid.UUID
    input: str
    output: str
    locale: str
    score: Optional[float]
    judge_reasoning: Optional[str]
    blocked: bool
    block_reason: Optional[str]
    created_at: datetime

    model_config = {"from_attributes": True}


@router.get("/runs", response_model=list[RunResponse])
def list_runs(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
) -> list[RunResponse]:
    rows = (
        db.execute(
            select(Run).order_by(Run.created_at.desc()).offset(skip).limit(limit)
        )
        .scalars()
        .all()
    )
    return [RunResponse.model_validate(r) for r in rows]


@router.get("/runs/{run_id}", response_model=RunResponse)
def get_run(run_id: uuid.UUID, db: Session = Depends(get_db)) -> RunResponse:
    run = db.get(Run, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found")
    return RunResponse.model_validate(run)
