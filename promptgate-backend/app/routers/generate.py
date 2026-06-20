from typing import Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.llm import call_llm

router = APIRouter()

SUPPORTED_LOCALES = {"en-US", "ar-SA", "ja-JP", "de-DE", "fr-FR"}


class GenerateRequest(BaseModel):
    prompt_name: str = Field(..., min_length=1, description="Stable prompt identifier — looked up in prompts table (Step 3)")
    version: Optional[int] = Field(None, description="Prompt version; None resolves to latest (Step 3)")
    input: str = Field(..., min_length=1, description="User message / template variables passed to the LLM")
    locale: str = Field("en-US", description="BCP-47 locale tag for response formatting")


class GenerateResponse(BaseModel):
    output: str
    locale: str
    # None until Step 3 wires the DB lookup; shape will not change after that.
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

    # Step 2: no DB yet — call LLM directly with `input` as the prompt text.
    # Step 3 replaces this with: fetch template by (prompt_name, version),
    # render with input, then call_llm — and populates run_id/prompt_id/version.
    output = call_llm(req.input, req.locale)
    return GenerateResponse(
        output=output,
        locale=req.locale,
    )
