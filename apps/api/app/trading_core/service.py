"""
Trading Core — service layer. Combines Stage 3's macro regime and Stage 4's
market state into a single opportunity assessment. This is the first place
in the system where "should I actually consider a trade" gets answered —
per AGENTS.md, still entirely deterministic, no AI involved.
"""
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.orm import Session

from app.go_os.macro.repository import SeriesNotIngestedError
from app.go_os.macro.service import compute_macro_regime_snapshot
from app.market_core.repository import NoMarketDataError
from app.market_core.service import compute_market_state
from app.trading_core.calculations import (
    Direction,
    OpportunityScore,
    PullbackSetup,
    TradeClassification,
    classify_trade,
    compute_opportunity_score,
    detect_trend_pullback,
)

# Only XAUUSD has a macro model behind it right now (Stage 3 is gold-specific
# via the master plan's Gold-Specific Intelligence Model, section 5.15).
# Other symbols would need their own asset-impact mapping before this
# service could reasonably assess them — deliberately not guessed at here.
SUPPORTED_SYMBOLS = {"XAUUSD"}


class UnsupportedSymbolError(Exception):
    def __init__(self, symbol: str) -> None:
        self.symbol = symbol
        super().__init__(
            f"'{symbol}' has no macro model yet — only {sorted(SUPPORTED_SYMBOLS)} "
            f"are supported by Trading Core so far."
        )


@dataclass
class OpportunitySnapshot:
    symbol: str
    interval: str
    as_of: datetime
    latest_close: float
    setup: PullbackSetup
    classification: TradeClassification
    gold_macro_score: int
    score: OpportunityScore | None  # None when no setup is currently detected


def compute_opportunity(db: Session, symbol: str, interval: str = "1day") -> OpportunitySnapshot:
    if symbol not in SUPPORTED_SYMBOLS:
        raise UnsupportedSymbolError(symbol)

    market_state = compute_market_state(db, symbol, interval)
    macro_snapshot = compute_macro_regime_snapshot(db)

    setup = detect_trend_pullback(
        trend=market_state.trend,
        momentum=market_state.momentum,
        latest_close=market_state.latest_close,
        sma_fast=market_state.sma_fast,
    )

    classification = classify_trade(setup.direction, macro_snapshot.gold_score.total)

    score: OpportunityScore | None = None
    if setup.direction is not Direction.NONE:
        score = compute_opportunity_score(
            direction=setup.direction,
            technical_score=setup.technical_score,
            gold_macro_score=macro_snapshot.gold_score.total,
            volatility=market_state.volatility,
        )

    return OpportunitySnapshot(
        symbol=symbol,
        interval=interval,
        as_of=market_state.as_of,
        latest_close=market_state.latest_close,
        setup=setup,
        classification=classification,
        gold_macro_score=macro_snapshot.gold_score.total,
        score=score,
    )


# Re-exported so API endpoints can catch these without importing from three
# different submodules.
__all__ = [
    "OpportunitySnapshot",
    "UnsupportedSymbolError",
    "SeriesNotIngestedError",
    "NoMarketDataError",
    "compute_opportunity",
]
