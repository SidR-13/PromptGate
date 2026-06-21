import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.llm import call_llm
from app.models import Prompt, Run
from app.moderator import moderate

router = APIRouter()

SUPPORTED_LOCALES = {"en-US", "ar-SA", "ja-JP", "de-DE", "fr-FR"}


class GenerateRequest(BaseModel):
    prompt_name: str = Field(..., min_length=1, description="Stable prompt identifier — looked up in prompts table")
    version: Optional[int] = Field(None, description="Prompt version; None resolves to latest via MAX(version)")
    input: str = Field(..., min_length=1, description="User message substituted into the prompt template at {input}")
    locale: str = Field("en-US", description="BCP-47 locale tag for response formatting")


class GenerateResponse(BaseModel):
    output: str
    locale: str
    run_id: Optional[uuid.UUID] = None
    prompt_id: Optional[uuid.UUID] = None
    version: Optional[int] = None
    blocked: bool = False
    block_reason: Optional[str] = None


def _resolve_prompt(name: str, version: Optional[int], db: Session) -> Prompt:
    """
    Look up a prompt by name and version.
    version=None resolves to MAX(version) for that name — not MAX(created_at),
    since timestamps can be out of order on restores/patches.
    Returns 404 if the name doesn't exist at all.
    """
    if version is not None:
        prompt = db.scalar(
            select(Prompt).where(Prompt.name == name, Prompt.version == version)
        )
        if prompt is None:
            raise HTTPException(
                status_code=404,
                detail=f"Prompt '{name}' version {version} not found",
            )
        return prompt

    # Resolve latest by MAX(version)
    max_version = db.scalar(
        select(func.max(Prompt.version)).where(Prompt.name == name)
    )
    if max_version is None:
        raise HTTPException(
            status_code=404,
            detail=f"No prompt found with name '{name}'",
        )
    prompt = db.scalar(
        select(Prompt).where(Prompt.name == name, Prompt.version == max_version)
    )
    return prompt  # type: ignore[return-value]  # max_version guarantees a row exists


def _render_template(template: str, input_text: str) -> str:
    """Substitute {input} placeholder in template with the user's input."""
    return template.replace("{input}", input_text)


@router.post("/generate", response_model=GenerateResponse)
def generate(req: GenerateRequest, db: Session = Depends(get_db)) -> GenerateResponse:
    if req.locale not in SUPPORTED_LOCALES:
        raise HTTPException(
            status_code=422,
            detail=f"Unsupported locale '{req.locale}'. Supported: {sorted(SUPPORTED_LOCALES)}",
        )

    prompt = _resolve_prompt(req.prompt_name, req.version, db)
    rendered = _render_template(prompt.template, req.input)
    output = call_llm(rendered, req.locale)

    # Moderation runs at generation time so every run row is moderated from
    # creation — never a window where a run exists with unknown moderation status.
    blocked, block_reason = moderate(output)

    run = Run(
        id=uuid.uuid4(),
        prompt_id=prompt.id,
        input=req.input,
        output=output,
        locale=req.locale,
        blocked=blocked,
        block_reason=block_reason or None,
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    return GenerateResponse(
        output=output,
        locale=req.locale,
        run_id=run.id,
        prompt_id=prompt.id,
        version=prompt.version,
        blocked=blocked,
        block_reason=block_reason or None,
    )
