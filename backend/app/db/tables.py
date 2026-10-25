from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Integer, String, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class KnowledgeGraphEdge(Base):
    """One row per knowledge-graph edge (indicator -> outcome). Seeded once from the
    original hardcoded set in knowledge_graph.py on first startup (see seed_graph_if_empty()); after
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
    """Simple key/value override store for admin-managed config (the Open-Meteo and
    AccuWeather API keys). Checked BEFORE the .env-loaded default in app/core/config.py —
    see app/ingestion/hydro_geology.py — so an admin can change a key from the UI without
    editing backend/.env or restarting the server."""

    __tablename__ = "admin_settings"
    key: Mapped[str] = mapped_column(String, primary_key=True)
    value: Mapped[str] = mapped_column(String, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, onupdate=_utcnow)
