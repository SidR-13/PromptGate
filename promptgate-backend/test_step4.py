"""
Step 4 tests: golden sets + LLM-as-judge evaluation.

Run with:
    AI_MOCK=true python test_step4.py
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
from app.main import app

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


def setup_prompt_and_run():
    """Create a prompt, golden set entry, and a run to evaluate."""
    r = client.post("/v1/prompts", json={
        "name": "support-reply",
        "template": "You are a support agent. Reply to: {input}",
    })
    assert r.status_code == 201, r.text
    prompt = r.json()

    r = client.post("/v1/golden-sets", json={
        "prompt_id": prompt["id"],
        "input": "Where is my order?",
        "expected_behavior": "Apologise, ask for order number, offer to help track",
    })
    assert r.status_code == 201, r.text
    golden = r.json()

    r = client.post("/v1/generate", json={
        "prompt_name": "support-reply",
        "input": "Where is my order?",
        "locale": "en-US",
    })
    assert r.status_code == 200, r.text
    run = r.json()

    return prompt, golden, run


def test_golden_set_crud():
    print("--- POST /v1/golden-sets: create entry ---")
    r = client.post("/v1/prompts", json={
        "name": "gs-test",
        "template": "Reply to: {input}",
    })
    prompt_id = r.json()["id"]

    r = client.post("/v1/golden-sets", json={
        "prompt_id": prompt_id,
        "input": "hello",
        "expected_behavior": "greet the user",
    })
    assert r.status_code == 201, r.text
    gs = r.json()
    assert gs["prompt_id"] == prompt_id
    print(f"  Created golden set entry: id={gs['id'][:8]}...")

    print("--- POST /v1/golden-sets: missing prompt → 404 ---")
    r = client.post("/v1/golden-sets", json={
        "prompt_id": "00000000-0000-0000-0000-000000000000",
        "input": "hello",
        "expected_behavior": "greet",
    })
    assert r.status_code == 404, r.text
    print("  404: OK")

    print("--- GET /v1/golden-sets/{prompt_id} ---")
    r = client.get(f"/v1/golden-sets/{prompt_id}")
    assert r.status_code == 200
    entries = r.json()
    assert len(entries) == 1
    print(f"  Listed {len(entries)} entry: OK")


def test_evaluate_scores_run():
    print("--- POST /v1/evaluate/{prompt_id}: scores all runs ---")
    prompt, golden, run = setup_prompt_and_run()

    r = client.post(f"/v1/evaluate/{prompt['id']}")
    assert r.status_code == 200, r.text
    body = r.json()

    assert body["runs_evaluated"] == 1
    assert body["mean_score"] == 4.0  # mock judge always returns 4
    assert body["passed"] is True
    assert len(body["results"]) == 1
    result = body["results"][0]
    assert result["score"] == 4.0
    assert result["passed"] is True
    print(f"  mean_score={body['mean_score']}, passed={body['passed']}: OK")

    # Confirm score persisted to DB via GET /v1/runs/{id}
    r = client.get(f"/v1/runs/{run['run_id']}")
    assert r.status_code == 200
    db_run = r.json()
    assert db_run["score"] == 4.0
    assert db_run["judge_reasoning"] is not None
    print(f"  score persisted to DB: score={db_run['score']}, reasoning set: OK")


def test_evaluate_no_runs():
    print("--- POST /v1/evaluate/{prompt_id}: no runs → 404 ---")
    r = client.post("/v1/prompts", json={"name": "empty-prompt", "template": "T: {input}"})
    prompt_id = r.json()["id"]
    r = client.post(f"/v1/evaluate/{prompt_id}")
    assert r.status_code == 404, f"Expected 404, got {r.status_code}"
    print("  404: OK")


def test_evaluate_no_golden_set():
    print("--- POST /v1/evaluate/{prompt_id}: no golden entries → score=0 ---")
    r = client.post("/v1/prompts", json={"name": "no-golden", "template": "T: {input}"})
    prompt_id = r.json()["id"]
    r = client.post("/v1/generate", json={
        "prompt_name": "no-golden", "input": "hi", "locale": "en-US"
    })
    assert r.status_code == 200

    r = client.post(f"/v1/evaluate/{prompt_id}")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["mean_score"] == 0.0
    assert body["passed"] is False
    print(f"  No golden entries → score=0.0, passed=False: OK")


def test_judge_failure_writes_zero():
    print("--- judge() failure writes score=0.0, not NULL ---")
    import app.llm as llm_module
    original = llm_module._mock_response

    # Force the mock to return garbage JSON so judge() catches ValueError
    llm_module._mock_response = lambda prompt, locale: "not json garbage"

    r = client.post("/v1/prompts", json={"name": "fail-judge", "template": "T: {input}"})
    prompt_id = r.json()["id"]
    r = client.post("/v1/golden-sets", json={
        "prompt_id": prompt_id,
        "input": "test",
        "expected_behavior": "something",
    })
    r = client.post("/v1/generate", json={
        "prompt_name": "fail-judge", "input": "test", "locale": "en-US"
    })
    run_id = r.json()["run_id"]

    r = client.post(f"/v1/evaluate/{prompt_id}")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["mean_score"] == 0.0
    assert "judge call failed" in body["results"][0]["judge_reasoning"]
    print(f"  score=0.0 on failure, reasoning contains 'judge call failed': OK")

    # Confirm score=0 in DB, not NULL
    r = client.get(f"/v1/runs/{run_id}")
    assert r.json()["score"] == 0.0
    print(f"  score=0.0 persisted to DB (not NULL): OK")

    llm_module._mock_response = original


if __name__ == "__main__":
    print("\n=== PromptGate — Step 4 tests [SQLite in-memory] ===\n")
    test_golden_set_crud()
    test_evaluate_scores_run()
    test_evaluate_no_runs()
    test_evaluate_no_golden_set()
    test_judge_failure_writes_zero()
    print("\nAll Step 4 tests passed.")
