"""
Provider interface for economic data — see AGENTS.md section 2 and
docs/ARCHITECTURE.md "Provider Adapter Pattern".

Business logic (the ingestion service) must depend only on this interface,
never on a concrete provider like FRED directly. That is what lets a second
provider be added later without touching ingestion code.
"""
from abc import ABC, abstractmethod
from datetime import date

from pydantic import BaseModel


class ObservationDTO(BaseModel):
    """One point-in-time vintage of one observation, provider-agnostic."""

    series_code: str
    observation_date: date
    value: float
    realtime_start: date
    realtime_end: date


class SeriesMetadataDTO(BaseModel):
    """Metadata about a series, provider-agnostic."""

    code: str
    name: str
    frequency: str | None = None
    units: str | None = None


class EconomicDataProvider(ABC):
    """Interface every economic data provider adapter must implement."""

    @abstractmethod
    def fetch_series_metadata(self, series_code: str) -> SeriesMetadataDTO:
        """Fetch descriptive metadata for a series."""

    @abstractmethod
    def fetch_observations(self, series_code: str) -> list[ObservationDTO]:
        """
        Fetch the full point-in-time vintage history for a series: every
        version of every observation that has ever been published, not just
        the latest revision. This is what makes point-in-time backtesting
        possible later.
        """
