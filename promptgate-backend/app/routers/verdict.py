import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db import get_db
from app.verdict import build_verdict

router = APIRouter()


class VerdictRequest(BaseModel):
    run_id: uuid.UUID


class LocaleResultItem(BaseModel):
    check_type: str
    passed: bool
    details: str


class VerdictResponse(BaseModel):
    run_id: uuid.UUID
    eval_score: Optional[float]
    blocked: bool
    block_reason: Optional[str]
    locale_results: list[LocaleResultItem]
    can_ship: bool
    reasons: list[str]


@router.post("/evaluate", response_model=VerdictResponse)
def evaluate(req: VerdictRequest, db: Session = Depends(get_db)) -> VerdictResponse:
    try:
        verdict = build_verdict(req.run_id, db)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return VerdictResponse(**verdict)
