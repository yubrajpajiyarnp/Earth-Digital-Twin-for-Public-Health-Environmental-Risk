from datetime import datetime, timezone

import pandas as pd
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from app.db.database import SessionLocal
from app.db.models import (
    AdminSetting,
    FaunaObservationWindow,
    ForecastLog,
    KnowledgeGraphEdge,
    NdviReading,
    No2Reading,
    RainfallReading,
)

_READING_MODELS = {
    "no2": No2Reading,
    "ndvi": NdviReading,
    "rainfall": RainfallReading,
    "fauna": FaunaObservationWindow,
}


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _upsert_series(model, value_col: str, city: str, series: pd.Series) -> None:
    if series.empty:
        return
    with SessionLocal() as db:
        for date, value in series.items():
            stmt = sqlite_insert(model).values(
                city=city, date=date.date(), **{value_col: float(value)}
            )
            stmt = stmt.on_conflict_do_update(
                index_elements=["city", "date"],
                set_={value_col: stmt.excluded[value_col], "fetched_at": _utcnow()},
            )
            db.execute(stmt)
        db.commit()


def save_no2_series(city: str, series: pd.Series) -> None:
    _upsert_series(No2Reading, "value", city, series)


def save_ndvi_series(city: str, series: pd.Series) -> None:
    _upsert_series(NdviReading, "value", city, series)


def save_rainfall_series(city: str, series: pd.Series) -> None:
    _upsert_series(RainfallReading, "value_mm", city, series)


def save_fauna_windows(city: str, windows: list[dict]) -> None:
    if not windows:
        return
    with SessionLocal() as db:
        for w in windows:
            stmt = sqlite_insert(FaunaObservationWindow).values(
                city=city,
                window_start=datetime.fromisoformat(w["start"]).date(),
                window_end=datetime.fromisoformat(w["end"]).date(),
                count=w["count"],
            )
            stmt = stmt.on_conflict_do_update(
                index_elements=["city", "window_start", "window_end"],
                set_={"count": stmt.excluded.count, "fetched_at": _utcnow()},
            )
            db.execute(stmt)
        db.commit()


def save_forecast(city: str, indicator: str, horizon_days: int, forecast_points: list[dict]) -> None:
    if not forecast_points:
        return
    with SessionLocal() as db:
        for p in forecast_points:
            db.add(
                ForecastLog(
                    city=city,
                    indicator=indicator,
                    target_date=datetime.fromisoformat(p["date"]).date(),
                    horizon_days=horizon_days,
                    predicted_value=float(p["value"]),
                )
            )
        db.commit()


def get_no2_history(city: str, limit_days: int = 365) -> list[dict]:
    with SessionLocal() as db:
        rows = (
            db.query(No2Reading)
            .filter(No2Reading.city == city)
            .order_by(No2Reading.date.desc())
            .limit(limit_days)
            .all()
        )
    return [{"id": r.id, "date": r.date.isoformat(), "value": r.value} for r in reversed(rows)]


def get_ndvi_history(city: str, limit_days: int = 365) -> list[dict]:
    with SessionLocal() as db:
        rows = (
            db.query(NdviReading)
            .filter(NdviReading.city == city)
            .order_by(NdviReading.date.desc())
            .limit(limit_days)
            .all()
        )
    return [{"id": r.id, "date": r.date.isoformat(), "value": r.value} for r in reversed(rows)]


def get_rainfall_history(city: str, limit_days: int = 365) -> list[dict]:
    with SessionLocal() as db:
        rows = (
            db.query(RainfallReading)
            .filter(RainfallReading.city == city)
            .order_by(RainfallReading.date.desc())
            .limit(limit_days)
            .all()
        )
    return [
        {"id": r.id, "date": r.date.isoformat(), "value": r.value_mm} for r in reversed(rows)
    ]


def get_fauna_history(city: str, limit: int = 365) -> list[dict]:
    with SessionLocal() as db:
        rows = (
            db.query(FaunaObservationWindow)
            .filter(FaunaObservationWindow.city == city)
            .order_by(FaunaObservationWindow.window_end.desc())
            .limit(limit)
            .all()
        )
    return [
        {
            "id": r.id,
            "window_start": r.window_start.isoformat(),
            "window_end": r.window_end.isoformat(),
            "count": r.count,
        }
        for r in reversed(rows)
    ]


def delete_reading(indicator: str, row_id: int) -> bool:
    """Admin-only: delete one row from the given indicator's reading table by id."""
    model = _READING_MODELS.get(indicator)
    if model is None:
        raise ValueError(f"Unknown indicator '{indicator}'; expected one of {list(_READING_MODELS)}")
    with SessionLocal() as db:
        row = db.get(model, row_id)
        if row is None:
            return False
        db.delete(row)
        db.commit()
        return True


def get_setting(key: str, default: str | None = None) -> str | None:
    with SessionLocal() as db:
        row = db.get(AdminSetting, key)
        return row.value if row is not None else default


def set_setting(key: str, value: str) -> None:
    with SessionLocal() as db:
        stmt = sqlite_insert(AdminSetting).values(key=key, value=value)
        stmt = stmt.on_conflict_do_update(
            index_elements=["key"], set_={"value": stmt.excluded.value, "updated_at": _utcnow()}
        )
        db.execute(stmt)
        db.commit()


def list_settings() -> list[dict]:
    with SessionLocal() as db:
        rows = db.query(AdminSetting).all()
    return [{"key": r.key, "value": r.value, "updated_at": r.updated_at.isoformat()} for r in rows]


def delete_setting(key: str) -> bool:
    with SessionLocal() as db:
        row = db.get(AdminSetting, key)
        if row is None:
            return False
        db.delete(row)
        db.commit()
        return True


def list_kg_edges() -> list[dict]:
    with SessionLocal() as db:
        rows = db.query(KnowledgeGraphEdge).all()
    return [
        {
            "id": r.id,
            "source": r.source,
            "target": r.target,
            "relation": r.relation,
            "mechanism": r.mechanism,
            "citation": r.citation,
            "data_connected": r.data_connected,
        }
        for r in rows
    ]


def upsert_kg_edge(
    source: str,
    target: str,
    relation: str,
    mechanism: str,
    citation: str,
    data_connected: bool,
    edge_id: int | None = None,
) -> dict:
    with SessionLocal() as db:
        if edge_id is not None:
            row = db.get(KnowledgeGraphEdge, edge_id)
            if row is None:
                raise ValueError(f"No knowledge-graph edge with id {edge_id}")
        else:
            row = KnowledgeGraphEdge(source=source, target=target)
            db.add(row)
        row.source = source
        row.target = target
        row.relation = relation
        row.mechanism = mechanism
        row.citation = citation
        row.data_connected = data_connected
        db.commit()
        db.refresh(row)
        return {
            "id": row.id,
            "source": row.source,
            "target": row.target,
            "relation": row.relation,
            "mechanism": row.mechanism,
            "citation": row.citation,
            "data_connected": row.data_connected,
        }


def delete_kg_edge(edge_id: int) -> bool:
    with SessionLocal() as db:
        row = db.get(KnowledgeGraphEdge, edge_id)
        if row is None:
            return False
        db.delete(row)
        db.commit()
        return True


def get_forecast_accuracy(city: str, indicator: str = "no2", limit: int = 200) -> list[dict]:
    """Join logged forecasts against the actual reading (NO2 only for now) recorded for
    that same date, where both exist — the real "did the model get it right" signal."""
    with SessionLocal() as db:
        forecasts = (
            db.query(ForecastLog)
            .filter(ForecastLog.city == city, ForecastLog.indicator == indicator)
            .order_by(ForecastLog.target_date.desc())
            .limit(limit)
            .all()
        )
        actuals = {
            r.date: r.value
            for r in db.query(No2Reading).filter(No2Reading.city == city).all()
        }

    results = []
    for f in forecasts:
        actual = actuals.get(f.target_date)
        if actual is None:
            continue
        results.append(
            {
                "target_date": f.target_date.isoformat(),
                "horizon_days": f.horizon_days,
                "predicted_value": f.predicted_value,
                "actual_value": actual,
                "error": f.predicted_value - actual,
                "pct_error": (f.predicted_value - actual) / actual * 100 if actual else None,
                "forecasted_at": f.created_at.isoformat(),
            }
        )
    return results
