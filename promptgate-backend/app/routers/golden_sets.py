import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import GoldenSet, Prompt

router = APIRouter()


class GoldenSetCreateRequest(BaseModel):
    prompt_id: uuid.UUID
    input: str = Field(..., min_length=1)
    expected_behavior: str = Field(..., min_length=1)


class GoldenSetResponse(BaseModel):
    id: uuid.UUID
    prompt_id: uuid.UUID
    input: str
    expected_behavior: str
    created_at: datetime

    model_config = {"from_attributes": True}


@router.post("/golden-sets", response_model=GoldenSetResponse, status_code=201)
def create_golden_set(
    req: GoldenSetCreateRequest, db: Session = Depends(get_db)
) -> GoldenSetResponse:
    prompt = db.get(Prompt, req.prompt_id)
    if prompt is None:
        raise HTTPException(status_code=404, detail=f"Prompt '{req.prompt_id}' not found")

    entry = GoldenSet(
        id=uuid.uuid4(),
        prompt_id=req.prompt_id,
        input=req.input,
        expected_behavior=req.expected_behavior,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return GoldenSetResponse.model_validate(entry)


@router.get("/golden-sets/{prompt_id}", response_model=list[GoldenSetResponse])
def list_golden_sets(prompt_id: uuid.UUID, db: Session = Depends(get_db)) -> list[GoldenSetResponse]:
    rows = db.execute(
        select(GoldenSet).where(GoldenSet.prompt_id == prompt_id)
    ).scalars().all()
    return [GoldenSetResponse.model_validate(r) for r in rows]
