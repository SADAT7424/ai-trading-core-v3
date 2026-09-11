"""
/api/v1/market/bars — ingestion trigger for price bars.

Symbol is passed WITHOUT a slash (e.g. "XAUUSD") to avoid URL-encoding
headaches in path parameters — the provider adapter translates to its own
format internally (see app/data/providers/twelvedata.py).
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.data.ingestion.market import ingest_bars
from app.data.providers.twelvedata import TwelveDataProvider, TwelveDataProviderError
from app.db.session import get_db

router = APIRouter(prefix="/market/bars", tags=["market"])


class BarIngestResponse(BaseModel):
    symbol: str
    interval: str
    fetched: int
    inserted: int
    already_present: int


@router.post("/{symbol}/{interval}/ingest", response_model=BarIngestResponse)
def trigger_bar_ingest(
    symbol: str, interval: str, db: Session = Depends(get_db)
) -> BarIngestResponse:
    settings = get_settings()
    try:
        provider = TwelveDataProvider(
            api_key=settings.twelve_data_api_key, base_url=settings.twelve_data_base_url
        )
        summary = ingest_bars(db=db, provider=provider, symbol=symbol, interval=interval)
    except TwelveDataProviderError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return BarIngestResponse(
        symbol=summary.symbol,
        interval=summary.interval,
        fetched=summary.fetched,
        inserted=summary.inserted,
        already_present=summary.already_present,
    )
