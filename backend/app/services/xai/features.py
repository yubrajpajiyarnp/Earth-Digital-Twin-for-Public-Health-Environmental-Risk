import pandas as pd

FEATURE_COLUMNS = [
    "lag_1",
    "lag_2",
    "lag_3",
    "lag_7",
    "rolling_mean_7",
    "rolling_mean_30",
    "day_of_week",
]


def build_feature_frame(series: pd.Series) -> tuple[pd.DataFrame, pd.Series]:
    """Supervised 1-step-ahead feature frame from a daily series: each row's features are
    built only from data available before that day (lags + trailing rolling stats), target
    is that day's actual value. Rows without enough history for all lags/rolling windows
    are dropped."""
    df = pd.DataFrame({"value": series})
    df["lag_1"] = df["value"].shift(1)
    df["lag_2"] = df["value"].shift(2)
    df["lag_3"] = df["value"].shift(3)
    df["lag_7"] = df["value"].shift(7)
    df["rolling_mean_7"] = df["value"].shift(1).rolling(7).mean()
    df["rolling_mean_30"] = df["value"].shift(1).rolling(30).mean()
    df["day_of_week"] = df.index.dayofweek
    df = df.dropna()
    return df[FEATURE_COLUMNS], df["value"]
