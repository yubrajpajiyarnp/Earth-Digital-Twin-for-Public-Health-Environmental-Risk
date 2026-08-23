"""Simulation engine: projects the effect of user-defined interventions on the two live
indicators (NO2 proxy, NDVI) and re-runs the same baseline-relative anomaly classification
used elsewhere (app/services/knowledge_graph/anomaly.py), so a "what-if" scenario produces
before/after risk levels in the same terms as the live pipeline.

The intervention -> indicator effect sizes below are STATED, LITERATURE-INFORMED
ASSUMPTIONS, not calibrated for Vellore: there's no local traffic-emissions inventory or
land-cover-change ground truth to fit them against. Treat scenario outputs as illustrative
"which direction and roughly how much", not a precise physical prediction — see CLAUDE.md.

The projection math is split into pure `project_*` functions (no I/O) so the RL budget
optimizer (app/services/rl/) can call them thousands of times per training run without a
live Earth Engine request on every step — see app/services/rl/env.py.
"""

from app.core.config import settings
from app.services.cv.ndvi_timeseries import fetch_ndvi_series
from app.services.cv.no2_timeseries import fetch_no2_daily_series
from app.services.knowledge_graph.anomaly import classify_anomaly
from app.services.knowledge_graph.graph import build_health_risk_graph

# Share of ambient urban NO2 typically attributed to road traffic, per WHO/EEA
# source-apportionment studies (commonly cited range ~0.3-0.8 across cities). A generic
# literature midpoint, not measured for Vellore specifically.
TRAFFIC_NO2_ATTRIBUTION = 0.6

# Mature-vegetation NDVI end-member the projection mixes toward, weighted by the area
# fraction reforested: a standard remote-sensing reference value, not Vellore-specific
# ground truth.
FOREST_NDVI = 0.75


def project_no2_after_traffic_reduction(current: float, reduction_pct: float) -> float:
    no2_change_frac = (reduction_pct / 100) * TRAFFIC_NO2_ATTRIBUTION
    return current * (1 - no2_change_frac)


def project_ndvi_after_afforestation(current: float, area_pct: float) -> float:
    frac = area_pct / 100
    return current * (1 - frac) + FOREST_NDVI * frac


def simulate_traffic_reduction(reduction_pct: float, days_back: int = 180) -> dict:
    """What if traffic-related emissions in Vellore dropped by `reduction_pct`%?"""
    if not 0 <= reduction_pct <= 100:
        raise ValueError("reduction_pct must be between 0 and 100")

    history = fetch_no2_daily_series(days_back=days_back)
    baseline_mean = float(history.mean())
    baseline_std = float(history.std()) or 1e-12
    current = float(history.iloc[-1])

    projected = project_no2_after_traffic_reduction(current, reduction_pct)

    z_before = (current - baseline_mean) / baseline_std
    z_after = (projected - baseline_mean) / baseline_std

    graph = build_health_risk_graph()
    outcomes = [
        {
            "outcome": outcome,
            "risk_before": classify_anomaly(z_before),
            "risk_after": classify_anomaly(z_after),
        }
        for _, outcome, _ in graph.out_edges("no2_column_density", data=True)
    ]

    return {
        "city": settings.pilot_city,
        "scenario": "traffic_reduction",
        "reduction_pct": reduction_pct,
        "assumption": (
            f"{TRAFFIC_NO2_ATTRIBUTION:.0%} of ambient NO2 attributed to traffic "
            "(literature range, not Vellore-calibrated)"
        ),
        "no2_current": current,
        "no2_projected": projected,
        "pct_change": (projected - current) / current * 100,
        "outcomes": outcomes,
    }


def simulate_afforestation(area_pct: float, days_back: int = 365) -> dict:
    """What if `area_pct`% of the monitored buffer area around Vellore were reforested?"""
    if not 0 <= area_pct <= 100:
        raise ValueError("area_pct must be between 0 and 100")

    series = fetch_ndvi_series(days_back=days_back)
    baseline_mean = float(series.mean())
    baseline_std = float(series.std()) or 1e-9
    current = float(series.iloc[-1])

    projected = project_ndvi_after_afforestation(current, area_pct)

    z_before = (current - baseline_mean) / baseline_std
    z_after = (projected - baseline_mean) / baseline_std

    graph = build_health_risk_graph()
    outcomes = [
        {
            "outcome": outcome,
            "risk_before": classify_anomaly(z_before, invert=True),
            "risk_after": classify_anomaly(z_after, invert=True),
        }
        for _, outcome, _ in graph.out_edges("deforestation", data=True)
    ]

    return {
        "city": settings.pilot_city,
        "scenario": "afforestation",
        "area_pct": area_pct,
        "assumption": (
            f"linear NDVI mixing toward a forest end-member of {FOREST_NDVI} over "
            f"{area_pct}% of the buffer area (standard remote-sensing reference value, "
            "not Vellore-calibrated)"
        ),
        "ndvi_current": current,
        "ndvi_projected": projected,
        "pct_change": (projected - current) / current * 100 if current else None,
        "outcomes": outcomes,
    }
