import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import generate

app = FastAPI(
    title="PromptGate",
    description="LLM output evaluation, moderation, and i18n gating service",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # Vite dev server (Step 8)
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(generate.router, prefix="/v1")


@app.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "ai_mock": os.environ.get("AI_MOCK", "true"),
        "model": os.environ.get("CLAUDE_MODEL", "claude-haiku-4-5"),
    }
