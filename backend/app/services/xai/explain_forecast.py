import numpy as np
import shap
from sklearn.ensemble import RandomForestRegressor

from app.core.config import settings
from app.services.cv.no2_timeseries import fetch_no2_daily_series
from app.services.llm.narrative import enrich_forecast_summary
from app.services.xai.features import build_feature_frame

_MIN_ROWS_TO_EXPLAIN = 40  # need enough rows left after dropping NaNs from lag_7/rolling_30

_FEATURE_LABELS = {
    "lag_1": "yesterday's reading",
    "lag_2": "the reading 2 days ago",
    "lag_3": "the reading 3 days ago",
    "lag_7": "the reading a week ago",
    "rolling_mean_7": "the 7-day rolling average",
    "rolling_mean_30": "the 30-day rolling average",
    "day_of_week": "day-of-week pattern",
}


def explain_latest_prediction(days_back: int = 180) -> dict:
    """Explain what's driving the most recent NO2 reading using SHAP over a small
    RandomForest trained on lag/rolling features of the same series.

    This is a SEPARATE model from the Holt-Winters forecaster in
    app/services/forecasting/aqi_forecast.py, not a decomposition of it: Holt-Winters has
    no discrete "input features" SHAP can attribute to (it recurses on the series itself),
    so this builds a purpose-made, feature-based surrogate whose only job is explainability
    — "what's driving the recent trend" — not the multi-step forecast used elsewhere. See
    CLAUDE.md.
    """
    series = fetch_no2_daily_series(days_back=days_back)
    X, y = build_feature_frame(series)

    if len(X) < _MIN_ROWS_TO_EXPLAIN:
        raise RuntimeError(
            f"Only {len(X)} feature rows available for {settings.pilot_city} after building "
            f"lag/rolling features; need at least {_MIN_ROWS_TO_EXPLAIN}. Try a larger days_back."
        )

    model = RandomForestRegressor(n_estimators=200, max_depth=6, random_state=0)
    model.fit(X, y)

    explainer = shap.TreeExplainer(model)
    shap_values = explainer.shap_values(X)

    latest_date = X.index[-1]
    latest_shap = shap_values[-1]
    latest_features = X.iloc[-1]
    base_value = float(np.ravel(explainer.expected_value)[0])
    predicted = float(model.predict(X.iloc[[-1]])[0])
    actual = float(y.iloc[-1])

    contributions = sorted(
        (
            {
                "feature": col,
                "label": _FEATURE_LABELS.get(col, col),
                "feature_value": float(latest_features[col]),
                "contribution": float(latest_shap[i]),
            }
            for i, col in enumerate(X.columns)
        ),
        key=lambda c: abs(c["contribution"]),
        reverse=True,
    )

    return {
        "city": settings.pilot_city,
        "target_date": latest_date.strftime("%Y-%m-%d"),
        "model": "RandomForestRegressor (SHAP TreeExplainer), 1-step-ahead surrogate",
        "base_value": base_value,
        "predicted_value": predicted,
        "actual_value": actual,
        "contributions": contributions,
        "summary": enrich_forecast_summary(
            contributions,
            base_value,
            predicted,
            actual,
            fallback=_summarize(contributions, base_value, predicted),
        ),
    }


def _summarize(contributions: list[dict], base_value: float, predicted: float) -> str:
    top = contributions[:3]
    parts = []
    for c in top:
        direction = "pushed it up" if c["contribution"] > 0 else "pulled it down"
        parts.append(f"{c['label']} {direction} ({c['contribution']:+.2e})")
    return (
        f"Starting from a baseline expectation of {base_value:.2e}, the model landed on "
        f"{predicted:.2e}. Biggest drivers: " + "; ".join(parts) + "."
    )
