# Architecture

This is the target architecture for GO OS. It is built incrementally — do not
create modules for stages that haven't started. See `docs/DEVELOPMENT_RULES.md`
for the build order.

## Target repository layout (grows over time)

```
ai-trading-core/
├── apps/
│   ├── api/
│   │   └── app/
│   │       ├── core/          config, logging, security
│   │       ├── db/            session, base models
│   │       ├── models/        SQLAlchemy models
│   │       ├── api/v1/        FastAPI routers
│   │       ├── go_os/         [Stage 3] macro intelligence
│   │       │   ├── calendar/
│   │       │   ├── surprise/
│   │       │   ├── macro/
│   │       │   ├── impact/
│   │       │   ├── event_risk/
│   │       │   ├── news/
│   │       │   ├── geopolitical/
│   │       │   ├── cross_asset/
│   │       │   └── ai/
│   │       ├── market_core/   [Stage 4] structure, trend, momentum, volatility, liquidity, regime
│   │       ├── trading_core/  [Stage 5] strategies, signals, confluence, opportunities
│   │       ├── portfolio/     [Stage 6] allocation, exposure, correlation
│   │       ├── risk/          [Stage 6] limits, governance, permissions, kill_switch
│   │       ├── execution/     [Stage 7] broker adapters, orders, slippage, monitoring
│   │       ├── positions/     [Stage 8] management, thesis, stops, targets, exits
│   │       ├── research/      [Stage 9] backtesting, walk_forward, monte_carlo
│   │       ├── memory/        [Stage 10] structured, semantic, graph, temporal
│   │       └── learning/      [Stage 11] performance, errors, calibration, drift
│   ├── workers/        Celery workers (data ingestion, scheduled jobs, AI analysis)
│   └── web/            Next.js dashboard
├── database/           Alembic migrations live under apps/api/alembic
├── docker/
├── docs/
└── .github/workflows/
```

## Request flow (current stage)

```
Browser (Next.js)  →  FastAPI (/api/v1/...)  →  PostgreSQL
                                              ↘  Redis (cache/state)
```

## Request flow (target, once GO OS + Trading Core exist)

```
External Data → Ingestion/Validation → GO OS (macro) → Market Core → Fusion
→ Strategy Engine → Opportunity Engine → Portfolio → Risk Governance
→ Execution → Position Manager → Exit → Trade Analytics → Memory/Learning
```

## Provider Adapter Pattern

Data providers and brokers are always accessed through an interface, never
called directly from business logic:

```
GO OS → Provider Interface → [Provider A | Provider B | Provider C]
Execution Engine → Broker Interface → [Broker A | Broker B]
```

This is not implemented yet in BUILD 01 (there are no external providers or
brokers wired up), but new integrations must follow this pattern from the
first line of code.

## Environments

`development`, `testing`, `paper`, `shadow`, `production` — each with separate
databases, credentials, and configuration. BUILD 01 only implements
`development` and `testing`.

## Full specification

The complete product and architecture specification — GO OS macro
intelligence, trading core, risk governance, execution, position management,
trade journal, memory/learning, and the full technology stack — is in
`docs/GO_OS_Master_Plan.docx`. This file is a working summary for engineering
use; the master plan is the source of truth for product decisions.
