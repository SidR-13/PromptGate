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
    assert body["mean_score"] == 4.7  # mock judge default returns 4.7 (see llm.py _JUDGE_DEFAULT)
    assert body["passed"] is True
    assert len(body["results"]) == 1
    result = body["results"][0]
    assert result["score"] == 4.7
    assert result["passed"] is True
    print(f"  mean_score={body['mean_score']}, passed={body['passed']}: OK")

    # Confirm score persisted to DB via GET /v1/runs/{id}
    r = client.get(f"/v1/runs/{run['run_id']}")
    assert r.status_code == 200
    db_run = r.json()
    assert db_run["score"] == 4.7
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


def test_single_failure_poisons_batch_not_averaged():
    print("--- judge() fail-closed: one failed entry poisons the whole score, not averaged ---")
    import app.llm as llm_module
    original = llm_module._mock_response

    # One golden entry's prompt will contain "FAIL_CASE" — force that specific
    # judge call to fail while the other golden entry's call succeeds normally.
    def selective_failure(prompt, locale):
        if "FAIL_CASE" in prompt:
            return "not json garbage"
        return original(prompt, locale)

    r = client.post("/v1/prompts", json={"name": "poison-test", "template": "T: {input}"})
    prompt_id = r.json()["id"]

    # Both golden entries use the same input as the run so the input filter
    # matches them. The trigger for failure is in expected_behavior, not input.
    client.post("/v1/golden-sets", json={
        "prompt_id": prompt_id, "input": "test", "expected_behavior": "PASS_CASE behavior",
    })
    client.post("/v1/golden-sets", json={
        "prompt_id": prompt_id, "input": "test", "expected_behavior": "FAIL_CASE behavior",
    })

    r = client.post("/v1/generate", json={
        "prompt_name": "poison-test", "input": "test", "locale": "en-US",
    })
    run_id = r.json()["run_id"]

    llm_module._mock_response = selective_failure
    r = client.post(f"/v1/evaluate/{prompt_id}")
    llm_module._mock_response = original

    assert r.status_code == 200, r.text
    body = r.json()
    result = body["results"][0]
    # Naive average of [4.0, 0.0] would be 2.0 — still fails the >=4 threshold here,
    # but the real risk is with more passing entries diluting one failure above
    # threshold. The fix makes ANY failure force exactly 0.0, never a diluted mean.
    assert result["score"] == 0.0, f"Expected poisoned score=0.0, got {result['score']}"
    assert result["passed"] is False
    assert "judge call failed" in result["judge_reasoning"]
    print(f"  One of two entries failed → final score=0.0 (not averaged to 2.0): OK")

    r = client.get(f"/v1/runs/{run_id}")
    assert r.json()["score"] == 0.0
    print(f"  Poisoned score=0.0 persisted to DB: OK")


def test_evaluate_single_run():
    print("--- POST /v1/evaluate/run/{run_id}: scores one run only ---")
    prompt, golden, run = setup_prompt_and_run()

    # Add a second run — it must NOT be touched by the single-run endpoint
    r = client.post("/v1/generate", json={
        "prompt_name": "support-reply",
        "input": "Another question",
        "locale": "de-DE",
    })
    assert r.status_code == 200, r.text
    second_run_id = r.json()["run_id"]

    # Score only the first run
    r = client.post(f"/v1/evaluate/run/{run['run_id']}")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["run_id"] == run["run_id"]
    assert body["score"] == 4.7  # mock judge default (see llm.py _JUDGE_DEFAULT)
    assert body["passed"] is True
    assert body["judge_reasoning"] is not None
    print(f"  score={body['score']}, passed={body['passed']}: OK")

    # First run scored in DB
    r = client.get(f"/v1/runs/{run['run_id']}")
    assert r.json()["score"] == 4.7
    print(f"  score persisted to DB for first run: OK")

    # Second run still NULL — single-run endpoint did not touch it
    r = client.get(f"/v1/runs/{second_run_id}")
    assert r.json()["score"] is None, (
        f"Second run score should still be NULL but got {r.json()['score']}"
    )
    print(f"  second run score still NULL (not overwritten): OK")


def test_evaluate_single_run_not_found():
    print("--- POST /v1/evaluate/run/{run_id}: unknown run → 404 ---")
    r = client.post("/v1/evaluate/run/00000000-0000-0000-0000-000000000000")
    assert r.status_code == 404, f"Expected 404, got {r.status_code}"
    print("  404: OK")


if __name__ == "__main__":
    print("\n=== PromptGate — Step 4 tests [SQLite in-memory] ===\n")
    test_golden_set_crud()
    test_evaluate_scores_run()
    test_evaluate_no_runs()
    test_evaluate_no_golden_set()
    test_judge_failure_writes_zero()
    test_single_failure_poisons_batch_not_averaged()
    test_evaluate_single_run()
    test_evaluate_single_run_not_found()
    print("\nAll Step 4 tests passed.")
