"""
Paper broker adapter — the ONLY broker adapter in this codebase.

Per the master plan (section 10.10): "Paper trading must use real market
prices — never fabricated data." This adapter fills orders against the most
recent REAL ingested price bar (Stage 4/Twelve Data), with a small simulated
spread — it never invents a price.

Limitation, stated plainly: this build only ingests daily bars, so paper
fills use the latest daily close as the reference price, not a live tick.
Intraday paper-trading realism (real-time quotes, true bid/ask) is a
natural improvement once intraday ingestion exists — not pretended here.

There is no real broker adapter anywhere in this codebase. Adding one is a
deliberate, separate decision for later — see AGENTS.md section 7/8.
"""
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.execution.broker_base import BrokerAdapter, FillResult
from app.market_core.repository import get_recent_bars


class NoPriceDataError(Exception):
    def __init__(self, symbol: str) -> None:
        super().__init__(f"No price data available for {symbol} — cannot simulate a fill.")


@dataclass
class PaperBrokerAdapter(BrokerAdapter):
    db: Session
    interval: str = "1day"
    spread_bps: float = 2.0  # 0.02% — a reasonable illustrative gold spread, not calibrated

    def place_market_order(self, symbol: str, direction: str, units: float) -> FillResult:
        bars = get_recent_bars(self.db, symbol, self.interval, limit=1)
        if not bars:
            raise NoPriceDataError(symbol)

        reference_price = float(bars[-1].close)
        half_spread = reference_price * (self.spread_bps / 10_000) / 2

        # A LONG buys at the (simulated) ask, a SHORT sells at the
        # (simulated) bid — the spread always works against the trader,
        # same as in reality.
        filled_price = (
            reference_price + half_spread if direction == "LONG" else reference_price - half_spread
        )

        return FillResult(
            filled_price=round(filled_price, 6),
            filled_at=datetime.now(UTC),
            broker_order_id=f"PAPER-{bars[-1].id[:8]}-{int(datetime.now(UTC).timestamp())}",
        )
