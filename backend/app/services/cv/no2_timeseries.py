from datetime import date, timedelta

import pandas as pd

from app.core.config import settings
from app.db.crud import save_no2_series
from app.services.cv.earth_engine_client import get_ee

_BAND = "tropospheric_NO2_column_number_density"


def fetch_no2_daily_series(days_back: int = 180) -> pd.Series:
    """Daily-mean NO2 column density near the pilot city over the trailing `days_back` days,
    reindexed to a continuous daily DatetimeIndex with gaps linearly interpolated (needed for
    forecasting models that assume a regular frequency; raw satellite coverage has gap days
    from cloud cover and the catalog's own ingestion lag — see CLAUDE.md).
    """
    ee = get_ee()
    point = ee.Geometry.Point([settings.pilot_lon, settings.pilot_lat])
    end = date.today()
    start = end - timedelta(days=days_back)

    collection = (
        ee.ImageCollection("COPERNICUS/S5P/OFFL/L3_NO2")
        .filterDate(str(start), str(end))
        .filterBounds(point)
        .select(_BAND)
    )

    def to_feature(image):
        value = image.reduceRegion(
            reducer=ee.Reducer.mean(), geometry=point.buffer(10000), scale=1000, bestEffort=True
        ).get(_BAND)
        return ee.Feature(None, {"date": image.date().format("YYYY-MM-dd"), "value": value})

    features = collection.map(to_feature).getInfo()["features"]
    rows = [
        (f["properties"]["date"], f["properties"]["value"])
        for f in features
        if f["properties"].get("value") is not None
    ]
    if not rows:
        raise RuntimeError(
            f"No Sentinel-5P NO2 scenes with valid readings for {settings.pilot_city} in the "
            f"last {days_back} days."
        )

    df = pd.DataFrame(rows, columns=["date", "value"])
    df["date"] = pd.to_datetime(df["date"])
    daily = df.groupby("date")["value"].mean().sort_index()

    # Persist the raw (pre-interpolation) readings only — the interpolated/filled values
    # below are for the forecaster's benefit, not real observations, and shouldn't be
    # stored as if they were.
    save_no2_series(settings.pilot_city, daily)

    full_index = pd.date_range(daily.index.min(), daily.index.max(), freq="D")
    daily = daily.reindex(full_index).interpolate(method="linear").ffill().bfill()
    daily.index.name = "date"
    return daily
