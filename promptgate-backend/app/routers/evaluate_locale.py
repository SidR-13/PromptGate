import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.locale_checker import run_locale_checks
from app.models import LocaleCheck, Run

router = APIRouter()


class CheckResult(BaseModel):
    check_type: str
    passed: bool
    details: str


class RunLocaleResult(BaseModel):
    run_id: uuid.UUID
    locale: str
    checks: list[CheckResult]
    all_passed: bool


class EvaluateLocaleResponse(BaseModel):
    prompt_id: uuid.UUID
    runs_checked: int
    all_passed: bool
    results: list[RunLocaleResult]


@router.post("/evaluate-locale/{prompt_id}", response_model=EvaluateLocaleResponse)
def evaluate_locale(prompt_id: uuid.UUID, db: Session = Depends(get_db)) -> EvaluateLocaleResponse:
    """
    Run i18n checks (date format, number format, RTL where applicable) over
    every run for this prompt_id. All-or-nothing: a single failing check on
    a single run fails the overall result — consistent with the fail-closed
    pattern used by moderate() and judge(), no averaging of pass/fail booleans.
    """
    runs = db.execute(select(Run).where(Run.prompt_id == prompt_id)).scalars().all()
    if not runs:
        raise HTTPException(
            status_code=404,
            detail=f"No runs found for prompt_id '{prompt_id}'",
        )

    run_results: list[RunLocaleResult] = []
    overall_passed = True

    for run in runs:
        checks = run_locale_checks(run.output, run.locale)
        check_results: list[CheckResult] = []

        for check_type, passed, details in checks:
            db.add(LocaleCheck(
                id=uuid.uuid4(),
                run_id=run.id,
                locale=run.locale,
                check_type=check_type,
                passed=passed,
                details=details,
            ))
            check_results.append(CheckResult(check_type=check_type, passed=passed, details=details))
            if not passed:
                overall_passed = False

        run_passed = all(c.passed for c in check_results)
        run_results.append(RunLocaleResult(
            run_id=run.id,
            locale=run.locale,
            checks=check_results,
            all_passed=run_passed,
        ))

    db.commit()

    return EvaluateLocaleResponse(
        prompt_id=prompt_id,
        runs_checked=len(runs),
        all_passed=overall_passed,
        results=run_results,
    )
