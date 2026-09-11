# GO OS — AI Trading Core

Personal AI-assisted algorithmic trading platform. Initial focus: XAU/USD (Gold).

> **Status: BUILD 01 — Foundation.** No broker connection, no live trading, no
> real-money execution. This stage establishes a clean, tested, reproducible
> skeleton for everything else described in the master plan.

See `docs/GO_OS_Master_Plan.docx` for the full product/architecture
specification, and **`AGENTS.md`** before making changes with Cursor or any AI
coding agent — it defines what the agent may and may not do in this repo.

## Stack (this stage)

| Layer      | Technology                          |
|------------|--------------------------------------|
| Backend    | Python 3.12 + FastAPI                |
| Database   | PostgreSQL                           |
| Cache/State| Redis                                |
| Workers    | Celery                               |
| Frontend   | Next.js + React + TypeScript         |
| Containers | Docker / Docker Compose              |
| Testing    | Pytest (API), CI via GitHub Actions  |
| Lint/Types | Ruff + MyPy (Python), ESLint + TS strict (web) |

Everything else in the full stack (TimescaleDB, pgvector, an AI gateway,
broker adapters, etc.) is introduced in later build stages — see
`docs/DEVELOPMENT_RULES.md`.

## Quickstart

### 1. Environment

```bash
cp .env.example .env
```

### 2. Infrastructure (Postgres + Redis)

```bash
docker compose up -d postgres redis
```

### 3. Backend API

```bash
cd apps/api
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

Visit http://localhost:8000/docs for the interactive API docs, and
http://localhost:8000/api/v1/system/health for the health check.

### 4. Background workers

```bash
cd apps/workers
pip install -r requirements.txt
celery -A celery_app worker --loglevel=info
```

### 5. Web dashboard

```bash
cd apps/web
npm install
npm run dev
```

Visit http://localhost:3000.

### Or: run everything with Docker Compose

```bash
docker compose up --build
```

## Tests

```bash
cd apps/api
pytest
```

## Project layout

```
ai-trading-core/
├── AGENTS.md              ← read first if you're an AI coding agent
├── docs/                  ← architecture, dev rules, and the full master plan
├── apps/
│   ├── api/                FastAPI backend
│   ├── workers/            Celery background workers
│   └── web/                Next.js dashboard
├── docker-compose.yml
└── .github/workflows/      CI
```

## Roadmap

All 11 code stages are implemented and tested. Stage 12 is a decision
process, not code — see `docs/STAGE_12_LIVE_PROGRESSION.md`.

1. ✅ Foundation — repo, Docker, Postgres, Redis, CI
2. ✅ Data Infrastructure — point-in-time economic (FRED) + price (Twelve Data) ingestion
3. ✅ GO OS — Macro Intelligence Engine (real yield, inflation, policy, USD → gold score)
4. ✅ Market Core (trend, momentum, volatility, RSI)
5. ✅ Trading Core & Strategy Engine (trend-pullback + macro alignment)
6. ✅ Risk Governance (position sizing, hard limits, kill switch, daily loss limit)
7. ✅ Execution Intelligence (paper broker adapter — no real broker, ever, in this build)
8. ✅ Position Management (thesis tracking, hard-stop-always-wins, trailing stops)
9. ✅ Research (point-in-time, look-ahead-free backtesting)
10. ✅ Memory (trade history insights, "similar setups" comparison)
11. ✅ Learning (confidence calibration — are quality grades actually predictive?)
12. 📋 Paper → Shadow → Controlled Live → Production — a real-world decision,
    not a build stage; see `docs/STAGE_12_LIVE_PROGRESSION.md` for the
    criteria to weigh before ever considering it.

RAH OS currently trades **paper only** — there is no real broker adapter
anywhere in this codebase, and adding one would be a distinct, deliberate,
future decision (see Stage 12 doc).
