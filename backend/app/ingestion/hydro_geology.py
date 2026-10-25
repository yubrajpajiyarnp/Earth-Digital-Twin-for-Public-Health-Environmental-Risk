"""Hydro-geological feeds for the two Nepal regions (see app/core/regions.py):

  - hourly precipitation, surface pressure and deep soil moisture (7–28 cm, 28–100 cm),
    as a 15-day ECMWF forecast or an ERA5 historical archive (Open-Meteo)
  - daily river discharge per Kathmandu river, history + GloFAS forecast (Open-Meteo Flood)
  - mean terrain slope over each region from the 90 m Copernicus DEM (Open-Meteo Elevation)
  - actual past flood/landslide incidents from Nepal's NDRRMA BIPAD portal

Key routing (CLAUDE.md Part 2): Kathmandu weather uses WEATHER_API_KEY, the Mugling
corridor's soil/rain/terrain requests use LANDSLIDE_API_KEY, discharge uses FLOOD_API_KEY.
Every key is optional — a blank key uses Open-Meteo's free non-commercial host, a set key
the customer-* host. BIPAD needs no key.

Fetch-only: no feature engineering or modelling happens here (that's
app/models/simulation/disaster_ml.py). Failures raise RuntimeError with a readable
message, which the routes map to HTTP 503.
"""

import math
import threading
import time

import httpx
import numpy as np
import pandas as pd

from app.core.config import settings
from app.core.regions import TIMEZONE
from app.db.crud import get_setting

_HOURLY_VARS = {
    "precipitation": "precip_mm",
    "surface_pressure": "pressure_hpa",
    "soil_moisture_7_to_28cm": "sm_7_28",
    "soil_moisture_28_to_100cm": "sm_28_100",
}
# The only Open-Meteo forecast model that exposes the ERA5-style 7–28 cm / 28–100 cm soil
# layers the models are trained on (others offer 9–27 / 27–81 cm). 15-day horizon.
_FORECAST_MODEL = "ecmwf_ifs025"
_MAX_FORECAST_DAYS = 15

_BIPAD_URL = "https://bipadportal.gov.np/api/v1/incident/"
_BIPAD_PAGE_SIZE = 2000

# Forecasts and discharge change a few times a day at most; incidents are reported daily.
_FORECAST_CACHE_TTL_SECONDS = 15 * 60
_INCIDENT_CACHE_TTL_SECONDS = 6 * 60 * 60
_cache: dict[tuple, tuple[float, object]] = {}
_cache_lock = threading.Lock()
_slope_cache: dict[str, float] = {}

# Slope is sampled on a 6x6 grid over the region's bbox, each point differenced against
# neighbours ~110 m away (just above the DEM's 90 m resolution).
_SLOPE_GRID = 6
_SLOPE_STEP_DEG = 0.001
_ELEVATION_BATCH = 100  # Elevation API limit per request


def _cached(key: tuple, ttl: float, fetch):
    now = time.monotonic()
    with _cache_lock:
        hit = _cache.get(key)
    if hit is not None and now - hit[0] < ttl:
        return hit[1]
    value = fetch()
    with _cache_lock:
        _cache[key] = (now, value)
    return value


def _api_key(key_name: str) -> str | None:
    return get_setting(key_name) or getattr(settings, key_name)


def open_meteo_get(service: str, path: str, params: dict, key_name: str) -> dict:
    key = _api_key(key_name)
    host = f"https://customer-{service}.open-meteo.com" if key else f"https://{service}.open-meteo.com"
    if key:
        params = {**params, "apikey": key}
    try:
        response = httpx.get(f"{host}{path}", params=params, timeout=120)
        response.raise_for_status()
        payload = response.json()
    except httpx.HTTPStatusError as exc:
        detail = exc.response.text[:200]
        raise RuntimeError(f"Open-Meteo {service} request failed ({exc.response.status_code}): {detail}") from exc
    except (httpx.HTTPError, ValueError) as exc:
        raise RuntimeError(f"Open-Meteo {service} request failed: {exc}") from exc
    if payload.get("error"):
        raise RuntimeError(f"Open-Meteo {service} error: {payload.get('reason')}")
    return payload


def fetch_hourly_weather(
    region: dict,
    *,
    start_date: str | None = None,
    end_date: str | None = None,
    past_days: int = 14,
    forecast_days: int = 14,
) -> pd.DataFrame:
    """Hourly precip_mm, pressure_hpa, sm_7_28, sm_28_100 at the region's point, in
    Asia/Kathmandu local time. With start_date/end_date it reads the ERA5 archive (~5-day
    lag); otherwise the ECMWF forecast with `past_days` of recent history prepended."""
    params = {
        "latitude": region["lat"],
        "longitude": region["lon"],
        "hourly": ",".join(_HOURLY_VARS),
        "timezone": TIMEZONE,
    }
    if start_date:
        params.update(start_date=start_date, end_date=end_date)
        payload = open_meteo_get("archive-api", "/v1/archive", params, region["key_name"])
    else:
        params.update(
            models=_FORECAST_MODEL,
            past_days=past_days,
            forecast_days=min(forecast_days, _MAX_FORECAST_DAYS),
        )
        payload = _cached(
            ("weather", region["id"], past_days, forecast_days),
            _FORECAST_CACHE_TTL_SECONDS,
            lambda: open_meteo_get("api", "/v1/forecast", params, region["key_name"]),
        )

    hourly = payload["hourly"]
    frame = pd.DataFrame(
        {col: hourly[var] for var, col in _HOURLY_VARS.items()},
        index=pd.to_datetime(hourly["time"]),
        dtype=float,
    )
    # ECMWF steps beyond ~day 6 are 3/6-hourly; Open-Meteo leaves gaps as null.
    return frame.interpolate(limit_direction="both")


def fetch_river_discharge(
    river: dict,
    *,
    start_date: str | None = None,
    end_date: str | None = None,
    past_days: int = 90,
    forecast_days: int = 14,
) -> pd.Series:
    """Daily GloFAS river discharge (m³/s) at one river's grid cell. With dates it returns
    that historical range; otherwise `past_days` of history plus the GloFAS forecast."""
    params = {"latitude": river["lat"], "longitude": river["lon"], "daily": "river_discharge"}
    if start_date:
        params.update(start_date=start_date, end_date=end_date)
        payload = open_meteo_get("flood-api", "/v1/flood", params, "flood_api_key")
    else:
        params.update(past_days=past_days, forecast_days=forecast_days)
        payload = _cached(
            ("discharge", river["id"], past_days, forecast_days),
            _FORECAST_CACHE_TTL_SECONDS,
            lambda: open_meteo_get("flood-api", "/v1/flood", params, "flood_api_key"),
        )

    daily = payload["daily"]
    series = pd.Series(daily["river_discharge"], index=pd.to_datetime(daily["time"]), dtype=float)
    series = series.dropna()
    if series.empty:
        raise RuntimeError(f"GloFAS returned no discharge for the {river['name']} cell.")
    return series


def fetch_region_slope_deg(region: dict) -> float:
    """Mean terrain slope (degrees) over the region's bbox, from the Copernicus 90 m DEM.
    Terrain doesn't change, so this is cached for the life of the process."""
    if region["id"] in _slope_cache:
        return _slope_cache[region["id"]]

    lat_min, lon_min, lat_max, lon_max = region["bbox"]
    centres = [
        (lat_min + (lat_max - lat_min) * i / (_SLOPE_GRID - 1), lon_min + (lon_max - lon_min) * j / (_SLOPE_GRID - 1))
        for i in range(_SLOPE_GRID)
        for j in range(_SLOPE_GRID)
    ]
    d = _SLOPE_STEP_DEG
    coords = []
    for lat, lon in centres:
        coords += [(lat + d, lon), (lat - d, lon), (lat, lon + d), (lat, lon - d)]

    elevations = []
    for i in range(0, len(coords), _ELEVATION_BATCH):
        batch = coords[i : i + _ELEVATION_BATCH]
        payload = open_meteo_get(
            "api",
            "/v1/elevation",
            {
                "latitude": ",".join(f"{c[0]:.5f}" for c in batch),
                "longitude": ",".join(f"{c[1]:.5f}" for c in batch),
            },
            region["key_name"],
        )
        elevations += payload["elevation"]

    slopes = []
    for k, (lat, _) in enumerate(centres):
        n, s, e, w = elevations[4 * k : 4 * k + 4]
        dy = 2 * d * 110_574
        dx = 2 * d * 111_320 * math.cos(math.radians(lat))
        slopes.append(math.degrees(math.atan(math.hypot((e - w) / dx, (n - s) / dy))))

    slope = float(np.mean(slopes))
    _slope_cache[region["id"]] = slope
    return slope


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    a = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lon2 - lon1) / 2) ** 2
    return 2 * 6371 * math.asin(math.sqrt(a))


def _fetch_incidents_uncached(region: dict, since: str) -> pd.DataFrame:
    rows = []
    offset = 0
    while True:
        try:
            response = httpx.get(
                _BIPAD_URL,
                params={
                    "format": "json",
                    "hazard": region["bipad_hazard_id"],
                    "incident_on__gt": since,
                    "ordering": "incident_on",
                    "fields": "id,point,incident_on",
                    "limit": _BIPAD_PAGE_SIZE,
                    "offset": offset,
                },
                timeout=120,
            )
            response.raise_for_status()
            page = response.json()["results"]
        except (httpx.HTTPError, ValueError, KeyError) as exc:
            raise RuntimeError(f"BIPAD incident request failed: {exc}") from exc
        rows += page
        if len(page) < _BIPAD_PAGE_SIZE:
            break
        offset += _BIPAD_PAGE_SIZE

    records = []
    for r in rows:
        point = r.get("point")
        when = r.get("incidentOn") or r.get("incident_on")
        if not point or not when:
            continue
        lon, lat = point["coordinates"][:2]
        distance = _haversine_km(region["lat"], region["lon"], lat, lon)
        if distance <= region["incident_radius_km"]:
            # BIPAD timestamps are Nepal local time (+05:45); the date part is the local day.
            records.append({"id": r["id"], "date": pd.Timestamp(when[:10]), "lat": lat, "lon": lon, "distance_km": distance})
    return pd.DataFrame(records, columns=["id", "date", "lat", "lon", "distance_km"])


def fetch_incidents(region: dict, since: str = "2011-01-01") -> pd.DataFrame:
    """Verified BIPAD incidents of the region's hazard type (flood or landslide) within its
    incident radius since `since`: one row per incident (id, date, lat, lon, distance_km).
    Reporting density rises sharply after ~2016 — reporting bias, not necessarily more
    hazard."""
    return _cached(
        ("incidents", region["id"], since),
        _INCIDENT_CACHE_TTL_SECONDS,
        lambda: _fetch_incidents_uncached(region, since),
    )
