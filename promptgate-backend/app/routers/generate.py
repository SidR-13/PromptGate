from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.llm import call_llm

router = APIRouter()

SUPPORTED_LOCALES = {"en-US", "ar-SA", "ja-JP", "de-DE", "fr-FR"}


class GenerateRequest(BaseModel):
    prompt: str = Field(..., min_length=1, description="The prompt text to send to the LLM")
    locale: str = Field("en-US", description="BCP-47 locale tag for response formatting")


class GenerateResponse(BaseModel):
    output: str
    locale: str


@router.post("/generate", response_model=GenerateResponse)
def generate(req: GenerateRequest) -> GenerateResponse:
    if req.locale not in SUPPORTED_LOCALES:
        raise HTTPException(
            status_code=422,
            detail=f"Unsupported locale '{req.locale}'. Supported: {sorted(SUPPORTED_LOCALES)}",
        )

    output = call_llm(req.prompt, req.locale)
    return GenerateResponse(output=output, locale=req.locale)
