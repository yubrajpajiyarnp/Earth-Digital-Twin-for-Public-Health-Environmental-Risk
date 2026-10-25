import time

import httpx

from app.core.config import settings
from app.core.regions import TIMEZONE, resolve_region
from app.db.crud import get_setting
from app.ingestion.hydro_geology import open_meteo_get

# Nepal Standard Time, UTC+05:45.
_UTC_OFFSET_SECONDS = 20700

# AccuWeather is a failsafe, not a primary source: it's only ever called if Open-Meteo
# (which needs no key and has no meaningful rate limit for this app's traffic) fails.
# AccuWeather's free tier is capped at 50 calls/day, so it's used sparingly and its own
# result is cached the same way. A location key must be resolved once per coordinate pair
# before current conditions can be queried — that's cached indefinitely since it never
# changes for a fixed lat/lon.
_ACCUWEATHER_GEOPOSITION_URL = "https://dataservice.accuweather.com/locations/v1/cities/geoposition/search"
_ACCUWEATHER_CURRENT_CONDITIONS_URL = "https://dataservice.accuweather.com/currentconditions/v1/{location_key}"
_accuweather_location_keys: dict[str, str] = {}

# 1-hour cache would be too stale for something people expect to look "live" — weather can
# meaningfully shift in minutes, so this is cached much more briefly than the pricing
# services, just enough to avoid hammering the API if the dashboard is refreshed rapidly.
_CACHE_TTL_SECONDS = 600
_cache: dict[str, dict] = {}  # region id -> {"data", "fetched_at"}

# Standard WMO weather-code table (used by Open-Meteo and most other providers).
_WMO_DESCRIPTIONS = {
    0: "Clear sky",
    1: "Mainly clear",
    2: "Partly cloudy",
    3: "Overcast",
    45: "Fog",
    48: "Depositing rime fog",
    51: "Light drizzle",
    53: "Moderate drizzle",
    55: "Dense drizzle",
    56: "Light freezing drizzle",
    57: "Dense freezing drizzle",
    61: "Slight rain",
    63: "Moderate rain",
    65: "Heavy rain",
    66: "Light freezing rain",
    67: "Heavy freezing rain",
    71: "Slight snow",
    73: "Moderate snow",
    75: "Heavy snow",
    77: "Snow grains",
    80: "Slight rain showers",
    81: "Moderate rain showers",
    82: "Violent rain showers",
    85: "Slight snow showers",
    86: "Heavy snow showers",
    95: "Thunderstorm",
    96: "Thunderstorm with slight hail",
    99: "Thunderstorm with heavy hail",
}


def _fetch_from_open_meteo(region: dict) -> dict:
    payload = open_meteo_get(
        "api",
        "/v1/forecast",
        {
            "latitude": region["lat"],
            "longitude": region["lon"],
            "current": (
                "temperature_2m,relative_humidity_2m,apparent_temperature,"
                "surface_pressure,weather_code,wind_speed_10m,is_day,precipitation"
            ),
            "timezone": TIMEZONE,
        },
        "weather_api_key",
    )
    current = payload["current"]
    weather_code = current["weather_code"]

    return {
        "region": region["id"],
        "region_label": region["label"],
        "local_time": current["time"],
        "timezone": payload["timezone"],
        "utc_offset_seconds": payload["utc_offset_seconds"],
        "temperature_c": current["temperature_2m"],
        "feels_like_c": current["apparent_temperature"],
        "humidity_pct": current["relative_humidity_2m"],
        "pressure_hpa": current["surface_pressure"],
        "wind_speed_kmh": current["wind_speed_10m"],
        "precipitation_mm": current["precipitation"],
        "is_day": bool(current["is_day"]),
        "weather_code": weather_code,
        "weather_description": _WMO_DESCRIPTIONS.get(weather_code, "Unknown"),
        "climate_zone": region["climate_zone"],
        "source": "Open-Meteo",
    }


def _get_accuweather_location_key(api_key: str, region: dict) -> str:
    if region["id"] in _accuweather_location_keys:
        return _accuweather_location_keys[region["id"]]

    response = httpx.get(
        _ACCUWEATHER_GEOPOSITION_URL,
        params={"apikey": api_key, "q": f"{region['lat']},{region['lon']}"},
        timeout=15,
    )
    response.raise_for_status()
    location_key = response.json()["Key"]
    _accuweather_location_keys[region["id"]] = location_key
    return location_key


def _fetch_from_accuweather(region: dict) -> dict:
    # Admin-managed override (set via /api/admin/settings) takes priority over the
    # .env-loaded default, matching the Open-Meteo keys' resolution pattern.
    api_key = get_setting("accuweather_api_key") or settings.accuweather_api_key
    if not api_key:
        raise RuntimeError(
            "ACCUWEATHER_API_KEY not set. Get a free key from developer.accuweather.com "
            "and add it to backend/.env, or set it via the admin settings panel, to enable "
            "the AccuWeather failsafe."
        )

    location_key = _get_accuweather_location_key(api_key, region)
    response = httpx.get(
        _ACCUWEATHER_CURRENT_CONDITIONS_URL.format(location_key=location_key),
        params={"apikey": api_key, "details": "true"},
        timeout=15,
    )
    response.raise_for_status()
    conditions = response.json()[0]

    return {
        "region": region["id"],
        "region_label": region["label"],
        "local_time": conditions["LocalObservationDateTime"],
        "timezone": TIMEZONE,
        "utc_offset_seconds": _UTC_OFFSET_SECONDS,
        "temperature_c": conditions["Temperature"]["Metric"]["Value"],
        "feels_like_c": conditions["RealFeelTemperature"]["Metric"]["Value"],
        "humidity_pct": conditions["RelativeHumidity"],
        "pressure_hpa": conditions["Pressure"]["Metric"]["Value"],
        "wind_speed_kmh": conditions["Wind"]["Speed"]["Metric"]["Value"],
        "precipitation_mm": conditions.get("PrecipitationSummary", {}).get("PastHour", {}).get("Metric", {}).get("Value"),
        "is_day": conditions["IsDayTime"],
        "weather_code": None,
        "weather_description": conditions["WeatherText"],
        "climate_zone": region["climate_zone"],
        "source": "AccuWeather (fallback)",
    }


def get_last_source() -> str | None:
    """Which provider actually served the most recently cached weather reading, if any —
    used by the admin data-sources card to show whether the AccuWeather failsafe has
    kicked in, without triggering a new fetch just to check."""
    latest = max(_cache.values(), key=lambda c: c["fetched_at"], default=None)
    return latest["data"]["source"] if latest else None


def get_current_weather(region_id: str | None = None) -> dict:
    region = resolve_region(region_id)
    now = time.time()
    cached = _cache.get(region["id"])
    if cached is not None and (now - cached["fetched_at"]) < _CACHE_TTL_SECONDS:
        return cached["data"]

    try:
        data = _fetch_from_open_meteo(region)
    except RuntimeError as primary_exc:
        try:
            data = _fetch_from_accuweather(region)
        except (httpx.HTTPError, RuntimeError, KeyError, IndexError) as fallback_exc:
            raise RuntimeError(
                f"Open-Meteo request failed ({primary_exc}), and the AccuWeather "
                f"failsafe also failed ({fallback_exc})."
            ) from fallback_exc

    _cache[region["id"]] = {"data": data, "fetched_at": now}
    return data
