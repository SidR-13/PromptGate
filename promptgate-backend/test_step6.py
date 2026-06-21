"""
Step 6 tests: i18n checks (date format, number format, RTL).

Run with:
    AI_MOCK=true python test_step6.py
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
from app.locale_checker import run_locale_checks

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


def test_checker_matches_documented_defects():
    print("--- run_locale_checks() against all 5 mocks: matches Step 1 documented defects ---")
    from app.llm import MOCK_RESPONSES

    expectations = {
        "en-US": {"date_format": True, "number_format": True},
        "ar-SA": {"date_format": True, "number_format": True, "rtl": False},
        "ja-JP": {"date_format": False, "number_format": False},
        "de-DE": {"date_format": True, "number_format": True},
        "fr-FR": {"date_format": True, "number_format": True},
    }

    for locale, expected in expectations.items():
        results = {c: p for c, p, _ in run_locale_checks(MOCK_RESPONSES[locale], locale)}
        for check_type, expected_passed in expected.items():
            actual = results.get(check_type)
            assert actual == expected_passed, (
                f"{locale}/{check_type}: expected passed={expected_passed}, got {actual}"
            )
        print(f"  {locale}: {results} matches expected: OK")


def test_evaluate_locale_endpoint():
    print("--- POST /v1/evaluate-locale/{prompt_id}: ja-JP run fails, persists rows ---")
    r = client.post("/v1/prompts", json={"name": "locale-test-ja", "template": "T: {input}"})
    prompt_id = r.json()["id"]

    r = client.post("/v1/generate", json={
        "prompt_name": "locale-test-ja", "input": "hi", "locale": "ja-JP",
    })
    run_id = r.json()["run_id"]

    r = client.post(f"/v1/evaluate-locale/{prompt_id}")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["runs_checked"] == 1
    assert body["all_passed"] is False
    result = body["results"][0]
    assert result["run_id"] == run_id
    assert result["all_passed"] is False
    check_types = {c["check_type"] for c in result["checks"]}
    assert check_types == {"date_format", "number_format"}  # no rtl check for ja-JP
    print(f"  all_passed=False, no rtl check emitted for ja-JP: OK")


def test_evaluate_locale_ar_sa_only_fails_rtl():
    print("--- POST /v1/evaluate-locale/{prompt_id}: ar-SA fails only rtl ---")
    r = client.post("/v1/prompts", json={"name": "locale-test-ar", "template": "T: {input}"})
    prompt_id = r.json()["id"]

    client.post("/v1/generate", json={
        "prompt_name": "locale-test-ar", "input": "hi", "locale": "ar-SA",
    })

    r = client.post(f"/v1/evaluate-locale/{prompt_id}")
    assert r.status_code == 200, r.text
    result = r.json()["results"][0]
    checks_by_type = {c["check_type"]: c["passed"] for c in result["checks"]}
    assert checks_by_type["date_format"] is True
    assert checks_by_type["number_format"] is True
    assert checks_by_type["rtl"] is False
    print(f"  ar-SA: {checks_by_type} — only rtl fails: OK")


def test_evaluate_locale_no_runs():
    print("--- POST /v1/evaluate-locale/{prompt_id}: no runs → 404 ---")
    r = client.post("/v1/prompts", json={"name": "empty-locale-test", "template": "T: {input}"})
    prompt_id = r.json()["id"]
    r = client.post(f"/v1/evaluate-locale/{prompt_id}")
    assert r.status_code == 404
    print("  404: OK")


def test_locale_checks_persisted_no_rtl_row_for_ltr():
    print("--- locale_checks table: en-US run has no rtl row ---")
    r = client.post("/v1/prompts", json={"name": "locale-test-en", "template": "T: {input}"})
    prompt_id = r.json()["id"]
    client.post("/v1/generate", json={
        "prompt_name": "locale-test-en", "input": "hi", "locale": "en-US",
    })
    r = client.post(f"/v1/evaluate-locale/{prompt_id}")
    assert r.status_code == 200
    result = r.json()["results"][0]
    check_types = {c["check_type"] for c in result["checks"]}
    assert "rtl" not in check_types, "en-US (ltr) should not get an rtl check row"
    assert result["all_passed"] is True
    print(f"  en-US checks: {check_types}, all_passed=True: OK")


if __name__ == "__main__":
    print("\n=== PromptGate — Step 6 tests [SQLite in-memory] ===\n")
    test_checker_matches_documented_defects()
    test_evaluate_locale_endpoint()
    test_evaluate_locale_ar_sa_only_fails_rtl()
    test_evaluate_locale_no_runs()
    test_locale_checks_persisted_no_rtl_row_for_ltr()
    print("\nAll Step 6 tests passed.")
