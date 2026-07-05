import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Prompt

router = APIRouter()


class PromptCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, description="Stable human-readable identifier, e.g. 'support-reply'")
    template: str = Field(..., min_length=1, description="Prompt template text; use {input} as the user-input placeholder")


class PromptResponse(BaseModel):
    id: uuid.UUID
    name: str
    version: int
    template: str
    created_at: datetime

    model_config = {"from_attributes": True}


class PromptSummary(BaseModel):
    name: str
    latest_version: int


@router.get("/prompts", response_model=list[PromptSummary])
def list_prompts(db: Session = Depends(get_db)) -> list[PromptSummary]:
    rows = db.execute(
        select(Prompt.name, func.max(Prompt.version).label("latest_version"))
        .group_by(Prompt.name)
        .order_by(Prompt.name)
    ).all()
    return [PromptSummary(name=row.name, latest_version=row.latest_version) for row in rows]


@router.post("/prompts", response_model=PromptResponse, status_code=201)
def create_prompt(req: PromptCreateRequest, db: Session = Depends(get_db)) -> PromptResponse:
    # Resolve next version: MAX(version) for this name + 1, or 1 if first
    max_version = db.scalar(
        select(func.max(Prompt.version)).where(Prompt.name == req.name)
    )
    next_version = (max_version or 0) + 1

    prompt = Prompt(
        id=uuid.uuid4(),
        name=req.name,
        version=next_version,
        template=req.template,
    )
    db.add(prompt)
    db.commit()
    db.refresh(prompt)
    return PromptResponse.model_validate(prompt)


@router.get("/prompts/{name}/history", response_model=list[PromptResponse])
def get_prompt_history(name: str, db: Session = Depends(get_db)) -> list[PromptResponse]:
    rows = (
        db.execute(
            select(Prompt).where(Prompt.name == name).order_by(Prompt.version)
        )
        .scalars()
        .all()
    )
    if not rows:
        raise HTTPException(status_code=404, detail=f"No prompt found with name '{name}'")
    return [PromptResponse.model_validate(r) for r in rows]
