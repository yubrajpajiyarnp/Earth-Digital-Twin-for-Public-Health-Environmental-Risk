import statistics

from app.core.config import settings
from app.services.fauna.gbif_observations import fetch_monthly_occurrence_counts
from app.services.knowledge_graph.anomaly import classify_anomaly
from app.services.knowledge_graph.graph import build_health_risk_graph

_MIN_MONTHS = 6


def assess_fauna_disruption(num_months: int = 13, chunk_days: int = 30) -> dict:
    """Compare the most recent month's GBIF wildlife-observation count against the
    distribution of counts over the preceding months, then propagate that anomaly
    through the knowledge graph to fauna_disruption.

    CAVEAT worth repeating from gbif_observations.py: this measures reporting activity
    (confounded by observer effort), not a validated population survey. On top of that,
    the most recent window can look artificially low simply because citizen-science
    platforms publish to GBIF with a lag (the same catalog-lag pattern seen with every
    other external source in this project, e.g. Sentinel-5P) — a below-baseline reading
    in the latest month is NOT strong evidence of a real drop, and this function doesn't
    try to correct for it. Treat `risk_level` here as more illustrative than the other
    (satellite-derived) indicators. See CLAUDE.md.
    """
    windows = fetch_monthly_occurrence_counts(num_months=num_months, chunk_days=chunk_days)
    if len(windows) < _MIN_MONTHS:
        raise RuntimeError(
            f"Only {len(windows)} months of GBIF data for {settings.pilot_city}; need at "
            f"least {_MIN_MONTHS} to assess a trend."
        )

    counts = [w["count"] for w in windows]
    recent_count = counts[-1]
    baseline_counts = counts[:-1]
    baseline_mean = statistics.mean(baseline_counts)
    baseline_std = statistics.pstdev(baseline_counts) or 1e-9

    z = (recent_count - baseline_mean) / baseline_std
    level = classify_anomaly(z, invert=True)  # fewer observations => elevated risk
    pct_change = (recent_count - baseline_mean) / baseline_mean * 100 if baseline_mean else 0.0

    graph = build_health_risk_graph()
    outcomes = []
    for _, outcome, data in graph.out_edges("wildlife_activity", data=True):
        outcomes.append(
            {
                "outcome": outcome,
                "risk_level": level,
                "mechanism": data["mechanism"],
                "citation": data["citation"],
                "explanation": (
                    f"GBIF recorded {recent_count} wildlife observations near "
                    f"{settings.pilot_city} in the most recent {chunk_days}-day window, "
                    f"{pct_change:+.1f}% relative to the prior {len(baseline_counts)} "
                    f"months' typical count, which is {level} for this location (note: "
                    "recent-month counts can read low simply from GBIF publishing lag, "
                    "not necessarily reduced activity). "
                    f"{data['mechanism']}"
                ),
            }
        )

    return {
        "city": settings.pilot_city,
        "indicator": "wildlife_activity",
        "recent_count": recent_count,
        "baseline_mean": baseline_mean,
        "baseline_std": baseline_std,
        "pct_change_vs_baseline": pct_change,
        "risk_level": level,
        "months_series": windows,
        "outcomes": outcomes,
    }
