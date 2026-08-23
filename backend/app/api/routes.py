from fastapi import APIRouter, HTTPException

from app.core.config import settings
from app.services.cv.aqi_proxy import get_no2_proxy
from app.services.cv.ndvi_timeseries import fetch_ndvi_series
from app.services.cv.rainfall_timeseries import fetch_rainfall_daily_series
from app.services.fauna.gbif_observations import fetch_monthly_occurrence_counts
from app.services.forecasting.aqi_forecast import forecast_no2
from app.services.knowledge_graph.fauna_risk_assessment import assess_fauna_disruption
from app.services.knowledge_graph.flood_risk_assessment import assess_flood_risk
from app.services.knowledge_graph.graph import build_health_risk_graph
from app.services.knowledge_graph.risk_assessment import assess_no2_health_risk
from app.services.knowledge_graph.vegetation_risk_assessment import assess_vegetation_risk
from app.services.pricing.carbon_price import get_carbon_price_usd_per_ton
from app.services.pricing.fuel_price import get_petrol_price_inr_per_litre
from app.services.rl.optimizer import optimize_budget_allocation
from app.services.simulation.disaster_engine import DISASTER_TYPES, simulate_disaster
from app.services.simulation.engine import simulate_afforestation, simulate_traffic_reduction
from app.services.xai.explain_forecast import explain_latest_prediction

router = APIRouter()


@router.get("/health")
def health():
    return {"status": "ok", "pilot_city": settings.pilot_city}


@router.get("/aqi-proxy")
def aqi_proxy(max_scenes: int = 30):
    try:
        return get_no2_proxy(max_scenes=max_scenes)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/forecast/aqi")
def forecast_aqi(horizon_days: int = 7, days_back: int = 180):
    try:
        return forecast_no2(horizon_days=horizon_days, days_back=days_back)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/risk/aqi")
def risk_aqi(horizon_days: int = 7, days_back: int = 180):
    try:
        return assess_no2_health_risk(horizon_days=horizon_days, days_back=days_back)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/explain/aqi")
def explain_aqi(days_back: int = 180):
    try:
        return explain_latest_prediction(days_back=days_back)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/ndvi")
def ndvi(days_back: int = 365):
    try:
        series = fetch_ndvi_series(days_back=days_back)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return {
        "city": settings.pilot_city,
        "metric": "ndvi",
        "scene_count": len(series),
        "series": [
            {"date": d.strftime("%Y-%m-%d"), "value": float(v)} for d, v in series.items()
        ],
    }


@router.get("/risk/vegetation")
def risk_vegetation(days_back: int = 365, recent_window_days: int = 60):
    try:
        return assess_vegetation_risk(days_back=days_back, recent_window_days=recent_window_days)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/rainfall")
def rainfall(days_back: int = 180):
    try:
        series = fetch_rainfall_daily_series(days_back=days_back)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return {
        "city": settings.pilot_city,
        "metric": "rainfall_mm",
        "day_count": len(series),
        "series": [
            {"date": d.strftime("%Y-%m-%d"), "value": float(v)} for d, v in series.items()
        ],
    }


@router.get("/risk/flood")
def risk_flood(days_back: int = 180, recent_window_days: int = 7):
    try:
        return assess_flood_risk(days_back=days_back, recent_window_days=recent_window_days)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/fauna")
def fauna(num_months: int = 13):
    try:
        return {
            "city": settings.pilot_city,
            "metric": "gbif_occurrence_count",
            "months_series": fetch_monthly_occurrence_counts(num_months=num_months),
        }
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/risk/fauna")
def risk_fauna(num_months: int = 13):
    try:
        return assess_fauna_disruption(num_months=num_months)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/simulate/disaster")
def simulate_disaster_route(disaster_type: str, severity_pct: float):
    if disaster_type not in DISASTER_TYPES:
        raise HTTPException(
            status_code=400, detail=f"disaster_type must be one of {DISASTER_TYPES}"
        )
    try:
        return simulate_disaster(disaster_type, severity_pct)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/simulate/traffic-reduction")
def simulate_traffic(reduction_pct: float, days_back: int = 180):
    try:
        return simulate_traffic_reduction(reduction_pct, days_back=days_back)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/simulate/afforestation")
def simulate_afforest(area_pct: float, days_back: int = 365):
    try:
        return simulate_afforestation(area_pct, days_back=days_back)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/optimize/budget")
def optimize_budget(
    budget: float = 100.0,
    training_steps: int = 4000,
    fuel_price_inr: float | None = None,
):
    training_steps = min(training_steps, 20000)  # cap: this trains a fresh policy per request
    try:
        return optimize_budget_allocation(
            budget=budget, training_steps=training_steps, manual_fuel_price_inr=fuel_price_inr
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/prices/fuel")
def prices_fuel(city: str = "Vellore", state: str = "TN"):
    try:
        price = get_petrol_price_inr_per_litre(city=city, state=state)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return {"city": city, "state": state, "petrol_price_inr_per_litre": price, "source": "PurePriceIO"}


@router.get("/prices/carbon")
def prices_carbon():
    try:
        price = get_carbon_price_usd_per_ton()
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return {"price_usd_per_ton": price, "source": "Carbonmark (sandbox)"}


@router.get("/knowledge-graph")
def knowledge_graph():
    graph = build_health_risk_graph()
    return {
        "nodes": list(graph.nodes),
        "edges": [
            {"source": source, "target": target, **data}
            for source, target, data in graph.edges(data=True)
        ],
    }
