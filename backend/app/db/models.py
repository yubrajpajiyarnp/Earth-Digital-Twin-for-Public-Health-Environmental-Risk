from datetime import datetime, timezone

from sqlalchemy import Boolean, Date, DateTime, Float, Integer, String, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class No2Reading(Base):
    """One row per (city, date): daily-mean NO2 column density, persisted every time
    no2_timeseries.fetch_no2_daily_series() pulls fresh data from Earth Engine. Builds a
    growing local history that outlives whatever trailing window GEE's own catalog
    happens to return on a given call."""

    __tablename__ = "no2_readings"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    city: Mapped[str] = mapped_column(String, nullable=False)
    date: Mapped[Date] = mapped_column(Date, nullable=False)
    value: Mapped[float] = mapped_column(Float, nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    __table_args__ = (UniqueConstraint("city", "date", name="uq_no2_city_date"),)


class NdviReading(Base):
    __tablename__ = "ndvi_readings"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    city: Mapped[str] = mapped_column(String, nullable=False)
    date: Mapped[Date] = mapped_column(Date, nullable=False)
    value: Mapped[float] = mapped_column(Float, nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    __table_args__ = (UniqueConstraint("city", "date", name="uq_ndvi_city_date"),)


class RainfallReading(Base):
    __tablename__ = "rainfall_readings"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    city: Mapped[str] = mapped_column(String, nullable=False)
    date: Mapped[Date] = mapped_column(Date, nullable=False)
    value_mm: Mapped[float] = mapped_column(Float, nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    __table_args__ = (UniqueConstraint("city", "date", name="uq_rainfall_city_date"),)


class FaunaObservationWindow(Base):
    """One row per (city, window_start, window_end): total GBIF occurrence count for
    that 30-day window, persisted every time gbif_observations.fetch_monthly_occurrence_
    counts() runs. Re-fetching the same window later updates the count in place, since
    GBIF's own publishing lag means a recent window's true count can rise after the fact."""

    __tablename__ = "fauna_observation_windows"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    city: Mapped[str] = mapped_column(String, nullable=False)
    window_start: Mapped[Date] = mapped_column(Date, nullable=False)
    window_end: Mapped[Date] = mapped_column(Date, nullable=False)
    count: Mapped[int] = mapped_column(Integer, nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    __table_args__ = (
        UniqueConstraint("city", "window_start", "window_end", name="uq_fauna_city_window"),
    )


class KnowledgeGraphEdge(Base):
    """One row per knowledge-graph edge (indicator -> outcome). Seeded once from the
    original hardcoded set in graph.py on first startup (see seed_graph_if_empty()); after
    that, this table IS the graph — build_health_risk_graph() reads from here, so an
    admin edit takes effect immediately without a code change or restart."""

    __tablename__ = "knowledge_graph_edges"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source: Mapped[str] = mapped_column(String, nullable=False)
    target: Mapped[str] = mapped_column(String, nullable=False)
    relation: Mapped[str] = mapped_column(String, nullable=False)
    mechanism: Mapped[str] = mapped_column(String, nullable=False)
    citation: Mapped[str] = mapped_column(String, nullable=False)
    data_connected: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    __table_args__ = (UniqueConstraint("source", "target", name="uq_kg_source_target"),)


class AdminSetting(Base):
    """Simple key/value override store for admin-managed config (currently the fuel and
    carbon pricing API keys). Checked BEFORE the .env-loaded default in app/core/config.py
    — see app/services/pricing/*.py — so an admin can change a key from the UI without
    editing backend/.env or restarting the server."""

    __tablename__ = "admin_settings"
    key: Mapped[str] = mapped_column(String, primary_key=True)
    value: Mapped[str] = mapped_column(String, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, onupdate=_utcnow)


class ForecastLog(Base):
    """One row per forecast POINT produced by aqi_forecast.forecast_no2(), NOT
    deduplicated by target_date — the same future date gets a new row each time it's
    forecasted again (e.g. from a shorter lead time), so joining against no2_readings
    later can show how forecast accuracy for a given day improved as it got closer,
    not just a single final prediction."""

    __tablename__ = "forecast_log"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    city: Mapped[str] = mapped_column(String, nullable=False)
    indicator: Mapped[str] = mapped_column(String, nullable=False)
    target_date: Mapped[Date] = mapped_column(Date, nullable=False)
    horizon_days: Mapped[int] = mapped_column(Integer, nullable=False)
    predicted_value: Mapped[float] = mapped_column(Float, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
