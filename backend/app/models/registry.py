"""Single entry point for every calculation and AI module in the Nepal disaster digital twin.

Each pipeline still lives in its own file under app/models/ or app/ingestion/ (that stays the
source of truth — nothing is duplicated here). This module gathers them in one place:

  - MODULES is a registry describing each one: what it computes, which technique it uses,
    and where its code lives
  - run(name, **kwargs) runs one module by name; run_all() runs every module and collects
    the results (one failing data source doesn't stop the rest)

Prediction modules need the local model bundle; the CLI loads it from disk (training it in
the foreground if none exists yet).

CLI (from backend/):
    python -m app.models.registry                       # list every module
    python -m app.models.registry predict_flood         # run one module, print JSON
    python -m app.models.registry --all                 # run every module, print JSON
    python -m app.models.registry --train               # retrain the bundle now
"""

import json
import sys
import time
from dataclasses import dataclass, field
from typing import Callable

import pandas as pd

from app.core.regions import KTM_RIVERS, REGIONS
from app.ingestion.hydro_geology import (
    fetch_hourly_weather,
    fetch_incidents,
    fetch_region_slope_deg,
    fetch_river_discharge,
)
from app.ingestion.weather import get_current_weather
from app.models.llm.dashboard_summary import build_dashboard_summary
from app.models.risk.knowledge_graph import build_health_risk_graph
from app.models.simulation import disaster_ml
from app.models.simulation.disaster_ml import (
    disaster_collinearity,
    model_status,
    predict_kathmandu_flood,
    predict_mugling_landslide,
    simulate_interactive,
)


@dataclass(frozen=True)
class ModelModule:
    name: str
    category: str
    technique: str
    description: str
    source: str
    fn: Callable
    defaults: dict = field(default_factory=dict)
    # Expensive modules (full history downloads) are skipped by run_all() unless asked for.
    heavy: bool = False


MODULES: dict[str, ModelModule] = {
    m.name: m
    for m in [
        # Data ingestion
        ModelModule(
            "weather_forecast_mugling", "data", "Open-Meteo ECMWF IFS 0.25°",
            "Hourly rain, pressure and deep soil moisture for the Mugling corridor.",
            "ingestion/hydro_geology.py", lambda: fetch_hourly_weather(REGIONS["mugling_landslide"]),
        ),
        ModelModule(
            "discharge_bagmati", "data", "GloFAS via Open-Meteo Flood API",
            "Bagmati daily discharge: last 90 days plus GloFAS forecast.",
            "ingestion/hydro_geology.py", lambda: fetch_river_discharge(KTM_RIVERS[0]),
        ),
        ModelModule(
            "incidents_mugling", "data", "NDRRMA BIPAD Portal",
            "Reported landslides within the corridor radius since 2011.",
            "ingestion/hydro_geology.py", lambda: fetch_incidents(REGIONS["mugling_landslide"]),
            heavy=True,
        ),
        ModelModule(
            "slope_mugling", "data", "Copernicus 90 m DEM via Open-Meteo Elevation",
            "Mean terrain slope (°) over the corridor.",
            "ingestion/hydro_geology.py", lambda: fetch_region_slope_deg(REGIONS["mugling_landslide"]),
        ),
        ModelModule(
            "weather", "data", "Open-Meteo (AccuWeather fallback)",
            "Current conditions for a region.",
            "ingestion/weather.py", get_current_weather, defaults={"region_id": "kathmandu_flood"},
        ),
        # Local ML
        ModelModule(
            "predict_flood", "ml", "HistGradientBoostingRegressor + Holt-Winters surge check",
            "Per-river 14-day discharge forecast, tiers and surge warnings for Kathmandu.",
            "models/simulation/disaster_ml.py", predict_kathmandu_flood, defaults={"include_narrative": False},
        ),
        ModelModule(
            "predict_landslide", "ml", "HistGradientBoostingClassifier + infinite-slope FoS",
            "14-day landslide failure probability, z-score and stability index for Mugling.",
            "models/simulation/disaster_ml.py", predict_mugling_landslide, defaults={"include_narrative": False},
        ),
        ModelModule(
            "simulate_interactive", "ml", "Trained models on a hypothetical day",
            "What-if rain volume / cloudburst / saturation for both regions.",
            "models/simulation/disaster_ml.py", simulate_interactive,
            defaults={"rain_volume_mm": 150.0, "cloudburst_mm_per_hr": 40.0, "soil_saturation_pct": 90.0},
        ),
        ModelModule(
            "collinearity_flood", "analytics", "Pearson / Spearman / VIF",
            "Weather drivers vs. Bagmati discharge and flood incidents.",
            "models/simulation/disaster_ml.py", disaster_collinearity, defaults={"region_id": "kathmandu_flood"},
        ),
        ModelModule(
            "collinearity_landslide", "analytics", "Pearson / Spearman / VIF (weekly)",
            "Weather drivers vs. corridor landslide incidents.",
            "models/simulation/disaster_ml.py", disaster_collinearity, defaults={"region_id": "mugling_landslide"},
        ),
        ModelModule(
            "model_status", "ml", "joblib bundle metadata",
            "Training state, period and holdout metrics.",
            "models/simulation/disaster_ml.py", model_status,
        ),
        # LLM
        ModelModule(
            "dashboard_summary", "llm", "Mistral via Ollama (template fallback)",
            "Plain-language summary of both regions' outlooks.",
            "models/llm/dashboard_summary.py", build_dashboard_summary,
        ),
        # Knowledge graph
        ModelModule(
            "knowledge_graph", "knowledge_graph", "NetworkX directed graph",
            "Cause-effect edges between hydro-geological drivers and outcomes.",
            "models/risk/knowledge_graph.py", build_health_risk_graph,
        ),
    ]
}


def _to_jsonable(value):
    """Frames, series and graphs aren't JSON-serializable; convert them so results can be
    printed or returned from an API route."""
    if isinstance(value, pd.DataFrame):
        return [{"time": str(i), **row} for i, row in value.astype(object).where(value.notna(), None).iterrows()]
    if isinstance(value, pd.Series):
        return [{"date": str(d), "value": None if pd.isna(v) else float(v)} for d, v in value.items()]
    if hasattr(value, "nodes") and hasattr(value, "edges"):
        return {
            "nodes": list(value.nodes),
            "edges": [{"source": s, "target": t, **d} for s, t, d in value.edges(data=True)],
        }
    return value


def list_modules() -> list[dict]:
    return [
        {
            "name": m.name,
            "category": m.category,
            "technique": m.technique,
            "description": m.description,
            "source": f"app/{m.source}",
            "heavy": m.heavy,
        }
        for m in MODULES.values()
    ]


def run(name: str, **kwargs):
    """Run one module by name. kwargs override the module's defaults."""
    if name not in MODULES:
        raise KeyError(f"Unknown module {name!r}. Choose from: {', '.join(MODULES)}")
    module = MODULES[name]
    return _to_jsonable(module.fn(**{**module.defaults, **kwargs}))


def run_all(include_heavy: bool = False, categories: list[str] | None = None) -> dict:
    """Run every module and collect the results. A module whose data source is down
    reports its error instead of stopping the run."""
    results = {}
    for name, module in MODULES.items():
        if module.heavy and not include_heavy:
            continue
        if categories and module.category not in categories:
            continue
        started = time.perf_counter()
        try:
            results[name] = {"ok": True, "result": run(name)}
        except (RuntimeError, ValueError) as exc:
            results[name] = {"ok": False, "error": str(exc)}
        results[name]["seconds"] = round(time.perf_counter() - started, 2)
    return {"modules": results}


def _ensure_bundle(force_train: bool = False) -> None:
    from app.db.database import init_db

    init_db()
    disaster_ml.start_background_training()
    if force_train or disaster_ml.model_status()["status"] != "ready":
        disaster_ml._train_and_save()  # foreground in the CLI


if __name__ == "__main__":
    args = sys.argv[1:]
    if not args:
        for m in list_modules():
            print(f"{m['name']:<26} {m['category']:<16} {m['technique']}")
    elif args[0] == "--train":
        _ensure_bundle(force_train=True)
        print(json.dumps(model_status(), indent=2, default=str))
    elif args[0] == "--all":
        _ensure_bundle()
        print(json.dumps(run_all(include_heavy="--heavy" in args), indent=2, default=str))
    else:
        _ensure_bundle()
        print(json.dumps(run(args[0]), indent=2, default=str))
