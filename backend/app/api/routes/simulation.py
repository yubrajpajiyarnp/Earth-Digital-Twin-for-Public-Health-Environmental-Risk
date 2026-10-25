"""Live Nepal disaster predictions and the interactive what-if simulator, both served by
the local ML engine in app/models/simulation/disaster_ml.py."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.core.regions import resolve_region
from app.models.simulation.disaster_ml import (
    predict_kathmandu_flood,
    predict_mugling_landslide,
    simulate_interactive,
)

router = APIRouter(tags=["simulation"])

_PREDICTORS = {"kathmandu_flood": predict_kathmandu_flood, "mugling_landslide": predict_mugling_landslide}


@router.get("/predict/disaster/nepal")
def predict_disaster_nepal(region: str | None = None, horizon_days: int = 14, include_narrative: bool = True):
    try:
        region_id = resolve_region(region)["id"]
        return _PREDICTORS[region_id](horizon_days=min(max(horizon_days, 1), 14), include_narrative=include_narrative)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


class InteractiveScenario(BaseModel):
    rain_volume_mm: float = Field(ge=0, le=600, description="Rainfall over the day (mm)")
    cloudburst_mm_per_hr: float = Field(ge=0, le=200, description="Peak 1-hour intensity (mm/h)")
    soil_saturation_pct: float = Field(ge=0, le=100, description="Deep-soil saturation, 0–100% of the region's range")
    pressure_drop_hpa: float | None = Field(default=None, ge=0, le=30)


@router.post("/simulate/disaster-interactive")
def simulate_disaster_interactive(body: InteractiveScenario):
    try:
        return simulate_interactive(
            body.rain_volume_mm, body.cloudburst_mm_per_hr, body.soil_saturation_pct, body.pressure_drop_hpa
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
