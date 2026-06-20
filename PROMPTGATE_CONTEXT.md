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

### Fail-Closed Moderation
Any error or ambiguity during the moderation pass defaults to `blocked=True`. Never defaults to allowed. If the moderation LLM call fails, the run is blocked.

### Prompt Versioning
Every change to a prompt template creates a new row with an incremented version number. Old versions are never mutated. History is queryable via GET /v1/prompts/{name}/history.

**"Latest" version resolution**: `MAX(version)` for that `name`, not `MAX(created_at)`. Timestamps are an audit trail, not an ordering contract — they diverge if a row is inserted out of order (backup restore, manual test patch). Version numbers are the defined meaningful ordering.

**Missing `prompt_name` → 404, not 422**: 422 means the value is inherently invalid (e.g. unsupported locale `zh-CN` will never exist). 404 means the resource doesn't exist yet — a valid `prompt_name` like `"support-reply"` could exist tomorrow. Same REST semantics as any resource lookup.

### Babel for i18n
Python Babel is used for locale-correct date/number formatting checks. Battle-tested vs hand-rolled. Checks: date format correct for locale, number format (decimal/grouping separators), RTL marker for ar-SA.

### Combined Verdict
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

### Step 3 — PostgreSQL + Prompt Versioning
Add DB layer. Store prompts and runs. Prompt versioning logic.
- `app/db.py`: SQLAlchemy models
- `alembic/`: migrations
- `GET /v1/prompts/{id}/history`

### Step 4 — Golden Set + LLM-as-Judge
Add test cases. Judge scores output 1–5 against expected behavior.
- `app/evaluator.py`: `judge(run_id) -> float`
- `POST /v1/golden-sets`
- `POST /v1/evaluate/{prompt_id}`

### Step 5 — Moderation Pass (Fail-Closed)
Separate moderation LLM call. Fail-closed: any error = blocked.
- `app/moderator.py`: `moderate(output: str) -> (bool, str)`
- Adds `blocked`, `block_reason` to runs

### Step 6 — i18n Checks (Babel)
Locale correctness for en-US, ar-SA, ja-JP, de-DE, fr-FR.
- `app/locale_checker.py`: check date format, number format, RTL
- `POST /v1/evaluate-locale/{prompt_id}`
- `locale_checks` table populated

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
- [ ] Step 3: PostgreSQL + prompt versioning
- [ ] Step 4: Golden set + LLM-as-judge
- [ ] Step 5: Moderation pass
- [ ] Step 6: i18n checks
- [ ] Step 7: Combined verdict
- [ ] Step 8: Frontend + CI gate
