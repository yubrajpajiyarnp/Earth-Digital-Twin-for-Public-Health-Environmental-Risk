from app.core.config import settings
from app.services.cv.rainfall_timeseries import fetch_rainfall_daily_series
from app.services.knowledge_graph.anomaly import classify_anomaly
from app.services.knowledge_graph.graph import build_health_risk_graph

_MIN_DAYS = 21  # need enough days for a rolling window + a meaningful baseline distribution


def assess_flood_risk(days_back: int = 180, recent_window_days: int = 7) -> dict:
    """Compare the most recent `recent_window_days`-day rainfall TOTAL (not daily mean —
    flood risk is about short-window accumulation, e.g. a week of heavy rain, not a
    single wet day) against the distribution of same-length rolling totals over the
    trailing `days_back` days, then propagate that anomaly through the knowledge graph to
    every outcome linked to rainfall_extreme.

    Same baseline-relative framing as the other risk assessments, for the same reason:
    there's no absolute "flood threshold" for this exact 10km buffer around Vellore to
    compare against, only what's unusual relative to its own recent weather.
    """
    series = fetch_rainfall_daily_series(days_back=days_back)
    if len(series) < _MIN_DAYS:
        raise RuntimeError(
            f"Only {len(series)} days of rainfall history for {settings.pilot_city}; need "
            f"at least {_MIN_DAYS} to assess flood risk. Try a larger days_back window."
        )

    rolling_sum = series.rolling(recent_window_days).sum().dropna()
    baseline_mean = float(rolling_sum.mean())
    baseline_std = float(rolling_sum.std()) or 1e-9
    recent_sum = float(rolling_sum.iloc[-1])

    z = (recent_sum - baseline_mean) / baseline_std
    level = classify_anomaly(z)  # higher rainfall total = elevated flood risk
    pct_change = (recent_sum - baseline_mean) / baseline_mean * 100 if baseline_mean else 0.0

    graph = build_health_risk_graph()
    outcomes = []
    for _, outcome, data in graph.out_edges("rainfall_extreme", data=True):
        outcomes.append(
            {
                "outcome": outcome,
                "risk_level": level,
                "mechanism": data["mechanism"],
                "citation": data["citation"],
                "explanation": (
                    f"The last {recent_window_days} days of rainfall near "
                    f"{settings.pilot_city} totaled {recent_sum:.1f}mm, "
                    f"{pct_change:+.1f}% relative to the typical {recent_window_days}-day "
                    f"total over the past {days_back} days, which is {level} for this "
                    f"location. {data['mechanism']}"
                ),
            }
        )

    return {
        "city": settings.pilot_city,
        "indicator": "rainfall",
        "recent_window_days": recent_window_days,
        "recent_total_mm": recent_sum,
        "baseline_mean_mm": baseline_mean,
        "baseline_std_mm": baseline_std,
        "pct_change_vs_baseline": pct_change,
        "risk_level": level,
        "outcomes": outcomes,
    }
