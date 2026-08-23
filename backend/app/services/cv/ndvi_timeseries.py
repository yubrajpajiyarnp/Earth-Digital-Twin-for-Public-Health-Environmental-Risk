from datetime import date, timedelta

import pandas as pd

from app.core.config import settings
from app.db.crud import save_ndvi_series
from app.services.cv.earth_engine_client import get_ee

# Scene Classification Layer codes to keep: 4=vegetation, 5=bare soil, 6=water, 7=unclassified.
# Excludes clouds (8/9/10), cloud shadow (3), snow (11) etc.
_SCL_KEEP = [4, 5, 6, 7]


def fetch_ndvi_series(days_back: int = 365, buffer_m: int = 5000) -> pd.Series:
    """Cloud-masked mean NDVI near the pilot city from Sentinel-2 SR, one value per scene
    (not reindexed to daily — optical imagery has real gaps from cloud cover that
    shouldn't be papered over with interpolation the way the NO2 series is)."""
    ee = get_ee()
    point = ee.Geometry.Point([settings.pilot_lon, settings.pilot_lat])
    region = point.buffer(buffer_m)
    end = date.today()
    start = end - timedelta(days=days_back)

    collection = (
        ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
        .filterDate(str(start), str(end))
        .filterBounds(region)
    )

    def to_feature(image):
        scl = image.select("SCL")
        # remap()'s output band is named "remapped" by default, NOT "SCL" — must rename or
        # the later .get("clear", ...) lookup silently misses and falls back to its default.
        cloud_free = scl.remap(_SCL_KEEP, [1] * len(_SCL_KEEP), 0).rename("clear")
        ndvi = image.normalizedDifference(["B8", "B4"]).updateMask(cloud_free).rename("ndvi")
        # .get(key, default) matters here too: a scene whose SCL band doesn't fully cover the
        # buffered region (common at tile edges) makes reduceRegion return an EMPTY dict for
        # that band, and .get() without a default throws server-side and kills the whole
        # .map() call for every scene, not just the bad one.
        value = ndvi.reduceRegion(
            reducer=ee.Reducer.mean(), geometry=region, scale=20, bestEffort=True
        ).get("ndvi", -99)
        clear_frac = cloud_free.reduceRegion(
            reducer=ee.Reducer.mean(), geometry=region, scale=60, bestEffort=True
        ).get("clear", 0)
        return ee.Feature(
            None,
            {"date": image.date().format("YYYY-MM-dd"), "value": value, "clear_frac": clear_frac},
        )

    def _is_usable(props: dict) -> bool:
        value = props.get("value")
        clear_frac = props.get("clear_frac")
        return value is not None and value > -90 and (clear_frac or 0) > 0.5

    features = collection.map(to_feature).getInfo()["features"]
    rows = [
        (f["properties"]["date"], f["properties"]["value"])
        for f in features
        if _is_usable(f["properties"])
    ]
    if not rows:
        raise RuntimeError(
            f"No usable (mostly cloud-free) Sentinel-2 scenes found for {settings.pilot_city} "
            f"in the last {days_back} days."
        )

    df = pd.DataFrame(rows, columns=["date", "value"])
    df["date"] = pd.to_datetime(df["date"])
    daily = df.groupby("date")["value"].mean().sort_index()
    save_ndvi_series(settings.pilot_city, daily)
    return daily
