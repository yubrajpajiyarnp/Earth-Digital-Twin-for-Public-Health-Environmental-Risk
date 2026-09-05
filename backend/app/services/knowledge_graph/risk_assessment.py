from app.core.config import settings
from app.services.cv.no2_timeseries import fetch_no2_daily_series
from app.services.forecasting.aqi_forecast import forecast_no2
from app.services.knowledge_graph.anomaly import classify_anomaly
from app.services.knowledge_graph.graph import build_health_risk_graph
from app.services.llm.narrative import enrich_risk_explanation


def assess_no2_health_risk(
    horizon_days: int = 7, days_back: int = 180, include_llm_explanations: bool = True
) -> dict:
    """Compare the forecasted NO2 proxy against its own historical baseline (z-score /
    % change) for the pilot city, then propagate that anomaly through the knowledge graph
    to every health outcome linked to NO2/pollution, producing one risk statement per
    outcome.

    This is a RELATIVE, anomaly-based assessment, not a calibrated absolute-AQI health
    risk: Sentinel-5P NO2 is a tropospheric column density (mol/m^2), not a ground-level
    concentration (ug/m^3) that WHO/CPCB thresholds are defined against, and converting
    between the two needs a boundary-layer model this project doesn't have. So the
    question answered here is "worse than usual for this location", not "above an
    absolute limit" — see CLAUDE.md.
    """
    history = fetch_no2_daily_series(days_back=days_back)
    baseline_mean = float(history.mean())
    baseline_std = float(history.std()) or 1e-12

    forecast = forecast_no2(horizon_days=horizon_days, days_back=days_back)
    forecast_values = [p["value"] for p in forecast["forecast"]]
    forecast_mean = sum(forecast_values) / len(forecast_values)

    z = (forecast_mean - baseline_mean) / baseline_std
    level = classify_anomaly(z)
    pct_change = (forecast_mean - baseline_mean) / baseline_mean * 100

    graph = build_health_risk_graph()
    outcomes = []
    for _, outcome, data in graph.out_edges("no2_column_density", data=True):
        template_explanation = (
            f"The forecasted NO2 pollution proxy for {settings.pilot_city} over the "
            f"next {horizon_days} days averages {pct_change:+.1f}% relative to its "
            f"{days_back}-day baseline, which is {level} for this location. "
            f"{data['mechanism']}"
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
                        indicator_label="NO2 pollution proxy (forecasted, next "
                        f"{horizon_days} days)",
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
        "indicator": "no2_column_density",
        "baseline_mean": baseline_mean,
        "baseline_std": baseline_std,
        "forecast_mean": forecast_mean,
        "pct_change_vs_baseline": pct_change,
        "risk_level": level,
        "horizon_days": horizon_days,
        "outcomes": outcomes,
    }
