import warnings

import numpy as np
import pandas as pd
from statsmodels.tsa.holtwinters import ExponentialSmoothing

_MIN_POINTS = 14


def holt_winters_baseline(series: pd.Series, horizon_days: int) -> pd.Series:
    series = series.dropna()
    if len(series) < _MIN_POINTS:
        raise RuntimeError(f"Need at least {_MIN_POINTS} days of history for a Holt-Winters baseline, got {len(series)}.")

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")  # statsmodels convergence chatter on flat series
        fit = ExponentialSmoothing(
            np.log1p(series.clip(lower=0)),
            trend="add",
            damped_trend=True,
            initialization_method="estimated",
        ).fit()
    index = pd.date_range(series.index.max() + pd.Timedelta(days=1), periods=horizon_days, freq="D")
    return pd.Series(np.expm1(fit.forecast(horizon_days).to_numpy()), index=index).clip(lower=0)
