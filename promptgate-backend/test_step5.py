"""
Step 5 tests: fail-closed moderation pass.

Run with:
    AI_MOCK=true python test_step5.py
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
from app.moderator import moderate

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


def test_moderate_unit_pass():
    print("--- moderate() unit test: normal output → not blocked ---")
    blocked, reason = moderate("This is a perfectly normal support reply.")
    assert blocked is False, f"Expected not blocked, got blocked={blocked}"
    assert reason == ""
    print("  blocked=False, reason='': OK")


def test_moderate_fails_closed():
    print("--- moderate() unit test: LLM error → fails closed (blocked=True) ---")
    import app.llm as llm_module
    original = llm_module._mock_response
    llm_module._mock_response = lambda prompt, locale: "not json garbage"

    blocked, reason = moderate("Some output")
    assert blocked is True, f"Expected fail-closed blocked=True, got {blocked}"
    assert "moderation check failed" in reason
    print(f"  blocked=True on error, reason='{reason}': OK")

    llm_module._mock_response = original


def test_generate_includes_moderation():
    print("--- POST /v1/generate: response includes blocked/block_reason ---")
    r = client.post("/v1/prompts", json={
        "name": "mod-test",
        "template": "Reply to: {input}",
    })
    assert r.status_code == 201, r.text

    r = client.post("/v1/generate", json={
        "prompt_name": "mod-test",
        "input": "Hello there",
        "locale": "en-US",
    })
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["blocked"] is False
    assert body["block_reason"] is None
    print(f"  blocked={body['blocked']}, block_reason={body['block_reason']}: OK")
    return body["run_id"]


def test_generate_moderation_persisted_to_db(run_id: str):
    print("--- GET /v1/runs/{id}: moderation fields persisted ---")
    r = client.get(f"/v1/runs/{run_id}")
    assert r.status_code == 200, r.text
    run = r.json()
    assert run["blocked"] is False
    assert run["block_reason"] is None
    print(f"  DB run: blocked={run['blocked']}, block_reason={run['block_reason']}: OK")


def test_generate_blocks_on_moderation_failure():
    print("--- POST /v1/generate: moderation failure → run blocked=True, still 200 ---")
    import app.llm as llm_module
    original = llm_module._mock_response

    call_count = {"n": 0}

    def flaky_mock(prompt, locale):
        call_count["n"] += 1
        if "MODERATION_CHECK:" in prompt:
            return "not json garbage"  # force moderation failure
        return original(prompt, locale)

    llm_module._mock_response = flaky_mock

    r = client.post("/v1/prompts", json={"name": "mod-fail-test", "template": "T: {input}"})
    assert r.status_code == 201

    r = client.post("/v1/generate", json={
        "prompt_name": "mod-fail-test",
        "input": "hello",
        "locale": "en-US",
    })
    assert r.status_code == 200, r.text  # request itself doesn't fail
    body = r.json()
    assert body["blocked"] is True, f"Expected fail-closed blocked=True, got {body}"
    assert "moderation check failed" in body["block_reason"]
    print(f"  Request still returns 200, but blocked=True: OK")

    r = client.get(f"/v1/runs/{body['run_id']}")
    db_run = r.json()
    assert db_run["blocked"] is True
    assert "moderation check failed" in db_run["block_reason"]
    print(f"  DB row also blocked=True (fail-closed persisted): OK")

    llm_module._mock_response = original


if __name__ == "__main__":
    print("\n=== PromptGate — Step 5 tests [SQLite in-memory] ===\n")
    test_moderate_unit_pass()
    test_moderate_fails_closed()
    run_id = test_generate_includes_moderation()
    test_generate_moderation_persisted_to_db(run_id)
    test_generate_blocks_on_moderation_failure()
    print("\nAll Step 5 tests passed.")
