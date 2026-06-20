from typing import Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.llm import call_llm

router = APIRouter()

SUPPORTED_LOCALES = {"en-US", "ar-SA", "ja-JP", "de-DE", "fr-FR"}


class GenerateRequest(BaseModel):
    # Step 2: accepts raw prompt text.
    # Step 3 will add prompt_name + version lookup and make `prompt` optional.
    prompt: str = Field(..., min_length=1, description="Prompt text (raw until Step 3 adds versioned lookup)")
    locale: str = Field("en-US", description="BCP-47 locale tag for response formatting")


class GenerateResponse(BaseModel):
    output: str
    locale: str
    # Populated by Step 3 once DB is wired; None until then.
    # Keeping them here now so the response shape never needs to change.
    run_id: Optional[UUID] = None
    prompt_id: Optional[UUID] = None
    version: Optional[int] = None


@router.post("/generate", response_model=GenerateResponse)
def generate(req: GenerateRequest) -> GenerateResponse:
    if req.locale not in SUPPORTED_LOCALES:
        raise HTTPException(
            status_code=422,
            detail=f"Unsupported locale '{req.locale}'. Supported: {sorted(SUPPORTED_LOCALES)}",
        )

    output = call_llm(req.prompt, req.locale)
    return GenerateResponse(
        output=output,
        locale=req.locale,
        # run_id, prompt_id, version filled in by Step 3
    )
