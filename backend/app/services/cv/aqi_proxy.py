from datetime import datetime, timezone

from app.core.config import settings
from app.services.cv.earth_engine_client import get_ee


def get_no2_proxy(max_scenes: int = 30) -> dict:
    """Mean tropospheric NO2 column density near the pilot city, averaged over the most
    recent `max_scenes` available Sentinel-5P passes. Stand-in AQI proxy for cities with no
    CPCB/TNPCB ground station.

    Takes the latest available scenes rather than a fixed date window, since the Earth
    Engine catalog's ingestion lag for this dataset (observed ~10+ days for Vellore) is
    inconsistent and not worth guessing at.
    """
    ee = get_ee()

    point = ee.Geometry.Point([settings.pilot_lon, settings.pilot_lat])

    collection = (
        ee.ImageCollection("COPERNICUS/S5P/OFFL/L3_NO2")
        .filterBounds(point)
        .select("tropospheric_NO2_column_number_density")
        .sort("system:time_start", False)
        .limit(max_scenes)
    )

    timestamps = collection.aggregate_array("system:time_start").getInfo()
    if not timestamps:
        raise RuntimeError(
            f"No Sentinel-5P NO2 scenes found for {settings.pilot_city} at all. Check the "
            "pilot coordinates or Earth Engine dataset access."
        )

    value = (
        collection.mean()
        .reduceRegion(
            reducer=ee.Reducer.mean(), geometry=point.buffer(10000), scale=1000, bestEffort=True
        )
        .get("tropospheric_NO2_column_number_density")
        .getInfo()
    )

    def to_iso(ms: int) -> str:
        return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).isoformat()

    return {
        "city": settings.pilot_city,
        "metric": "tropospheric_NO2_column_number_density",
        "unit": "mol/m^2",
        "scene_count": len(timestamps),
        "earliest_scene": to_iso(min(timestamps)),
        "latest_scene": to_iso(max(timestamps)),
        "value": value,
    }
