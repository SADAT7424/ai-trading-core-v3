# Development Rules

## Build order

Never build out of order. Each stage should be working and tested before the
next begins.

1. **Foundation** (this repo, current state) — repo, Docker, Postgres, Redis,
   config, logging, health checks, CI, basic dashboard shell.
2. **Data Infrastructure** — economic calendar ingestion, market data
   ingestion, normalization, validation, point-in-time storage.
3. **GO OS** — surprise engine, macro regime engine, event risk engine, asset
   impact engine, cross-asset engine, AI macro analyst.
4. **Market Core** — market structure, trend, momentum, volatility, liquidity,
   market regime classification.
5. **Trading Core** — strategy definitions, signal engine, confluence,
   opportunity engine.
6. **Risk** — position sizing, portfolio heat, exposure/correlation limits,
   event locks, daily loss limits, kill switch.
7. **Execution** — broker adapter interface, order manager, slippage/latency
   monitoring. (No live broker connected until this stage, and even then,
   paper mode first.)
8. **Position Management** — trade thesis tracking, stops, targets, trailing,
   partial exits, exit engine.
9. **Research** — historical replay, backtester, walk-forward validation,
   Monte Carlo, performance attribution.
10. **Memory** — trade/event/regime memory, knowledge graph.
11. **Learning** — calibration, error analysis, champion/challenger, drift
    detection.
12. **Live** — Backtest → Paper → Shadow → Controlled Live → Production, in
    that order, never skipping a stage.

## Definition of "done" for a stage

- Code is type-checked, linted, and passes CI.
- Unit tests exist for every new calculation or decision rule.
- Integration tests exist for every new boundary between modules.
- Anything risk-related has an explicit test that tries to break it.
- Docs under `docs/` reflect what was actually built.
- No TODOs left in code that silently change behavior (e.g. `# TODO: add risk
  check`) — either the check exists or the feature isn't merged.

## Never do this

- Never build every layer at once and "hope it works." Build → unit test →
  integrate → validate → (once relevant) backtest → continue.
- Never let AI-generated code touch risk limits, kill-switch logic, or order
  placement without deterministic validation and a corresponding test.
- Never connect development code to a live trading account. Environments are
  fully separated (see `docs/ARCHITECTURE.md`).
- Never introduce infrastructure (Kafka, Kubernetes, a dedicated vector DB, a
  dedicated graph DB, multiple brokers, multiple AI providers) before the
  stage that actually requires it.

## Testing checklist for new code

- [ ] Unit tests for pure calculations
- [ ] Integration test for the module boundary it sits on
- [ ] For anything risk/order-related: a test that deliberately violates a
      limit and asserts rejection
- [ ] Structured log lines added for anything that could need debugging later
- [ ] Docs updated
