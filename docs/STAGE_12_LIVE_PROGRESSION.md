# Stage 12 — Live Progression

Unlike Stages 1–11, this is not something to build. It's a decision
process — the master plan is explicit that capital deployment must be
staged (section 4.10): **Backtest → Paper → Shadow → Controlled Live →
Production**, never skipping a stage. This document exists so that
decision is made deliberately, later, against real criteria — not on
impulse, and not by default just because the code exists.

**Where RAH OS is today: Paper.** Every order this system has ever placed
is simulated (`broker: "PAPER"` on every single Order row — see
`app/execution/paper_broker.py`). There is no real broker adapter anywhere
in this codebase, and building one is a distinct, separate decision from
anything covered here.

## The stages, and what each one actually means

1. **Backtest** — historical replay only (Stage 9). Tells you whether a
   strategy *could* have worked. Says nothing about whether it will keep
   working, or whether it's resilient to real-world friction.
2. **Paper** — where this system is now. Real market data, real macro
   data, simulated fills, simulated money. Proves the *pipeline* works
   end-to-end. Says relatively little yet about the *strategy's* edge,
   since paper trading removes real slippage, real emotion, and real
   liquidity constraints.
3. **Shadow** — not yet built. The system would generate real signals in
   real time and log what it *would* have done, without placing any order
   at all, paper or real. This catches timing/data issues that only show
   up when a strategy runs continuously in real time rather than in a
   backtest's clean historical replay.
4. **Controlled Live** — real money, deliberately small, usually with a
   tight, separate risk budget from the eventual target — e.g., risking
   real cents or a few dollars per trade, specifically to observe real
   broker behavior (real slippage, real spread, real fills) without
   meaningful capital at risk.
5. **Production** — real money, at the position sizing the risk
   configuration is actually designed for.

## Criteria to consider before moving from Paper toward Shadow

None of these are hard-coded checks in the software — they're judgment
calls a person makes, informed by the numbers the system now provides:

- **Sample size**: `GET /api/v1/performance/summary` — how many *completed*
  trades exist? A handful of trades proves nothing either way; the master
  plan's own philosophy throughout has been "one thing tested well beats
  many things tested shallowly." The same applies to trusting a track
  record.
- **Backtest correspondence**: does live paper performance
  (`/api/v1/performance/summary`) look roughly consistent with the
  historical backtest (`/api/v1/research/backtest/{symbol}`)? A large,
  persistent gap between the two is worth understanding before trusting
  either.
- **Calibration**: `GET /api/v1/learning/calibration` — are better-graded
  setups actually winning more often? If grades are inverted or
  uninformative, the scoring rubric needs revisiting before it's trusted
  with more capital or more autonomy.
- **Discipline check**: has the kill switch or a risk limit ever needed to
  fire for real (not just in a test)? If so, did it work correctly, and
  was the reason understood?
- **Time, not just trade count**: has the system been observed across more
  than one kind of market condition (trending, ranging, high volatility —
  visible via `/api/v1/market/state/{symbol}`)? A strategy that's only
  ever been tested in one regime hasn't really been tested.

## What this document deliberately does not do

It does not set a specific number of trades, a specific win rate, or a
specific date. Those would be false precision — a made-up threshold is not
actually safer than an honest "not yet," and this project's whole
discipline has been refusing to fabricate numbers that don't come from
real data or real reasoning. When the numbers above look genuinely
convincing, that is itself the signal to have this conversation again —
not to write code, but to decide.
