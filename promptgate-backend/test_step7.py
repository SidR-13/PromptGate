"""
Step 7 tests: combined verdict (can_ship).

Run with:
    AI_MOCK=true python test_step7.py
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


def test_unevaluated_run_cannot_ship():
    print("--- Fresh run, nothing evaluated yet → can_ship=False ---")
    r = client.post("/v1/prompts", json={"name": "verdict-fresh", "template": "T: {input}"})
    prompt_id = r.json()["id"]
    r = client.post("/v1/generate", json={
        "prompt_name": "verdict-fresh", "input": "hi", "locale": "en-US",
    })
    run_id = r.json()["run_id"]

    r = client.post("/v1/evaluate", json={"run_id": run_id})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["can_ship"] is False
    assert any("not yet evaluated" in reason for reason in body["reasons"])
    assert any("no locale checks" in reason for reason in body["reasons"])
    print(f"  can_ship=False, reasons={body['reasons']}: OK")


def test_fully_passing_run_can_ship():
    print("--- Fully evaluated, all checks pass → can_ship=True ---")
    r = client.post("/v1/prompts", json={"name": "verdict-pass", "template": "T: {input}"})
    prompt_id = r.json()["id"]
    client.post("/v1/golden-sets", json={
        "prompt_id": prompt_id, "input": "hi", "expected_behavior": "greet warmly",
    })
    r = client.post("/v1/generate", json={
        "prompt_name": "verdict-pass", "input": "hi", "locale": "en-US",
    })
    run_id = r.json()["run_id"]

    r = client.post(f"/v1/evaluate/{prompt_id}")
    assert r.status_code == 200, r.text
    r = client.post(f"/v1/evaluate-locale/{prompt_id}")
    assert r.status_code == 200, r.text

    r = client.post("/v1/evaluate", json={"run_id": run_id})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["can_ship"] is True, f"Expected can_ship=True, got reasons={body['reasons']}"
    assert body["reasons"] == []
    assert body["eval_score"] == 4.0
    assert body["blocked"] is False
    print(f"  can_ship=True, reasons=[]: OK")


def test_low_score_blocks_shipping():
    print("--- Low judge score → can_ship=False even with clean moderation/locale ---")
    import app.llm as llm_module
    original = llm_module._mock_response

    r = client.post("/v1/prompts", json={"name": "verdict-lowscore", "template": "T: {input}"})
    prompt_id = r.json()["id"]
    client.post("/v1/golden-sets", json={
        "prompt_id": prompt_id, "input": "hi", "expected_behavior": "greet",
    })
    r = client.post("/v1/generate", json={
        "prompt_name": "verdict-lowscore", "input": "hi", "locale": "en-US",
    })
    run_id = r.json()["run_id"]

    # Force judge to return a low (but legitimate, non-zero) score
    def low_score_mock(prompt, locale):
        if "EXPECTED BEHAVIOR:" in prompt:
            return '{"score": 2, "reasoning": "misses key elements"}'
        return original(prompt, locale)

    llm_module._mock_response = low_score_mock
    client.post(f"/v1/evaluate/{prompt_id}")
    llm_module._mock_response = original
    client.post(f"/v1/evaluate-locale/{prompt_id}")

    r = client.post("/v1/evaluate", json={"run_id": run_id})
    body = r.json()
    assert body["can_ship"] is False
    assert body["eval_score"] == 2.0
    assert any("below threshold" in reason for reason in body["reasons"])
    print(f"  can_ship=False, score=2.0 below threshold: OK")


def test_blocked_run_cannot_ship_despite_good_score():
    print("--- Moderation-blocked run → can_ship=False even with good score ---")
    import app.llm as llm_module
    original = llm_module._mock_response

    def fail_moderation(prompt, locale):
        if "MODERATION_CHECK:" in prompt:
            return "not json garbage"
        return original(prompt, locale)

    r = client.post("/v1/prompts", json={"name": "verdict-blocked", "template": "T: {input}"})
    prompt_id = r.json()["id"]
    client.post("/v1/golden-sets", json={
        "prompt_id": prompt_id, "input": "hi", "expected_behavior": "greet",
    })

    llm_module._mock_response = fail_moderation
    r = client.post("/v1/generate", json={
        "prompt_name": "verdict-blocked", "input": "hi", "locale": "en-US",
    })
    llm_module._mock_response = original
    run_id = r.json()["run_id"]
    assert r.json()["blocked"] is True

    client.post(f"/v1/evaluate/{prompt_id}")          # good score
    client.post(f"/v1/evaluate-locale/{prompt_id}")   # clean locale

    r = client.post("/v1/evaluate", json={"run_id": run_id})
    body = r.json()
    assert body["can_ship"] is False, f"Expected blocked run to fail ship gate, got {body}"
    assert body["blocked"] is True
    assert any("blocked by moderation" in reason for reason in body["reasons"])
    print(f"  can_ship=False despite good score, due to moderation block: OK")


def test_failed_locale_check_blocks_shipping():
    print("--- ja-JP run with failing locale checks → can_ship=False despite good score ---")
    r = client.post("/v1/prompts", json={"name": "verdict-jajp", "template": "T: {input}"})
    prompt_id = r.json()["id"]
    client.post("/v1/golden-sets", json={
        "prompt_id": prompt_id, "input": "hi", "expected_behavior": "greet",
    })
    r = client.post("/v1/generate", json={
        "prompt_name": "verdict-jajp", "input": "hi", "locale": "ja-JP",
    })
    run_id = r.json()["run_id"]

    client.post(f"/v1/evaluate/{prompt_id}")
    client.post(f"/v1/evaluate-locale/{prompt_id}")

    r = client.post("/v1/evaluate", json={"run_id": run_id})
    body = r.json()
    assert body["can_ship"] is False
    assert any("locale check(s) failed" in reason for reason in body["reasons"])
    failed_types = {lr["check_type"] for lr in body["locale_results"] if not lr["passed"]}
    assert "date_format" in failed_types
    assert "number_format" in failed_types
    print(f"  can_ship=False, failed checks: {failed_types}: OK")


def test_unknown_run_id_404():
    print("--- POST /v1/evaluate: unknown run_id → 404 ---")
    r = client.post("/v1/evaluate", json={"run_id": "00000000-0000-0000-0000-000000000000"})
    assert r.status_code == 404, r.text
    print("  404: OK")


if __name__ == "__main__":
    print("\n=== PromptGate — Step 7 tests [SQLite in-memory] ===\n")
    test_unevaluated_run_cannot_ship()
    test_fully_passing_run_can_ship()
    test_low_score_blocks_shipping()
    test_blocked_run_cannot_ship_despite_good_score()
    test_failed_locale_check_blocks_shipping()
    test_unknown_run_id_404()
    print("\nAll Step 7 tests passed.")
