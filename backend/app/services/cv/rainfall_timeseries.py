from datetime import date, timedelta

import pandas as pd

from app.core.config import settings
from app.db.crud import save_rainfall_series
from app.services.cv.earth_engine_client import get_ee

_BAND = "precipitation"


def fetch_rainfall_daily_series(days_back: int = 180, buffer_m: int = 10000) -> pd.Series:
    """Daily rainfall (mm) near the pilot city from CHIRPS (UCSB-CHG/CHIRPS/DAILY), one
    value per calendar day — unlike Sentinel-5P/2, CHIRPS already publishes exactly one
    global image per day, so no per-scene grouping is needed the way NO2/NDVI required."""
    ee = get_ee()
    point = ee.Geometry.Point([settings.pilot_lon, settings.pilot_lat])
    region = point.buffer(buffer_m)
    end = date.today()
    start = end - timedelta(days=days_back)

    collection = (
        ee.ImageCollection("UCSB-CHG/CHIRPS/DAILY")
        .filterDate(str(start), str(end))
        .filterBounds(region)
        .select(_BAND)
    )

    def to_feature(image):
        value = image.reduceRegion(
            reducer=ee.Reducer.mean(), geometry=region, scale=5500, bestEffort=True
        ).get(_BAND, -99)
        return ee.Feature(None, {"date": image.date().format("YYYY-MM-dd"), "value": value})

    features = collection.map(to_feature).getInfo()["features"]

    def _is_usable(props: dict) -> bool:
        value = props.get("value")
        return value is not None and value > -90

    rows = [
        (f["properties"]["date"], f["properties"]["value"])
        for f in features
        if _is_usable(f["properties"])
    ]
    if not rows:
        raise RuntimeError(
            f"No usable CHIRPS rainfall data for {settings.pilot_city} in the last "
            f"{days_back} days."
        )

    df = pd.DataFrame(rows, columns=["date", "value"])
    df["date"] = pd.to_datetime(df["date"])
    daily = df.groupby("date")["value"].mean().sort_index()
    save_rainfall_series(settings.pilot_city, daily)
    return daily
