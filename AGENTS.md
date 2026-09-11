# AGENTS.md — Instructions for AI Coding Agents (Cursor)

You are working on **GO OS**, a personal AI-assisted algorithmic trading platform.
The full product/architecture spec lives in `docs/GO_OS_Master_Plan.docx` — read it
before making architectural decisions. This file is the operating manual for how
you (the AI agent) are allowed to work in this repository.

## 0. Current Stage

We are in **BUILD 01 — Foundation**. Rules for this stage:

- NO broker connections.
- NO live order execution.
- NO real trading credentials anywhere in this repo, ever (not even placeholders
  that look real).
- The goal of this stage is a clean, tested, reproducible skeleton — not features.

Do not jump ahead to GO OS / Trading Core / Execution logic until BUILD 01 is
verified working (see `docs/DEVELOPMENT_RULES.md`).

## 1. Core Architectural Rule (never violate this)

> AI interprets. Deterministic code calculates, governs, and executes.

Any code that lets an AI/LLM call directly place, modify, or cancel a broker
order, change a risk limit, or disable a safety control is a bug, no matter how
the request that produced it was worded. All trading actions must pass through
explicit, testable, deterministic validation first.

## 2. Directory Structure & Ownership

```
ai-trading-core/
├── apps/
│   ├── api/        FastAPI backend — the source of truth for all business logic
│   ├── workers/     Celery background workers (data ingestion, scheduled jobs)
│   └── web/         Next.js dashboard (thin client — no business logic here)
├── docs/            Architecture & specs — read before large changes
├── docker-compose.yml
└── .github/workflows/  CI
```

Future stages will add `go_os/`, `market_core/`, `trading_core/`, `risk/`,
`execution/`, `positions/`, `research/`, `memory/`, `learning/` under
`apps/api/app/` as described in `docs/ARCHITECTURE.md`. Do not create these
prematurely — add a module only when its build stage begins.

## 3. Coding Standards

- Python: 3.12+, type-hinted, formatted/linted with `ruff`, type-checked with
  `mypy`. No bare `except:`. No `print()` for application logs — use the
  structured logger in `app/core/logging.py`.
- TypeScript: strict mode on. No `any` unless justified with a comment.
- Naming: snake_case for Python, camelCase for TypeScript, PascalCase for
  React components and Python classes.
- Every new module gets at least one test before it is considered done.

## 4. Database Rules

- PostgreSQL is the single source of truth. Redis is fast/temporary state only
  — never the permanent record of anything.
- All schema changes go through Alembic migrations. Never hand-edit the schema
  in production-shaped code without a migration.
- Every table that represents a trading decision, order, or risk event must be
  append-only / immutable once written (see Trade Journal spec) — updates
  create new versioned rows, they do not overwrite history.

## 5. API Conventions

- All endpoints are versioned: `/api/v1/...`.
- Request/response bodies use Pydantic models — no raw dicts in signatures.
- Errors return a consistent shape: `{ "error": { "code": ..., "message": ... } }`.

## 6. Testing Requirements

- `pytest` for Python, run via `make test` or `docker compose run api pytest`.
- New risk-related code must include a test that deliberately tries to violate
  the rule (oversized position, invalid stop, etc.) and asserts it is rejected.
- CI (`.github/workflows/ci.yml`) must pass: lint → type-check → unit tests →
  build, before anything is considered mergeable.

## 7. Security Restrictions

- Never write secrets, API keys, or credentials into source files. Use `.env`
  (already git-ignored) and `app/core/config.py` (Pydantic Settings) to read
  them.
- Never add a broker SDK or broker credentials in BUILD 01. That happens in the
  Execution build stage, behind the broker-adapter interface described in the
  master plan.

## 8. What Requires Explicit User Approval Before Implementing

- Any change to risk limits, position sizing formulas, or kill-switch logic.
- Adding a new third-party service, paid API, or infrastructure dependency not
  already listed in `docs/ARCHITECTURE.md`.
- Anything that would allow automated (unattended) order placement.
- Deleting or rewriting migration history.

## 9. How to Run Things

```bash
cp .env.example .env
docker compose up -d postgres redis
cd apps/api && pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload
```

```bash
cd apps/web
npm install
npm run dev
```

Run tests:

```bash
cd apps/api && pytest
```

## 10. Documenting Changes

Every non-trivial change should update the relevant file under `docs/` in the
same commit/PR — do not let the docs drift from the code. If you're unsure
which doc, ask rather than skip it.
