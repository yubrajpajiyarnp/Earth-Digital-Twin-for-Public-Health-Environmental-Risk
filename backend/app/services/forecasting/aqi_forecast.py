from statsmodels.tsa.holtwinters import ExponentialSmoothing

from app.core.config import settings
from app.services.cv.no2_timeseries import fetch_no2_daily_series

_MIN_POINTS_TO_FORECAST = 14
_MIN_POINTS_FOR_WEEKLY_SEASONALITY = 21


def forecast_no2(horizon_days: int = 7, days_back: int = 180) -> dict:
    """Forecast the NO2 AQI-proxy `horizon_days` ahead using Holt-Winters exponential
    smoothing over the trailing `days_back` days of daily satellite readings."""
    series = fetch_no2_daily_series(days_back=days_back)

    if len(series) < _MIN_POINTS_TO_FORECAST:
        raise RuntimeError(
            f"Only {len(series)} days of history available for {settings.pilot_city}; need at "
            f"least {_MIN_POINTS_TO_FORECAST} to fit a forecast. Try a larger days_back window."
        )

    has_seasonality = len(series) >= _MIN_POINTS_FOR_WEEKLY_SEASONALITY
    model = ExponentialSmoothing(
        series,
        trend="add",
        damped_trend=True,
        seasonal="add" if has_seasonality else None,
        seasonal_periods=7 if has_seasonality else None,
        initialization_method="estimated",
    )
    fit = model.fit()
    forecast = fit.forecast(horizon_days)

    return {
        "city": settings.pilot_city,
        "metric": "tropospheric_NO2_column_number_density",
        "unit": "mol/m^2",
        "history_points": len(series),
        "history_start": series.index.min().strftime("%Y-%m-%d"),
        "history_end": series.index.max().strftime("%Y-%m-%d"),
        "horizon_days": horizon_days,
        "forecast": [
            {"date": d.strftime("%Y-%m-%d"), "value": float(v)}
            for d, v in forecast.items()
        ],
    }
