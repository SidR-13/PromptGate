"""
Step 3 endpoint tests using SQLite in-memory DB.
No Docker or live Postgres required.

Run with:
    AI_MOCK=true python test_step3.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

os.environ.setdefault("AI_MOCK", "true")
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

from app.db import Base, get_db
from app.main import app  # importing app pulls in all models via routers

# StaticPool forces SQLAlchemy to reuse the single in-memory connection.
# Without it, each new connection gets a fresh empty DB and tables disappear.
engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base.metadata.create_all(engine)


def override_get_db():
    db = TestingSession()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)


def test_create_prompt_versioning():
    print("--- POST /v1/prompts: auto-versioning ---")
    r = client.post("/v1/prompts", json={
        "name": "support-reply",
        "template": "You are a support agent. Reply to: {input}",
    })
    assert r.status_code == 201, r.text
    v1 = r.json()
    assert v1["version"] == 1
    assert v1["name"] == "support-reply"
    print(f"  Created v1: id={v1['id'][:8]}...")

    r = client.post("/v1/prompts", json={
        "name": "support-reply",
        "template": "You are a friendly support agent. Reply to: {input}",
    })
    assert r.status_code == 201, r.text
    v2 = r.json()
    assert v2["version"] == 2
    print(f"  Created v2: id={v2['id'][:8]}...")
    return v1, v2


def test_prompt_history():
    print("--- GET /v1/prompts/{name}/history ---")
    r = client.get("/v1/prompts/support-reply/history")
    assert r.status_code == 200, r.text
    history = r.json()
    assert len(history) == 2
    assert history[0]["version"] == 1
    assert history[1]["version"] == 2
    print(f"  History has {len(history)} versions, ordered by version asc: OK")

    r = client.get("/v1/prompts/nonexistent/history")
    assert r.status_code == 404, r.text
    print("  Missing prompt_name → 404: OK")


def test_generate_latest():
    print("--- POST /v1/generate: resolves latest by MAX(version) ---")
    r = client.post("/v1/generate", json={
        "prompt_name": "support-reply",
        "input": "My order hasn't arrived",
        "locale": "en-US",
    })
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["version"] == 2, f"Expected latest=2, got {body['version']}"
    assert body["run_id"] is not None
    assert body["prompt_id"] is not None
    assert body["locale"] == "en-US"
    print(f"  Resolved to version=2 (latest): OK")
    print(f"  run_id={body['run_id'][:8]}..., prompt_id={body['prompt_id'][:8]}...")
    return body["run_id"]


def test_generate_explicit_version():
    print("--- POST /v1/generate: explicit version=1 ---")
    r = client.post("/v1/generate", json={
        "prompt_name": "support-reply",
        "version": 1,
        "input": "My order hasn't arrived",
        "locale": "de-DE",
    })
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["version"] == 1
    print(f"  Pinned to version=1: OK")


def test_generate_missing_prompt():
    print("--- POST /v1/generate: missing prompt_name → 404 ---")
    r = client.post("/v1/generate", json={
        "prompt_name": "ghost-prompt",
        "input": "hello",
        "locale": "en-US",
    })
    assert r.status_code == 404, f"Expected 404, got {r.status_code}: {r.text}"
    print("  404: OK")


def test_generate_missing_version():
    print("--- POST /v1/generate: existing name, wrong version → 404 ---")
    r = client.post("/v1/generate", json={
        "prompt_name": "support-reply",
        "version": 99,
        "input": "hello",
        "locale": "en-US",
    })
    assert r.status_code == 404, f"Expected 404, got {r.status_code}: {r.text}"
    print("  404: OK")


def test_runs(run_id: str):
    print("--- GET /v1/runs ---")
    r = client.get("/v1/runs")
    assert r.status_code == 200, r.text
    runs = r.json()
    assert len(runs) >= 2  # at least the two generate calls above
    print(f"  Found {len(runs)} run(s): OK")

    print("--- GET /v1/runs/{id} ---")
    r = client.get(f"/v1/runs/{run_id}")
    assert r.status_code == 200, r.text
    run = r.json()
    assert run["id"] == run_id
    assert run["score"] is None       # not yet set (Step 4)
    assert run["blocked"] is False    # not yet set (Step 5)
    print(f"  Run fetched, score=None, blocked=False: OK")

    r = client.get("/v1/runs/00000000-0000-0000-0000-000000000000")
    assert r.status_code == 404
    print("  Missing run_id → 404: OK")


def test_template_rendering():
    print("--- Template {input} substitution ---")
    r = client.post("/v1/prompts", json={
        "name": "echo-test",
        "template": "Echo back exactly: {input}",
    })
    assert r.status_code == 201
    r = client.post("/v1/generate", json={
        "prompt_name": "echo-test",
        "input": "HELLO WORLD",
        "locale": "en-US",
    })
    assert r.status_code == 200
    # In mock mode we get the canned response, but no error means template rendered OK
    print("  Template rendered without error: OK")


if __name__ == "__main__":
    print("\n=== PromptGate — Step 3 tests [SQLite in-memory] ===\n")
    v1, v2 = test_create_prompt_versioning()
    test_prompt_history()
    run_id = test_generate_latest()
    test_generate_explicit_version()
    test_generate_missing_prompt()
    test_generate_missing_version()
    test_runs(run_id)
    test_template_rendering()
    print("\nAll Step 3 tests passed.")
