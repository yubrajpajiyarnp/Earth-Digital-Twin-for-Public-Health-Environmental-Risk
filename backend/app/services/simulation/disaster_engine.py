"""Disaster event simulation (flood, fire, earthquake): projects the effect of a
user-specified severity on human health, vegetation, and wildlife activity where a
causal story is defensible for that disaster type, plus a reconstruction-fund estimate
broken down by infrastructure category and public-usage priority.

Real baselines are reused wherever they causally apply (rainfall for flood, NDVI/NO2/GBIF
for flood and fire); the sensitivity coefficients translating "severity" into an effect
on those baselines are STATED, NOT CALIBRATED assumptions — there's no local
disaster-damage assessment for Vellore to fit them against, same honesty pattern as
simulation/engine.py's TRAFFIC_NO2_ATTRIBUTION and FOREST_NDVI. Earthquake has no
defensible link to any of this app's environmental indicators (it's not weather-driven),
so its simulation skips the environmental knowledge-graph outcomes entirely rather than
force a fake causal story — it only produces the reconstruction estimate.

Slow by construction for flood/fire: each fetches 2-3 live sources in sequence (NDVI
alone is 30-90s+, GBIF ~15-20s) — give callers a generous timeout. Earthquake is fast
(pure math, no I/O).
"""

import statistics

from app.core.config import settings
from app.services.cv.ndvi_timeseries import fetch_ndvi_series
from app.services.cv.no2_timeseries import fetch_no2_daily_series
from app.services.cv.rainfall_timeseries import fetch_rainfall_daily_series
from app.services.fauna.gbif_observations import fetch_monthly_occurrence_counts
from app.services.knowledge_graph.anomaly import classify_anomaly
from app.services.knowledge_graph.graph import build_health_risk_graph

DISASTER_TYPES = ["flood", "fire", "earthquake"]

# --- Flood sensitivity coefficients (illustrative, see module docstring) ---
FLOOD_NDVI_DROP_AT_100PCT_SEVERITY = 0.05
FLOOD_FAUNA_Z_DROP_AT_100PCT_SEVERITY = 1.0

# --- Fire sensitivity coefficients (illustrative) ---
# Fire destroys vegetation more directly than flood waterlogging, and habitat loss from
# burning is typically more severe than flood disruption — both coefficients set higher
# than the flood equivalents on that basis, not a measured comparison.
FIRE_NDVI_DROP_AT_100PCT_SEVERITY = 0.15
FIRE_FAUNA_Z_DROP_AT_100PCT_SEVERITY = 1.5
# Rough air-quality-degradation stand-in for smoke: this app has no dedicated particulate
# indicator, so a fire's smoke impact is illustrated by spiking the NO2 proxy — NOT a
# claim that wildfire smoke literally is NO2, just the nearest available "air got worse"
# signal in this pipeline.
FIRE_NO2_SPIKE_FRAC_AT_100PCT_SEVERITY = 1.0

# Infrastructure categories for the reconstruction-fund breakdown: a STATED,
# ILLUSTRATIVE model of (a) how reconstruction spend typically splits across categories
# and (b) the order in which they'd be prioritized based on how much of the public
# depends on each day-to-day (roads/water/power affect ~everyone daily; schools/other
# affect a narrower, though still important, slice). Not sourced from a specific
# published Vellore or India-wide cost-breakdown study — see CLAUDE.md. Same
# category/priority/split applies across disaster types for now; only the total amount
# and which environmental outcomes are shown differ by type.
INFRASTRUCTURE_CATEGORIES = [
    {"category": "roads_transport", "label": "Roads & transport", "priority": 1, "cost_share": 0.30},
    {"category": "water_supply", "label": "Water supply", "priority": 2, "cost_share": 0.15},
    {"category": "electricity", "label": "Electricity", "priority": 3, "cost_share": 0.15},
    {"category": "healthcare", "label": "Healthcare facilities", "priority": 4, "cost_share": 0.10},
    {"category": "housing", "label": "Housing", "priority": 5, "cost_share": 0.20},
    {"category": "schools", "label": "Schools & education", "priority": 6, "cost_share": 0.07},
    {"category": "other", "label": "Other public infrastructure", "priority": 7, "cost_share": 0.03},
]

# Order-of-magnitude reconstruction-cost model. Loosely scaled to the MAGNITUDE of
# published Indian SDRF/NDRF disaster-relief norms (household/infrastructure compensation
# is on the order of tens of thousands to a few lakh INR per affected household) — this is
# NOT the exact current government rate, which changes periodically, and this session did
# not look up the actual current SDRF/NDRF rate tables. Consult that documentation before
# using this for anything but illustration.
EST_POPULATION_IN_BUFFER = 50_000
RECONSTRUCTION_COST_PER_AFFECTED_PERSON_INR = 15_000


def estimate_reconstruction_fund(severity_pct: float) -> dict:
    """Pure (no I/O) illustrative reconstruction-cost estimate, broken down by
    infrastructure category and sorted by public-usage priority (1 = rebuild first)."""
    affected_fraction = min(1.0, severity_pct / 200)
    affected_population = affected_fraction * EST_POPULATION_IN_BUFFER
    total_cost = affected_population * RECONSTRUCTION_COST_PER_AFFECTED_PERSON_INR

    breakdown = sorted(
        (
            {
                "category": c["category"],
                "label": c["label"],
                "priority": c["priority"],
                "estimated_cost_inr": total_cost * c["cost_share"],
            }
            for c in INFRASTRUCTURE_CATEGORIES
        ),
        key=lambda item: item["priority"],
    )

    return {
        "affected_population_estimate": affected_population,
        "estimated_cost_inr": total_cost,
        "breakdown_by_category": breakdown,
        "assumption": (
            f"Illustrative only: assumes ~{EST_POPULATION_IN_BUFFER:,} people in the "
            f"monitored buffer area and ~₹{RECONSTRUCTION_COST_PER_AFFECTED_PERSON_INR:,} "
            "reconstruction cost per affected person, order-of-magnitude scaled to "
            "published Indian SDRF/NDRF disaster-relief norms — NOT the exact current "
            "government rate (not looked up this session). Category cost-shares and "
            "rebuild priority are a stated general assumption (roads/water/power ranked "
            "above schools/other on daily public dependence), not a Vellore-specific "
            "study. Consult actual SDRF/NDRF documentation and a local infrastructure "
            "assessment for real figures. See CLAUDE.md."
        ),
    }


def _ndvi_projection(drop_at_100pct_severity: float, severity_pct: float, days_back: int = 365):
    series = fetch_ndvi_series(days_back=days_back)
    baseline_mean = float(series.mean())
    baseline_std = float(series.std()) or 1e-9
    current = float(series.iloc[-1])
    projected = max(0.0, current - drop_at_100pct_severity * (severity_pct / 100))
    z_before = (current - baseline_mean) / baseline_std
    z_after = (projected - baseline_mean) / baseline_std
    return current, projected, z_before, z_after


def _fauna_projection(z_drop_at_100pct_severity: float, severity_pct: float):
    windows = fetch_monthly_occurrence_counts()
    counts = [w["count"] for w in windows]
    current = counts[-1]
    baseline_counts = counts[:-1]
    baseline_mean = statistics.mean(baseline_counts)
    baseline_std = statistics.pstdev(baseline_counts) or 1e-9
    z_before = (current - baseline_mean) / baseline_std
    z_after = z_before - z_drop_at_100pct_severity * (severity_pct / 100)
    return current, z_before, z_after


def simulate_flood_event(severity_pct: float, rainfall_days_back: int = 180, recent_window_days: int = 7) -> dict:
    """What if the recent rainfall (7-day total) were `severity_pct`% higher than it
    already is relative to its own baseline? Projects effects on waterborne disease,
    vegetation, and wildlife activity, plus a reconstruction-fund estimate."""
    if severity_pct < 0:
        raise ValueError("severity_pct must be non-negative")

    rainfall = fetch_rainfall_daily_series(days_back=rainfall_days_back)
    rolling_sum = rainfall.rolling(recent_window_days).sum().dropna()
    rain_baseline_mean = float(rolling_sum.mean())
    rain_baseline_std = float(rolling_sum.std()) or 1e-9
    rain_current = float(rolling_sum.iloc[-1])
    rain_projected = rain_current * (1 + severity_pct / 100)
    z_rain_before = (rain_current - rain_baseline_mean) / rain_baseline_std
    z_rain_after = (rain_projected - rain_baseline_mean) / rain_baseline_std

    ndvi_current, ndvi_projected, z_ndvi_before, z_ndvi_after = _ndvi_projection(
        FLOOD_NDVI_DROP_AT_100PCT_SEVERITY, severity_pct
    )
    fauna_current, z_fauna_before, z_fauna_after = _fauna_projection(
        FLOOD_FAUNA_Z_DROP_AT_100PCT_SEVERITY, severity_pct
    )

    graph = build_health_risk_graph()
    outcomes = []
    for _, outcome, _ in graph.out_edges("rainfall_extreme", data=True):
        outcomes.append(
            {"outcome": outcome, "risk_before": classify_anomaly(z_rain_before), "risk_after": classify_anomaly(z_rain_after)}
        )
    for _, outcome, _ in graph.out_edges("deforestation", data=True):
        outcomes.append(
            {"outcome": outcome, "risk_before": classify_anomaly(z_ndvi_before, invert=True), "risk_after": classify_anomaly(z_ndvi_after, invert=True)}
        )
    for _, outcome, _ in graph.out_edges("wildlife_activity", data=True):
        outcomes.append(
            {"outcome": outcome, "risk_before": classify_anomaly(z_fauna_before, invert=True), "risk_after": classify_anomaly(z_fauna_after, invert=True)}
        )

    return {
        "city": settings.pilot_city,
        "scenario": "flood_event",
        "severity_pct": severity_pct,
        "metrics": {
            "rainfall_mm": {"current": rain_current, "projected": rain_projected},
            "ndvi": {"current": ndvi_current, "projected": ndvi_projected},
            "fauna_observations": {"current": fauna_current},
        },
        "outcomes": outcomes,
        "reconstruction_estimate": estimate_reconstruction_fund(severity_pct),
        "assumption": (
            "Vegetation-damage and wildlife-disruption coefficients are stated "
            "illustrative assumptions layered on real rainfall/NDVI/GBIF baselines — not "
            "calibrated for Vellore. See CLAUDE.md."
        ),
    }


def simulate_fire_event(severity_pct: float, no2_days_back: int = 180) -> dict:
    """What if a fire of `severity_pct` intensity occurred? Projects effects on air
    quality (smoke proxy), vegetation, and wildlife activity, plus a reconstruction-fund
    estimate. Unlike flood, there's no live "current fire" indicator to compare against —
    severity is a pure hypothetical input, not derived from a real anomaly."""
    if severity_pct < 0:
        raise ValueError("severity_pct must be non-negative")

    no2_series = fetch_no2_daily_series(days_back=no2_days_back)
    no2_baseline_mean = float(no2_series.mean())
    no2_baseline_std = float(no2_series.std()) or 1e-12
    no2_current = float(no2_series.iloc[-1])
    no2_projected = no2_current * (1 + FIRE_NO2_SPIKE_FRAC_AT_100PCT_SEVERITY * (severity_pct / 100))
    z_no2_before = (no2_current - no2_baseline_mean) / no2_baseline_std
    z_no2_after = (no2_projected - no2_baseline_mean) / no2_baseline_std

    ndvi_current, ndvi_projected, z_ndvi_before, z_ndvi_after = _ndvi_projection(
        FIRE_NDVI_DROP_AT_100PCT_SEVERITY, severity_pct
    )
    fauna_current, z_fauna_before, z_fauna_after = _fauna_projection(
        FIRE_FAUNA_Z_DROP_AT_100PCT_SEVERITY, severity_pct
    )

    graph = build_health_risk_graph()
    outcomes = []
    for _, outcome, _ in graph.out_edges("no2_column_density", data=True):
        outcomes.append(
            {"outcome": outcome, "risk_before": classify_anomaly(z_no2_before), "risk_after": classify_anomaly(z_no2_after)}
        )
    for _, outcome, _ in graph.out_edges("deforestation", data=True):
        outcomes.append(
            {"outcome": outcome, "risk_before": classify_anomaly(z_ndvi_before, invert=True), "risk_after": classify_anomaly(z_ndvi_after, invert=True)}
        )
    for _, outcome, _ in graph.out_edges("wildlife_activity", data=True):
        outcomes.append(
            {"outcome": outcome, "risk_before": classify_anomaly(z_fauna_before, invert=True), "risk_after": classify_anomaly(z_fauna_after, invert=True)}
        )

    return {
        "city": settings.pilot_city,
        "scenario": "fire_event",
        "severity_pct": severity_pct,
        "metrics": {
            "no2_smoke_proxy": {"current": no2_current, "projected": no2_projected},
            "ndvi": {"current": ndvi_current, "projected": ndvi_projected},
            "fauna_observations": {"current": fauna_current},
        },
        "outcomes": outcomes,
        "reconstruction_estimate": estimate_reconstruction_fund(severity_pct),
        "assumption": (
            "No live 'current fire' indicator exists, so severity is a pure hypothetical "
            "input. The air-quality effect is illustrated via the NO2 proxy as a rough "
            "smoke stand-in (not a literal smoke measurement); vegetation-damage and "
            "wildlife-disruption coefficients are stated illustrative assumptions — not "
            "calibrated for Vellore. See CLAUDE.md."
        ),
    }


def simulate_earthquake_event(severity_pct: float) -> dict:
    """What if an earthquake of `severity_pct` intensity occurred? Earthquakes aren't
    weather/vegetation-driven, so there's no defensible link to this app's environmental
    indicators (NO2/NDVI/rainfall/fauna) — this simulation deliberately skips those
    outcomes rather than force a fake causal story, and only produces the
    reconstruction-fund estimate."""
    if severity_pct < 0:
        raise ValueError("severity_pct must be non-negative")

    return {
        "city": settings.pilot_city,
        "scenario": "earthquake_event",
        "severity_pct": severity_pct,
        "metrics": {},
        "outcomes": [],
        "reconstruction_estimate": estimate_reconstruction_fund(severity_pct),
        "assumption": (
            "Earthquakes have no defensible causal link to this project's environmental "
            "indicators (NO2/NDVI/rainfall/fauna), so no risk outcomes are shown — only "
            "the reconstruction-fund estimate, which itself is illustrative (see its own "
            "assumption field). This project has not verified Vellore's actual seismic "
            "hazard zone classification (BIS IS 1893) this session; treat this purely as "
            "a what-if cost exercise, not a real seismic-risk assessment."
        ),
    }


def simulate_disaster(disaster_type: str, severity_pct: float) -> dict:
    if disaster_type not in DISASTER_TYPES:
        raise ValueError(f"disaster_type must be one of {DISASTER_TYPES}")
    if disaster_type == "flood":
        return simulate_flood_event(severity_pct)
    if disaster_type == "fire":
        return simulate_fire_event(severity_pct)
    return simulate_earthquake_event(severity_pct)
