"""
CI eval gate: composes the 4 existing PromptGate endpoints
(generate -> evaluate -> evaluate-locale -> evaluate) to decide whether a
prompt change is safe to ship.

Deliberately does NOT call a combined "do everything" endpoint — none
exists, by design. Every bug found in this project (Steps 4 and 6) came
from a shortcut standing in for raw composition; a convenience endpoint
built solely for CI's benefit would be the same category of risk for no
functional gain over calling what already exists, in sequence.

Exit code 0: every run for every fixture prompt has can_ship=True.
Exit code 1: at least one run has can_ship=False. Writes gate_report.md
with a flat, unordered bullet list of reasons per failing run — no
numbering or "primary reason" framing, since build_verdict()'s reasons
list is deterministic but carries no severity ranking (see
PROMPTGATE_CONTEXT.md, Step 7).

Usage:
    python ci/eval_gate.py --base-url http://localhost:8000 --fixtures ci/golden_prompts.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import requests


def seed_prompt(base_url: str, fixture: dict) -> str:
    r = requests.post(f"{base_url}/v1/prompts", json={
        "name": fixture["name"],
        "template": fixture["template"],
    })
    r.raise_for_status()
    prompt_id = r.json()["id"]

    for entry in fixture["golden_set"]:
        r = requests.post(f"{base_url}/v1/golden-sets", json={
            "prompt_id": prompt_id,
            "input": entry["input"],
            "expected_behavior": entry["expected_behavior"],
        })
        r.raise_for_status()

    return prompt_id


def generate_runs(base_url: str, fixture: dict, prompt_id: str) -> list[str]:
    run_ids = []
    for locale in fixture["test_locales"]:
        # Use the first golden entry's input as the generation input —
        # the same input the judge will score against.
        test_input = fixture["golden_set"][0]["input"]
        r = requests.post(f"{base_url}/v1/generate", json={
            "prompt_name": fixture["name"],
            "input": test_input,
            "locale": locale,
        })
        r.raise_for_status()
        run_ids.append(r.json()["run_id"])
    return run_ids


def run_gate(base_url: str, fixtures: list[dict]) -> tuple[bool, list[dict]]:
    """
    Returns (all_passed, results) where results is a list of
    {prompt_name, run_id, locale, can_ship, reasons}.
    """
    all_passed = True
    results: list[dict] = []

    for fixture in fixtures:
        prompt_id = seed_prompt(base_url, fixture)
        run_ids = generate_runs(base_url, fixture, prompt_id)

        # judge() and locale checks both require explicit calls — neither
        # runs automatically at generation time (only moderate() does).
        r = requests.post(f"{base_url}/v1/evaluate/{prompt_id}")
        r.raise_for_status()
        r = requests.post(f"{base_url}/v1/evaluate-locale/{prompt_id}")
        r.raise_for_status()

        for run_id, locale in zip(run_ids, fixture["test_locales"]):
            r = requests.post(f"{base_url}/v1/evaluate", json={"run_id": run_id})
            r.raise_for_status()
            verdict = r.json()

            if not verdict["can_ship"]:
                all_passed = False

            results.append({
                "prompt_name": fixture["name"],
                "run_id": run_id,
                "locale": locale,
                "can_ship": verdict["can_ship"],
                "reasons": verdict["reasons"],
            })

    return all_passed, results


def render_report(all_passed: bool, results: list[dict]) -> str:
    lines = ["## PromptGate eval gate", ""]
    lines.append("✅ All runs passed — safe to ship." if all_passed else "❌ Some runs failed the ship gate.")
    lines.append("")

    for result in results:
        status = "✅" if result["can_ship"] else "❌"
        lines.append(f"### {status} `{result['prompt_name']}` — {result['locale']} (run `{result['run_id'][:8]}`)")
        if result["reasons"]:
            # Flat bullet list, no numbering — reasons carry no severity
            # ranking despite always appearing in the same source order.
            for reason in result["reasons"]:
                lines.append(f"- {reason}")
        else:
            lines.append("- no blocking issues")
        lines.append("")

    return "\n".join(lines)


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--fixtures", default="ci/golden_prompts.json")
    parser.add_argument("--report-out", default="gate_report.md")
    args = parser.parse_args()

    fixtures = json.loads(Path(args.fixtures).read_text(encoding="utf-8"))
    all_passed, results = run_gate(args.base_url, fixtures)
    report = render_report(all_passed, results)

    Path(args.report_out).write_text(report, encoding="utf-8")
    print(report)

    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
