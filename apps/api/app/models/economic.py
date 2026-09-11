"""
Economic data models — Stage 2 (Data Infrastructure).

These implement `data_sources`, and a simplified pair of
`economic_series` / `economic_observations` tables covering the
`economic_events` / `economic_releases` / `economic_revisions` concept from
the master plan (docs/RAH_OS_Master_Plan.docx, section 14.1), adapted to how
FRED actually models data: as versioned "vintages" of each observation.

Point-in-time correctness (master plan section 14.2) is the single most
important property here: `EconomicObservation` rows are NEVER updated or
deleted. When a value is revised, a NEW row is inserted with a later
`realtime_start`. This lets the (future) backtester ask "what value did we
know about on date X?" instead of always seeing today's revised numbers.
"""
import uuid
from datetime import UTC, date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class DataSource(Base):
    """A named upstream data provider, e.g. FRED."""

    __tablename__ = "data_sources"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    base_url: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )

    series: Mapped[list["EconomicSeries"]] = relationship(back_populates="source")


class EconomicSeries(Base):
    """
    A single tracked economic indicator, e.g. CPI (FRED code CPIAUCSL).

    `code` is the upstream provider's identifier so we never have to guess
    or re-derive it — it is copied verbatim from the provider.
    """

    __tablename__ = "economic_series"
    __table_args__ = (UniqueConstraint("source_id", "code", name="uq_series_source_code"),)

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    source_id: Mapped[str] = mapped_column(String(36), ForeignKey("data_sources.id"))
    code: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    frequency: Mapped[str] = mapped_column(String(20), nullable=True)
    units: Mapped[str] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )

    source: Mapped["DataSource"] = relationship(back_populates="series")
    observations: Mapped[list["EconomicObservation"]] = relationship(
        back_populates="series"
    )


class EconomicObservation(Base):
    """
    A single point-in-time vintage of one observation of one series.

    Append-only. Never updated, never deleted (see AGENTS.md section 4).
    `(series_id, observation_date, realtime_start)` uniquely identifies a
    specific vintage, which is what makes repeated ingestion runs safe to
    re-run without creating duplicates.
    """

    __tablename__ = "economic_observations"
    __table_args__ = (
        UniqueConstraint(
            "series_id",
            "observation_date",
            "realtime_start",
            name="uq_observation_vintage",
        ),
    )

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    series_id: Mapped[str] = mapped_column(String(36), ForeignKey("economic_series.id"))

    # The period this value describes, e.g. 2024-01-01 for January's CPI.
    observation_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)

    value: Mapped[float] = mapped_column(Numeric(20, 6), nullable=False)

    # The window during which this vintage of the value was the "current"
    # known value. realtime_end far in the future means "still current."
    realtime_start: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    realtime_end: Mapped[date] = mapped_column(Date, nullable=False)

    ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )

    series: Mapped["EconomicSeries"] = relationship(back_populates="observations")
