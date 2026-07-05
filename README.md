# PromptGate

PromptGate is an LLM output gateway that answers one question before any AI-generated text ships to production: *is this response safe, high-quality, and correct for the target market?* I built it for the scenario that comes up repeatedly on teams shipping AI features across multiple locales — a response can look fine in English and in a test harness while failing every real quality bar for German, Japanese, or Arabic customers. PromptGate enforces those bars automatically across three independently fail-closed subsystems — quality scoring, content moderation, and locale formatting correctness — and blocks a release the moment any one of them fails.

## The problem it solves

Most LLM evaluation setups check output quality in isolation. They don't ask whether the output is appropriate for a customer in Riyadh reading right-to-left, or whether a Japanese response uses Western date formats because the model defaulted to English conventions. "It seems fine in English" is not a shipping standard when your product serves five locales. Without a gateway that checks each signal independently and composes them into a single shippable verdict, locale-specific defects reach production silently — and they tend to stay there because they're invisible to reviewers who only read English.

## How it works — the pipeline

```
Input ──▶ [Generate] ──▶ [Judge] ──▶ [Moderate] ──▶ [i18n Check] ──▶ [Verdict]
             │               │             │               │               │
         LLM call        LLM-as-judge  Fail-closed     Babel checks    can_ship
         stored as        scores 1–5    blocks on       date/number/    True iff
         Run row          vs golden     any error       RTL per locale  all pass
                          set entries
```

**Generate** — the prompt template is resolved to its latest version, rendered with the user's input, and sent to the LLM. The response is stored as a `Run` row immediately.

**Judge** — a separate LLM call scores the output 1–5 against golden test cases with matching inputs. Fail-closed: if any single golden-entry evaluation fails, the entire score poisons to 0.0 rather than being averaged away by entries that scored well.

**Moderate** — another separate LLM call evaluates the output for harmful or policy-violating content. Fail-closed: if the moderation call errors for any reason, the run is blocked. It never defaults to allowed.

**i18n Check** — Babel validates date format, number grouping separators, and RTL Unicode control marks for the run's locale. Fail-closed: no locale checks recorded is treated identically to a failed check — unchecked does not mean safe.

**Verdict** — `build_verdict()` reads raw signals only, never a cached summary. `can_ship` is `True` only when all four checks pass.

## Screenshots

![The full dashboard: 50 runs across 5 locales, 34% ship rate. Only outputs that clear all three checks ship.](docs/screenshots/dashboard-hero.png)

---

The most important property of the system: **a perfect quality score does not mean safe to ship.**

![ar-SA scores 5.0 on quality — a perfect response — and is still blocked. RTL Unicode control marks are missing from the Arabic output.](docs/screenshots/dashboard-blocked.png)

The reasons panel shows what passed and why, not just the final verdict.

![de-DE passes all three checks: eval score 5.0, moderation clean, date and number format correct for German locale.](docs/screenshots/dashboard-passed.png)

One prompt, five locales, independently evaluated outputs.

![Five locales in a single frame — Japanese, English, French, German, Arabic — each evaluated against the same prompt but judged in its target locale.](docs/screenshots/dashboard-multilingual.png)

---

![Per-locale check matrix: ar-SA fails RTL only, ja-JP fails both date and number format. Each failure is independently identified.](docs/screenshots/locale-grid.png)

![Score trend across runs: v4 ship rate drops to 31% — the amber threshold line is at 4.0, green dots are shippable, red are blocked.](docs/screenshots/trend-chart.png)

## Tech stack

| Layer | Technology | Why |
|---|---|---|
| Backend API | Python 3.11, FastAPI | Async-native, Pydantic validation at the request boundary, minimal boilerplate for a structured JSON API |
| LLM | claude-haiku-4-5 (Anthropic) | Fast, cost-efficient model for both judge and moderation passes; `AI_MOCK=true` flag keeps CI fully reproducible without API calls |
| Database | PostgreSQL 16 + Alembic | FK constraints enforce the `run → prompt_version` relationship; Alembic migrations are versioned alongside code and run in CI identically to production |
| Frontend | React 19 + TypeScript + Vite + Tailwind v4 + Recharts | Vite HMR for fast iteration; Recharts for the score trend chart with explicit `score=0.0` gap treatment so judge failures never read as quality regressions |
| i18n | Python Babel | Battle-tested ICU locale data for date and number formats and text direction — avoids the per-locale regex maintenance trap |
| CI/CD | GitHub Actions | Blocks PRs on eval regression; treats prompt changes like code changes |
| Infra | Docker Compose | Single-command local stack; Postgres healthcheck gates backend startup so the application never starts against an unready database |

## Key engineering decisions

**1. Fail-closed philosophy applied uniformly across all three subsystems**

The easiest failure mode in a multi-signal gateway is for one good signal to silently compensate for another's failure. I designed all three subsystems with the same invariant: any error or ambiguity is a hard block, never a soft signal that gets averaged away. `judge()` poisons the entire run score to 0.0 if any single golden-entry evaluation fails. `moderate()` blocks on any error — a failed moderation call never defaults to allowed. `build_verdict()` treats a NULL score as not shippable, and the absence of locale checks as not shippable. Three independent implementations, same philosophy: no single passing signal can mask another subsystem's failure.

**2. score=NULL means "not yet run" — score=0.0 means "ran and failed"**

This semantic split is load-bearing. `_judge_single` clamps legitimate quality scores to `[1.0, 5.0]`, which means 0.0 is never a real quality result — it is only ever written by the except branch, indicating a judge infrastructure failure. Preserving NULL as the "not evaluated" state means `build_verdict()` has a single code path: `score < 4.0` → fail, with NULL handled by the same `score is None` guard. There is no special-casing, no secondary NULL path, and no ambiguity about whether a 0.0 in the database means "very bad response" or "judge crashed." An infrastructure error is a definite failing result, not an unknown state.

**3. Input-filtered golden set evaluation**

Golden set entries are stored per-prompt, but a prompt can serve multiple input types — "where is my order," "I want a refund," and "my product is damaged" are different scenarios with different expected behaviors. Without filtering, `judge()` scored a French "refund" response against an English "order tracking" golden entry. The topic mismatch and language mismatch together guaranteed a score of 1–2 regardless of actual response quality. The fix was a single `.where(GoldenSet.input == run.input)` clause in the evaluation query: golden entries are now matched per-scenario, not per-prompt. The `input` field went from decorative metadata to a functional filter, and scoring became accurate.

**4. Locale-aware judge**

The initial judge implementation called `call_llm_json(locale="en-US")` hardcoded throughout — never parameterized. The symptom was exact and reproducible: `en-US` always scored 5.0, every other locale always scored 2.0, regardless of actual response quality. The judge was reading German or Japanese output against an English prompt template and interpreting the language difference as a quality problem. The fix required two changes: passing `run.locale` through the full call chain (`judge()` → `_judge_single()` → `call_llm_json()`), and adding an explicit `LOCALE` block to the judge prompt instructing the model to evaluate as a fluent speaker of the target locale and not penalise non-English output. After this fix, `de-DE` and `fr-FR` correctly score on content quality; `ja-JP` and `ar-SA` remain blocked — but for the right reason, by the locale checker for formatting defects, not by the judge for language.

**5. No pre-aggregated verdict fields anywhere in the schema**

There is no `locale_passed` column on `Run`, no cached `last_verdict`, no summary field anywhere in the database. `build_verdict()` queries `Run.score`, `Run.blocked`, and raw `LocaleCheck` rows directly, every time it is called. This was a deliberate decision made after the Step 4 averaging bug: that bug existed precisely because `judge()` was consuming a mean — an aggregation — which allowed one failure to be diluted by enough passing scores into a result that cleared the threshold. Every pre-aggregation point is a place where a fail-closed invariant can be quietly violated. Keeping `build_verdict()` at the raw signal layer means there is no aggregation surface to get wrong.

## Bugs worth reading about

**1. Python `\b` silently fails at CJK/Latin character transitions**

The date format checker was written to detect Western month names in non-English output. The canonical defect in the Japanese mock was `"会議はJune 20"` — a meeting notice using an English date. The pattern `\bJune\b` never fired. Python's `re` module treats Han and Hiragana characters as `\w`, which means there is no word boundary between `は` and `J` — `\b` requires a `\w`/`\W` transition, and both sides are `\w`. The same root cause hit the number check, where `\b` failed to match at the Latin/CJK boundary after an ungrouped number immediately followed by a Japanese character. The entire motivating defect category was silently undetected. I caught this by running the checker manually against all five locale mocks and inspecting pass/fail before writing any test assertions — writing tests first would have encoded the broken behavior as expected. The fix dropped `\b` entirely: the date check uses a negative lookahead to avoid matching inside longer Latin words, and the number check uses digit-adjacency lookarounds where only digit boundaries matter.

**2. `judge()` averaged a failed golden-entry score into the mean**

`_judge_single` returns 0.0 only from its except branch. Legitimate scores are clamped to `[1.0, 5.0]`, so 0.0 is never a real quality signal. The original `judge()` summed all scores and divided by count. With nine golden entries scoring 5.0 and one infrastructure failure scoring 0.0, the mean was 4.5 — which passes the `≥ 4.0` threshold. The run was marked shippable despite a real evaluation gap. The fix was poisoning: if any score in the list is 0.0, the entire run's final score is forced to 0.0, regardless of how well the other entries scored. This is the same invariant `moderate()` uses — one block is final, never averaged against other checks.

**3. Locale-aware judge bias**

The bias was not random noise; it was exact and reproducible: `en-US` always 5.0, every other locale always 2.0, across every run. That pattern — perfect precision, wrong axis — is a strong signal that the scoring mechanism had a systematic flaw rather than a data problem. The root cause was `call_llm_json(locale="en-US")` hardcoded in `_judge_single`: the judge evaluated every response as if it were English, then penalised the language difference rather than the content quality. PromptGate's locale checker was doing genuine multilingual work, but the judge was not. The system appeared to support multilingual evaluation while silently blocking every non-English output for the wrong reason. After the fix, `de-DE` and `fr-FR` both reach `can_ship=True`; `ja-JP` and `ar-SA` remain blocked by the locale checker for the intended formatting defects.

**4. EvalPanel called the verdict-read endpoint as its evaluate step**

The frontend evaluation panel sent `POST /v1/evaluate` as its "evaluate now" action. That endpoint reads already-written scores from the database and returns a verdict — it never calls the judge. Every panel run appeared to complete successfully (200 response, verdict returned), but the score in the database never changed. The defect was invisible in normal use: if a run already had a score, the panel returned a valid verdict and there was no signal that the judge had not run again. I found it by noticing that a freshly-generated run always showed `score=NULL` in the database regardless of how many times I clicked evaluate. The fix was adding `POST /v1/evaluate/run/{run_id}` — a dedicated single-run judge endpoint that writes the score for exactly one run without touching other runs for the same prompt.

**5. Adding more golden entries made scores worse, not better**

When non-English scores consistently came back at 2.0, the first hypothesis was insufficient golden set coverage — perhaps the judge needed locale-specific golden entries. I added five locales × three query types = 15 new entries. With the input filter in place, a French "order not arrived" run now matched exactly five golden entries: one with a French expected behavior (scored 5.0) and four that expected responses in other languages (scored 1.0 each). Mean: 1.8 — worse than before. More entries added more mismatches. The golden set content was correct; the root cause was that the judge was evaluating in `en-US` regardless of the run's locale. The fix required going to the judge itself, not the data. The lesson: adding data to compensate for a systematic bias amplifies the bias by providing more mismatched comparisons.

## Running locally

**Prerequisites:** Docker, Docker Compose. An Anthropic API key is optional — `AI_MOCK=true` by default.

**1. Clone and configure**

```bash
git clone https://github.com/SidR-13/PromptGate.git
cd PromptGate
cp promptgate-backend/.env.example promptgate-backend/.env
```

Edit `promptgate-backend/.env`:

```env
ANTHROPIC_API_KEY=your_key_here   # only needed when AI_MOCK=false
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/promptgate
AI_MOCK=true
CLAUDE_MODEL=claude-haiku-4-5
```

**2. Start the stack**

```bash
docker compose up
```

Starts the FastAPI backend on `http://localhost:8000` and PostgreSQL 16. The backend waits for Postgres to pass its healthcheck before starting. Alembic migrations run automatically.

**3. Create a prompt**

```bash
curl -X POST http://localhost:8000/v1/prompts \
  -H "Content-Type: application/json" \
  -d '{"name": "support-reply", "template": "You are a support agent. Reply to: {input}"}'
```

**4. Add a golden set entry**

```bash
curl -X POST http://localhost:8000/v1/golden-sets \
  -H "Content-Type: application/json" \
  -d '{
    "prompt_id": "<id from step 3>",
    "input": "Where is my order?",
    "expected_behavior": "Acknowledge the concern, ask for order number, offer to help track"
  }'
```

**5. Open the dashboard**

Navigate to `http://localhost:5173`.

**6. Run the evaluation pipeline**

Select a prompt, click **Run evaluation** to invoke the judge, then **Check locale** to run i18n checks. The verdict panel shows `CAN SHIP` or `BLOCKED` with an itemized reasons list.

## API reference

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Health check — returns `ai_mock` and `model` env vars |
| POST | `/v1/generate` | Call LLM with prompt, run moderation pass, store Run row |
| GET | `/v1/prompts` | List all prompt names with latest version number |
| POST | `/v1/prompts` | Create new prompt version (auto-increments per name) |
| GET | `/v1/prompts/{name}/history` | Full version history for a prompt, ordered by version |
| GET | `/v1/golden-sets/{prompt_id}` | List golden set entries for a prompt |
| POST | `/v1/golden-sets` | Add a golden test case |
| POST | `/v1/evaluate/{prompt_id}` | Run judge over all runs for a prompt |
| POST | `/v1/evaluate/run/{run_id}` | Run judge for a single run without touching other runs |
| POST | `/v1/evaluate-locale/{prompt_id}` | Run i18n checks on all runs for a prompt |
| GET | `/v1/locale-checks/{run_id}` | Raw locale check rows for a run (empty list if not yet run) |
| POST | `/v1/evaluate` | Combined verdict — aggregates all signals into `can_ship` |
| GET | `/v1/runs` | Paginated run history with `prompt_name` and `version` |
| GET | `/v1/runs/{id}` | Single run detail |

## CI gate

The workflow in `.github/workflows/eval-gate.yml` runs on any pull request that modifies the `/prompts` directory. It:

1. Starts a Postgres service container and runs Alembic migrations against it
2. Seeds a test prompt and golden set from `ci/golden_prompts.json`
3. Calls `POST /v1/generate` for each test locale
4. Calls `POST /v1/evaluate/{prompt_id}` to score the outputs
5. Calls `POST /v1/evaluate-locale/{prompt_id}` for i18n checks
6. Calls `POST /v1/evaluate` to read the final verdict

If `can_ship` is `False` for any run, the job fails and posts a sticky PR comment with a flat bullet list of reasons. The list is unordered — the order in which reasons are assembled is deterministic but carries no implied severity ranking, so the comment does not frame any one failure as the "primary" cause. The gate runs with `AI_MOCK=true` by default, making it fully reproducible for any contributor without an API key.

The design intent is to treat prompt regressions like code regressions. A change that causes a previously-passing prompt to score below 4.0 or fail a locale check blocks the merge, the same way a failing unit test would.

## What I would build next

**Multi-model support** — the judge and the generator are currently the same model. Separating them (a configurable judge model, independent of the generation model) would let teams use a larger model for evaluation without paying for it on every generation request, and would make it possible to compare judge consistency across models.

**Async evaluation pipeline** — generation and scoring are currently synchronous. Decoupling them with a job queue would let the generate endpoint return immediately and allow the judge to score batches without blocking user requests or tying up request threads.

**Golden set versioning** — golden entries are currently immutable once created. Tracking which version of the golden set produced which scores would make it possible to distinguish a score change caused by a prompt edit from one caused by a change in the evaluation criteria.

**Webhook notifications** — `build_verdict()` already produces a structured reasons list. Adding a webhook on any `can_ship=False` verdict would let teams route blocked-run alerts to Slack or email without polling the dashboard.

**Confidence intervals on judge scores** — judge scores are point estimates from a single LLM call. Running the judge N times per golden entry and reporting variance alongside the mean would surface cases where the judge itself is inconsistent. A score of 4.0 ± 0.1 is a very different signal from 4.0 ± 1.5, and a system reporting only the mean cannot tell them apart.
