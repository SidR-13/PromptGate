# PromptGate — Project Context

## What Is This?

PromptGate is an LLM output evaluation, moderation, and internationalization gating system. It wraps LLM calls and answers one question before any AI output ships to production: **"is this safe and correct to ship?"**

Portfolio project demonstrating AI infrastructure engineering skills:
- LLM-as-judge evaluation pattern
- Fail-closed content moderation
- Prompt versioning and history
- Internationalization (i18n) correctness checks
- Combined `can_ship` verdict aggregation
- GitHub Actions CI gate

---

## Repository

`github.com/SidR-13/PromptGate`

---

## Tech Stack

| Layer      | Technology                              |
|------------|-----------------------------------------|
| Backend    | Python 3.11, FastAPI                    |
| LLM        | Claude API (Anthropic) — `claude-haiku-4-5` |
| Database   | PostgreSQL 16                           |
| Frontend   | React + TypeScript + Vite + Tailwind CSS + Recharts |
| DevOps     | Docker Compose                          |
| CI/CD      | GitHub Actions                          |
| i18n       | Python Babel (battle-tested locale formatting) |

---

## Folder Structure

```
D:\Portfolio Projects\PromptGate\
├── PROMPTGATE_CONTEXT.md          ← this file
├── promptgate-backend/
│   ├── app/
│   │   ├── main.py                ← FastAPI app entry
│   │   ├── llm.py                 ← call_llm(), mock support
│   │   ├── db.py                  ← SQLAlchemy models + session
│   │   ├── evaluator.py           ← judge(), golden set scoring
│   │   ├── moderator.py           ← fail-closed moderation pass
│   │   ├── locale_checker.py      ← Babel i18n checks
│   │   ├── verdict.py             ← build_verdict(), can_ship logic
│   │   └── routers/
│   │       ├── generate.py
│   │       ├── prompts.py
│   │       ├── golden_sets.py
│   │       ├── evaluate.py
│   │       └── runs.py
│   ├── alembic/                   ← DB migrations
│   ├── tests/
│   ├── requirements.txt
│   ├── Dockerfile
│   └── .env.example
├── promptgate-frontend/
│   ├── src/
│   │   ├── components/
│   │   ├── pages/
│   │   └── api/
│   ├── package.json
│   ├── tsconfig.json
│   └── vite.config.ts
├── docker-compose.yml
├── .github/
│   └── workflows/
│       └── eval-gate.yml          ← CI gate blocks PRs on eval regression
└── .gitignore
```

---

## Database Schema

### `prompts`
| Column     | Type      | Notes                          |
|------------|-----------|--------------------------------|
| id         | UUID PK   |                                |
| name       | TEXT      | human-readable identifier      |
| version    | INTEGER   | auto-incremented per name      |
| template   | TEXT      | the prompt template text       |
| created_at | TIMESTAMP |                                |

### `runs`
| Column         | Type      | Notes                              |
|----------------|-----------|------------------------------------|
| id             | UUID PK   |                                    |
| prompt_id      | UUID FK   | → prompts.id                       |
| input          | TEXT      | user-provided variable values      |
| output         | TEXT      | LLM response                       |
| locale         | TEXT      | e.g. "en-US"                       |
| score          | FLOAT     | 1–5 from judge                     |
| judge_reasoning| TEXT      |                                    |
| blocked        | BOOLEAN   | from moderation pass               |
| block_reason   | TEXT      |                                    |
| created_at     | TIMESTAMP |                                    |

### `golden_sets`
| Column            | Type      | Notes                          |
|-------------------|-----------|--------------------------------|
| id                | UUID PK   |                                |
| prompt_id         | UUID FK   | → prompts.id                   |
| input             | TEXT      | test input                     |
| expected_behavior | TEXT      | what a good response looks like|
| created_at        | TIMESTAMP |                                |

### `locale_checks`
| Column     | Type      | Notes                                    |
|------------|-----------|------------------------------------------|
| id         | UUID PK   |                                          |
| run_id     | UUID FK   | → runs.id                                |
| locale     | TEXT      | e.g. "ar-SA"                             |
| check_type | TEXT      | "date_format", "number_format", "rtl"    |
| passed     | BOOLEAN   |                                          |
| details    | TEXT      | human-readable explanation               |
| created_at | TIMESTAMP |                                          |

---

## API Endpoints

| Method | Path                          | Purpose                                      |
|--------|-------------------------------|----------------------------------------------|
| POST   | /v1/generate                  | Call LLM with a prompt, store run            |
| GET    | /v1/prompts/{id}/history      | Prompt version history                       |
| POST   | /v1/golden-sets               | Add a golden test case                       |
| POST   | /v1/evaluate/{prompt_id}      | Run LLM-as-judge over golden set             |
| POST   | /v1/evaluate-locale/{prompt_id}| Run i18n checks on a prompt                 |
| POST   | /v1/evaluate                  | Combined verdict → `can_ship`                |
| GET    | /v1/runs                      | Paginated run history                        |
| GET    | /v1/runs/{id}                 | Single run detail                            |

---

## Key Engineering Decisions

### LLM-as-Judge Pattern
Use Claude to grade Claude's own output against golden test cases. Judge scores 1–5. Score ≥ 4 = pass, < 4 = fail. Judge sees the prompt template, the test input, the expected behavior, and the actual output.

**Judge failure handling:** If `judge()` raises (e.g. `ValueError` from `call_llm_json` on non-JSON output), the exception is caught inside the evaluate endpoint and the run is updated with `score=0.0, judge_reasoning="judge call failed: {error}"`. Score is never left NULL after an evaluation attempt.

`NULL score` is reserved exclusively for "evaluation not yet run on this row." This keeps `build_verdict()` (Step 7) to a single code path: `score < 4` → fail, no NULL special-casing required. Writing an explicit 0 on failure is consistent with the fail-closed philosophy — an error is a definite failing result, not an unknown state.

### Fail-Closed Moderation
Any error or ambiguity during the moderation pass defaults to `blocked=True`. Never defaults to allowed. If the moderation LLM call fails, the run is blocked.

### Prompt Versioning
Every change to a prompt template creates a new row with an incremented version number. Old versions are never mutated. History is queryable via GET /v1/prompts/{name}/history.

**"Latest" version resolution**: `MAX(version)` for that `name`, not `MAX(created_at)`. Timestamps are an audit trail, not an ordering contract — they diverge if a row is inserted out of order (backup restore, manual test patch). Version numbers are the defined meaningful ordering.

**Missing `prompt_name` → 404, not 422**: 422 means the value is inherently invalid (e.g. unsupported locale `zh-CN` will never exist). 404 means the resource doesn't exist yet — a valid `prompt_name` like `"support-reply"` could exist tomorrow. Same REST semantics as any resource lookup.

### Babel for i18n
Python Babel is used for locale-correct date/number formatting checks. Battle-tested vs hand-rolled. Checks: date format correct for locale, number format (decimal/grouping separators), RTL marker for ar-SA.

### Combined Verdict
**Confirmed before implementation:** `Run.locale` is a single string field — a run is generated in exactly one locale, never multiple. So "all locale checks pass" for a run means all `LocaleCheck` rows sharing that `run_id` passed (typically 2–3 rows: date_format, number_format, optionally rtl) — there is no second "across 5 locales" layer per run, because a run can't have 5 locales.

There is no pre-aggregated `locale_passed` field anywhere in the schema — no such column exists on `Run`. The only place locale results live is the raw `locale_checks` table. `build_verdict(run_id)` queries it directly: `any LocaleCheck row for this run_id with passed=False → block`. There's no cached summary field it could read from instead, because none was ever created — this was a deliberate choice carried over from the Step 4 averaging bug: the moment you give a fail-closed system a pre-aggregated number to consume instead of the raw signal, dilution bugs become possible again. `build_verdict()` always reads raw rows from `judge()`, `moderate()`, and `locale_checker` results, never a cached verdict.

`build_verdict(run_id)` aggregates:
- `eval_score`: judge score (1–5)
- `blocked`: from moderation
- `block_reason`: why blocked (if applicable)
- `locale_results`: per-locale check results
- `can_ship`: True only if score ≥ 4 AND blocked == False AND all locale checks pass

### AI_MOCK Pattern
Same pattern as CodeSentinel. `AI_MOCK=true` returns deterministic mock responses. `AI_MOCK=false` calls real Claude API. All development uses mock mode.

---

## Environment Variables

```bash
ANTHROPIC_API_KEY=                          # real key, only used when AI_MOCK=false
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/promptgate
AI_MOCK=true                                # ALWAYS true during development
CLAUDE_MODEL=claude-haiku-4-5               # ALWAYS haiku during development
```

---

## STRICT Cost Rules

- `AI_MOCK=true` during ALL development work
- Only switch to real API calls for final end-to-end testing, maximum 20 real API calls total
- Always use `claude-haiku-4-5`, never sonnet, during development
- Cache golden set results aggressively — never re-run an identical test
- For locale checks, mock 4 of 5 locales and only test 1 locale with real API to verify the pattern works

---

## Git Rules

- Never add Co-Authored-By or AI attribution to commits
- Commit in logical batches matching the 8 steps below
- Push after each step is confirmed working

---

## Build Steps (8 Batches)

### Step 1 — `call_llm(prompt, locale) -> str` ✅
Simple standalone script. No web framework. Calls Claude API with mock support. Test from command line.
- `app/llm.py`: `call_llm(prompt: str, locale: str) -> str`
- Mock: returns canned response when `AI_MOCK=true`
- Real: uses `anthropic` Python SDK, `claude-haiku-4-5`
- `call_llm_json()`: wraps `call_llm`, strips markdown fences, parses JSON, raises `ValueError` on failure

**Bugs caught and fixed during Step 1:**

1. **Mock responses were all "perfectly correct" (silent test trap)**
   - Original mocks for all 5 locales returned well-formed, locale-correct output.
   - Problem: Step 6's i18n checker would always pass in dev — you'd never know the checker was broken until live.
   - Fix: Introduced intentional defects in two locales so the checker has real failures to catch:
     - `ar-SA`: plain Arabic text with no RTL Unicode control characters (`\u202B` / `\u200F`) — Step 6 RTL check should flag this
     - `ja-JP`: Western date format `"June 20, 2026"` instead of `2026年6月20日`, and `1234.56` instead of `¥1,234,560` — Step 6 date/number checks should flag these
   - `en-US`, `de-DE`, `fr-FR` remain correct, giving a realistic mix of pass and fail.

2. **`call_llm_json()` silently returned `{"parse_error": True}` on bad JSON**
   - Original behavior: if the LLM returned non-JSON garbage, the function returned a dict with a `parse_error` key.
   - Problem: Step 4 (judge) and Step 5 (moderation) both consume this helper. A silent dict that looks like a result would produce false-passing eval scores with no visible error.
   - Fix: Now raises `ValueError` with the raw output in the message, so callers fail loudly instead of silently scoring wrong.

### Step 2 — FastAPI + Docker ✅
Wrap `call_llm` in `POST /v1/generate`. Run in Docker Compose with hot reload.
- `app/main.py`: FastAPI app, CORS middleware for Vite dev server, `/health` endpoint
- `app/routers/generate.py`: `POST /v1/generate` — validates locale against supported set, returns `{ output, locale }`
- `Dockerfile`: `python:3.11-slim`, uvicorn with `--reload` for development
- `docker-compose.yml`: backend + postgres:16-alpine, postgres healthcheck gates backend startup, `pgdata` volume

**Validation behaviour:**
- Unsupported locale → 422 with list of valid locales
- Empty prompt → 422 (Pydantic `min_length=1`)
- `/health` exposes `ai_mock` and `model` env vars for easy ops visibility

**Bugs caught and fixed during Step 2:**

1. **`GenerateRequest` was still taking raw `prompt: str` after response was fixed (request/response mismatch)**
   - Response was updated with `run_id`, `prompt_id`, `version` but the request still took a raw string with no `prompt_name`.
   - Problem: without `prompt_name` in the request, Step 3 has nothing to look up in the `prompts` table — `prompt_id` and `version` would stay `None` forever even with a live DB.
   - Fix: `GenerateRequest` now takes `prompt_name: str`, `version: Optional[int]` (None = latest), `input: str`, `locale: str`. The old `prompt` field is actively rejected (422). Step 3 just adds the DB lookup; no contract change.

2. **`GenerateResponse` was missing `run_id`, `prompt_id`, `version` (pre-Step 3 shape mismatch)**
   - Original response only returned `output` and `locale`.
   - Problem: Step 3 needs all four fields to log a DB row. Retrofitting them after Postgres is wired would mean touching the Pydantic models, the router, and the DB-insert code simultaneously — too many moving parts at once.
   - Fix: Added `run_id`, `prompt_id`, `version` as `Optional[UUID/int] = None` to `GenerateResponse` now. Step 3 just fills them in; the response contract never changes.

2. **Schema decisions locked in before Step 3 to prevent mid-build pivots**
   - `prompts` table: `UNIQUE(name, version)` constraint, not just a bare `id`. `GET /v1/prompts/{name}/history` groups by `name`.
   - `runs.prompt_id`: FK to `prompts.id` (UUID of the exact version row), not just the name. Required for "did v3 regress vs v2" comparisons in Steps 7/8.
   - Migrations: Alembic — set up once, all future tables added with one command per step.

3. **httpx/Starlette version deprecation warning**
   - `FastAPI.testclient` emits `StarletteDeprecationWarning` when used with the current `httpx` version; suggests installing `httpx2`.
   - Not a bug in our code — a version mismatch in the local test environment. Tests pass and behaviour is correct.
   - No fix applied: this only affects the local test runner, not Docker or production. Will resolve naturally when `httpx2` adoption stabilises.

### Step 3 — PostgreSQL + Prompt Versioning ✅
Add DB layer. Store prompts and runs. Prompt versioning logic.
- `app/config.py`: Pydantic-settings; `DATABASE_URL`, `AI_MOCK`, `CLAUDE_MODEL`, `ANTHROPIC_API_KEY`
- `app/db.py`: SQLAlchemy engine (pool settings guarded — SQLite doesn't accept `pool_size`/`max_overflow`), `get_db` dependency
- `app/models.py`: `Prompt` (id, name, version, template, created_at) + `Run` (id, prompt_id FK, input, output, locale, score, judge_reasoning, blocked, block_reason, created_at); `UNIQUE(name, version)`
- `alembic/versions/001_initial_schema.py`: initial migration; `DATABASE_URL` read from env in `env.py` so no editing `alembic.ini` in Docker
- `app/routers/prompts.py`: `POST /v1/prompts` (auto-increments version via `MAX(version)+1`), `GET /v1/prompts/{name}/history` (ordered by version asc, 404 if name unknown)
- `app/routers/runs.py`: `GET /v1/runs` (paginated, desc by created_at), `GET /v1/runs/{id}` (404 on miss)
- `app/routers/generate.py`: full DB wiring — resolves prompt by `MAX(version)` (not `MAX(created_at)`), renders `{input}` placeholder in template, stores Run row, returns `run_id`/`prompt_id`/`version` in response

**Implementation notes:**

- `POST /v1/generate` full wiring: `_resolve_prompt()` → `_render_template()` → `call_llm()` → `Run(...)` insert → `db.commit()` → response carries real `run_id`, `prompt_id`, `version` (not None). Confirmed by test: DB row written and UUID returned.
- `POST /v1/prompts` race condition: two concurrent requests for the same name both read the same `MAX(version)` and attempt to insert the same version. The `UNIQUE(name, version)` constraint raises `IntegrityError` — fails loudly rather than silently corrupting version ordering. Caller retries. Acceptable for a portfolio project.
- `GET /v1/runs` pagination: `skip=0`, `limit=50` by default; hard cap at `limit=200`. Step 8 dashboard should use these defaults and offer a page control capped at 200.

**Bugs caught and fixed during Step 3:**

1. **`pool_size`/`max_overflow` crash on SQLite (test environment)**
   - `create_engine()` was called with PostgreSQL pool args unconditionally.
   - SQLite uses `SingletonThreadPool` and rejects those kwargs with `TypeError`.
   - Fix: detect `sqlite` prefix in the URL and only pass pool args for non-SQLite engines.

2. **SQLite in-memory tables vanish between connections (StaticPool)**
   - `sqlite:///:memory:` creates a fresh empty database per connection. Without `StaticPool`, the test session creates tables on one connection and the request handler opens a different connection — empty DB, `no such table` error.
   - Fix: `poolclass=StaticPool` forces all connections to share one in-memory database for the duration of the test run.

### Step 4 — Golden Set + LLM-as-Judge ✅
Add test cases. Judge scores output 1–5 against expected behavior.
- `app/models.py`: added `GoldenSet` (id, prompt_id FK, input, expected_behavior, created_at)
- `alembic/versions/002_add_golden_sets.py`: migration for golden_sets table
- `app/evaluator.py`: `judge(run_id, db)` — scores each golden entry individually via `call_llm_json`, takes the mean; on `ValueError`/`KeyError`/`TypeError` writes `score=0.0, judge_reasoning="judge call failed: {e}"` (never leaves NULL after an evaluation attempt)
- `app/routers/golden_sets.py`: `POST /v1/golden-sets` (404 if prompt missing), `GET /v1/golden-sets/{prompt_id}`
- `app/routers/evaluate.py`: `POST /v1/evaluate/{prompt_id}` — iterates all runs for the prompt, calls `judge()` on each, returns `mean_score`, `passed` (≥4.0), per-run results
- `app/llm.py`: added `MOCK_JSON_TRIGGERS` dict — detects judge/moderator prompts by unique substrings and returns valid mock JSON so `call_llm_json()` never raises in mock mode

**Score column confirmed Float:** judge returns fractional scores (e.g. 3.5, 4.2 possible); `Float` stores them without rounding; threshold `score >= 4.0` works identically to integer comparison.

**Open question for Step 8:** the per-run score from `judge()` is now fail-closed (poisoned to 0.0 on any golden-entry failure — see bug log below), but `POST /v1/evaluate/{prompt_id}`'s batch-level `mean_score`/`passed` still averages across *multiple runs* the same naive way. A CI gate (Step 8) reading that batch `passed` field could still get diluted past the threshold by enough good runs outvoting one poisoned run. Revisit if Step 8's `eval-gate.yml` reads the batch endpoint directly rather than checking individual run scores.

**Bugs caught and fixed during Step 4:**

1. **`judge()` averaged a failed golden-entry score into the mean instead of poisoning the result (fixed retroactively after Step 5)**
   - `_judge_single` clamps legitimate scores to `[1.0, 5.0]`; only its except branch ever returns `0.0`. The original `judge()` summed all scores and divided by count — meaning a single failed judge call (`score=0.0`) could be diluted into a passing mean if enough other golden entries scored well (e.g. 9 entries at 5.0 + 1 failure at 0.0 → mean 4.5, which passes the ≥4.0 threshold despite a real failure).
   - Problem: this directly contradicted `moderate()`'s fail-closed pattern from Step 5 — moderation never averages pass/fail across multiple checks, one block is final. `judge()` was using a different philosophy under the hood, and `build_verdict()` (Step 7) would have silently inherited the inconsistency by reading whichever score `judge()` handed it.
   - Fix: any golden entry with `score == 0.0` (i.e. a judge-call failure, never a legitimate low score since those are clamped to ≥1.0) forces the entire run's final score to `0.0`, regardless of how well other entries scored. Verified with a test: one passing entry (score 4) + one failing entry (score 0, forced via mock) → final score is `0.0`, not the naively-averaged `2.0`.

2. **`call_llm_json` in mock mode always raised `ValueError` for judge/moderator calls**
   - `_mock_response` returned locale text strings unconditionally; any caller expecting JSON would always hit the `ValueError` path.
   - Problem: impossible to test the happy path of `judge()` in mock mode — every evaluation would write `score=0.0, judge_reasoning="judge call failed"`.
   - Fix: `MOCK_JSON_TRIGGERS` dict maps unique prompt substrings (`"EXPECTED BEHAVIOR:"`, `"MODERATION_CHECK:"`) to valid mock JSON strings. The mock detects the caller by prompt content and returns the right shape.

### Step 5 — Moderation Pass (Fail-Closed) ✅
Separate moderation LLM call. Fail-closed: any error = blocked.
- `app/moderator.py`: `moderate(output: str) -> (bool, str)` — catches `ValueError`/`KeyError`/`TypeError` from `call_llm_json` and returns `(True, "moderation check failed: {e}")`. Never fails open.
- Wired directly into `app/routers/generate.py`: every run is moderated at creation time, immediately after `call_llm`, before the `Run` row is inserted. No window where a run exists with unknown moderation status.
- `GenerateResponse` now returns `blocked` and `block_reason` alongside `output` — caller sees moderation status immediately, no separate lookup needed.
- `app/llm.py` mock: `"MODERATION_CHECK:"` trigger (added in Step 4 already) returns `{"blocked": false, "reason": ""}` in mock mode.

**Design decision — HTTP status on block:** `POST /v1/generate` still returns `200` even when `blocked=True`. The request succeeded (a run was generated and stored); moderation is a flag on the result, not a request-level error. This mirrors real moderation pipelines — they annotate content for the caller's decision rather than failing the HTTP call. The `can_ship` gate (Step 7) is where blocking actually prevents shipping, not at generation time.

**Bugs caught and fixed during Step 5:** none — the mock JSON trigger infrastructure built in Step 4 (`MOCK_JSON_TRIGGERS`) already covered the moderation case, so no rework was needed. All 6 test assertions passed on first run, including the fail-closed path (moderation LLM error → `blocked=True` persisted to DB, request still returns 200).

### Step 6 — i18n Checks (Babel) ✅
Locale correctness for en-US, ar-SA, ja-JP, de-DE, fr-FR.
- `app/locale_checker.py`: `run_locale_checks(output, locale)` — three checks, driven by Babel locale data rather than per-locale regex:
  - `check_date_format`: flags English month names appearing in non-English-locale output
  - `check_number_format`: flags numbers ≥1000 with no thousands-grouping separator (years 1000–2999 excluded — see bug log)
  - `check_rtl`: only emitted when `Locale(locale).text_direction == 'rtl'` (Babel-driven, not hardcoded to ar-SA specifically); requires an explicit RTL Unicode control mark
- `app/models.py`: added `LocaleCheck` (id, run_id FK, locale, check_type, passed, details, created_at)
- `alembic/versions/003_add_locale_checks.py`
- `app/routers/evaluate_locale.py`: `POST /v1/evaluate-locale/{prompt_id}` — iterates all runs for the prompt, runs all applicable checks per run, persists every check row, returns per-run breakdown. **All-or-nothing aggregation**: `all_passed` is `True` only if every check on every run passed — booleans don't average, so this stays naturally consistent with `moderate()`'s fail-closed pattern without needing a special rule.

**Babel locale data used to ground the design** (not assumed): confirmed via direct query that `ar_SA`'s correct number format is identical to `en_US` (comma group, period decimal) — only `de_DE`/`fr_FR` differ. This meant the ar-SA mock's ungrouped number (`"1234.56"`, no comma) was an **undocumented extra defect** introduced by accident in Step 1, not the intended single RTL-only defect. Fixed the mock to `"1,234.56"` so ar-SA now fails exactly the one check it was designed to fail.

**Bugs caught and fixed during Step 6 (found via manual verification *before* writing the test suite — each one would have been masked by example-fitting tests):**

1. **Years false-positived as "ungrouped numbers" in every locale**
   - The number-grouping regex matched any 4+ consecutive raw digits, including the year `"2026"` embedded in every mock sentence — nobody groups years (`"2,026"` is never correct).
   - Fix: bare 4-digit integers in the range 1000–2999 are excluded from the grouping check.

2. **The ja-JP date defect — the entire motivating example from Step 1 — was not detected**
   - `\b\d...\b` and `\b(January|...)\b` word-boundary regex silently failed across the CJK/Latin transition. Python's `re` module treats Han/Hiragana characters as `\w`, so there is no word boundary between `は` and `J` in `"会議はJune 20"` — `\b` requires a `\w`/`\W` transition, and both sides are `\w`.
   - This is the same root cause appearing twice: once on the date check (leading boundary) and once on the number check (trailing boundary, between `"1234.56"` and the immediately-following `円` with no space).
   - Fix: dropped `\b` entirely. Date check uses case-sensitive substring match with a negative lookahead (`(?![a-zA-Z])`) to avoid matching inside longer Latin words (e.g. "Juneau"). Number check uses digit-adjacency lookarounds (`(?<!\d)...(?!\d)`) instead of word-boundary lookarounds — only digits matter for that check, so CJK adjacency is irrelevant once `\w` is out of the picture.
   - Caught by running the checker manually against all 5 mocks and inspecting pass/fail *before* writing assertions — writing the test first would have let the test simply encode the (silently wrong) behavior as "expected."

### Step 7 — Combined Verdict
Aggregate all signals into `can_ship` boolean.
- `app/verdict.py`: `build_verdict(run_id)`
- `POST /v1/evaluate` → returns full verdict object

### Step 8 — Frontend Dashboard + CI Gate
React dashboard showing run history, scores, verdict. GitHub Actions blocks PRs if eval degrades.
- `promptgate-frontend/`: React + TypeScript + Vite + Tailwind + Recharts
- `.github/workflows/eval-gate.yml`

---

## Current Status

- [x] PROMPTGATE_CONTEXT.md created
- [x] Step 1: call_llm standalone script — all 5 locale mocks verified, JSON error path raises loudly
- [x] Step 2: FastAPI + Docker — POST /v1/generate, locale validation, health endpoint, Docker Compose with postgres healthcheck
- [x] Step 3: PostgreSQL + prompt versioning — models, Alembic migration, MAX(version) resolution, 404 on missing name, runs endpoints
- [x] Step 4: Golden set + LLM-as-judge — GoldenSet model, judge() with mean scoring, score=0.0 on failure (not NULL), mock JSON trigger detection
- [x] Step 5: Moderation pass — fail-closed moderate(), wired into generate at creation time, blocked/block_reason in response, 200 status even when blocked
- [x] Step 6: i18n checks — Babel-driven date/number/RTL checks, fixed CJK word-boundary bug that masked the ja-JP defect, fixed year false-positive, fixed undocumented ar-SA number defect
- [ ] Step 7: Combined verdict
- [ ] Step 8: Frontend + CI gate
