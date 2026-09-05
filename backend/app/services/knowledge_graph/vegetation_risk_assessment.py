import pandas as pd

from app.core.config import settings
from app.services.cv.ndvi_timeseries import fetch_ndvi_series
from app.services.knowledge_graph.anomaly import classify_anomaly
from app.services.knowledge_graph.graph import build_health_risk_graph
from app.services.llm.narrative import enrich_risk_explanation

_MIN_SCENES = 8


def assess_vegetation_risk(
    days_back: int = 365, recent_window_days: int = 60, include_llm_explanations: bool = True
) -> dict:
    """Compare recent NDVI (vegetation greenness) near the pilot city against its own
    longer-term baseline to flag vegetation-loss / deforestation-linked risk, propagated
    through the knowledge graph to temperature_rise.

    Same relative-anomaly framing as the NO2 risk assessment, for the same reason: there's
    no single absolute "healthy NDVI" threshold that means anything without knowing the
    specific land-cover type being observed, so this asks "greener or browner than usual
    for this exact spot" rather than comparing to a universal cutoff.

    Sentinel-2 gives one value per (mostly cloud-free) overpass rather than a daily series
    — Vellore had a real ~6-week gap during monsoon cloud cover — so `recent_window_days`
    is a trailing window over whatever scenes exist, not a fixed-count sample.
    """
    series = fetch_ndvi_series(days_back=days_back)
    if len(series) < _MIN_SCENES:
        raise RuntimeError(
            f"Only {len(series)} usable Sentinel-2 scenes for {settings.pilot_city} in the "
            f"last {days_back} days; need at least {_MIN_SCENES} to assess a trend."
        )

    baseline_mean = float(series.mean())
    baseline_std = float(series.std()) or 1e-9

    recent_cutoff = series.index.max() - pd.Timedelta(days=recent_window_days)
    recent = series[series.index >= recent_cutoff]
    recent_mean = float(recent.mean()) if len(recent) else float(series.iloc[-1])

    z = (recent_mean - baseline_mean) / baseline_std
    level = classify_anomaly(z, invert=True)
    pct_change = (recent_mean - baseline_mean) / baseline_mean * 100

    graph = build_health_risk_graph()
    outcomes = []
    for _, outcome, data in graph.out_edges("deforestation", data=True):
        template_explanation = (
            f"Recent vegetation greenness (NDVI) near {settings.pilot_city} averages "
            f"{pct_change:+.1f}% relative to its {days_back}-day baseline, which is "
            f"{level} for this location. {data['mechanism']}"
        )
        outcomes.append(
            {
                "outcome": outcome,
                "risk_level": level,
                "mechanism": data["mechanism"],
                "citation": data["citation"],
                "explanation": (
                    enrich_risk_explanation(
                        city=settings.pilot_city,
                        indicator_label="vegetation greenness (NDVI)",
                        risk_level=level,
                        pct_change=pct_change,
                        mechanism=data["mechanism"],
                        outcome=outcome,
                        fallback=template_explanation,
                    )
                    if include_llm_explanations
                    else template_explanation
                ),
            }
        )

    return {
        "city": settings.pilot_city,
        "indicator": "ndvi",
        "scene_count": len(series),
        "baseline_mean": baseline_mean,
        "baseline_std": baseline_std,
        "recent_mean": recent_mean,
        "recent_window_days": recent_window_days,
        "pct_change_vs_baseline": pct_change,
        "risk_level": level,
        "outcomes": outcomes,
    }
