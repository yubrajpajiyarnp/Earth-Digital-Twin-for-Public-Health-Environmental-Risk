"""Raw data feeds: current weather, Kathmandu river discharge, past incidents."""

from fastapi import APIRouter, HTTPException

from app.core.regions import KTM_RIVERS, resolve_region
from app.ingestion.hydro_geology import fetch_incidents, fetch_river_discharge
from app.ingestion.weather import get_current_weather

router = APIRouter(tags=["data"])


@router.get("/weather")
def weather(region: str | None = None):
    try:
        return get_current_weather(region)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/feeds/river-discharge")
def river_discharge(past_days: int = 90, forecast_days: int = 14):
    try:
        rivers = []
        for river in KTM_RIVERS:
            series = fetch_river_discharge(river, past_days=past_days, forecast_days=forecast_days)
            rivers.append(
                {
                    "river_id": river["id"],
                    "river": river["name"],
                    "unit": "m³/s",
                    "series": [{"date": d.strftime("%Y-%m-%d"), "value": float(v)} for d, v in series.items()],
                }
            )
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return {"source": "GloFAS via Open-Meteo Flood API", "rivers": rivers}


@router.get("/feeds/incidents")
def incidents(region: str | None = None, since: str = "2011-01-01"):
    try:
        r = resolve_region(region)
        frame = fetch_incidents(r, since=since)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return {
        "region": r["id"],
        "hazard": r["hazard"],
        "radius_km": r["incident_radius_km"],
        "source": "NDRRMA BIPAD Portal",
        "count": len(frame),
        "incidents": [
            {"id": int(row.id), "date": row.date.strftime("%Y-%m-%d"), "lat": row.lat, "lon": row.lon, "distance_km": round(row.distance_km, 1)}
            for row in frame.itertuples()
        ],
    }
