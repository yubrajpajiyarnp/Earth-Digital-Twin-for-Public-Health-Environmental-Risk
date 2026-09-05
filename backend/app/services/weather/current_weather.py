import time

import httpx

from app.core.config import settings
from app.db.crud import get_setting

_URL = "https://api.open-meteo.com/v1/forecast"

# AccuWeather is a failsafe, not a primary source: it's only ever called if Open-Meteo
# (which needs no key and has no meaningful rate limit for this app's traffic) fails.
# AccuWeather's free tier is capped at 50 calls/day, so it's used sparingly and its own
# result is cached the same way. A location key must be resolved once per coordinate pair
# before current conditions can be queried — that's cached indefinitely since it never
# changes for a fixed lat/lon.
_ACCUWEATHER_GEOPOSITION_URL = "https://dataservice.accuweather.com/locations/v1/cities/geoposition/search"
_ACCUWEATHER_CURRENT_CONDITIONS_URL = "https://dataservice.accuweather.com/currentconditions/v1/{location_key}"
_accuweather_location_key_cache: dict = {"key": None}

# 1-hour cache would be too stale for something people expect to look "live" — weather can
# meaningfully shift in minutes, so this is cached much more briefly than the pricing
# services, just enough to avoid hammering the API if the dashboard is refreshed rapidly.
_CACHE_TTL_SECONDS = 600
_cache: dict = {"data": None, "fetched_at": 0.0}

# Standard WMO weather-code table (used by Open-Meteo and most other providers) — the
# subset actually reachable for Vellore's climate, plus the full range for completeness.
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

# Vellore's Koppen-Geiger climate classification is a fixed geographic fact, not something
# that needs a live API call — included alongside the live reading for context, not as a
# substitute for it.
CLIMATE_ZONE = "Tropical wet and dry climate (Koppen \"Aw\")"


def _fetch_from_open_meteo() -> dict:
    response = httpx.get(
        _URL,
        params={
            "latitude": settings.pilot_lat,
            "longitude": settings.pilot_lon,
            "current": (
                "temperature_2m,relative_humidity_2m,apparent_temperature,"
                "surface_pressure,weather_code,wind_speed_10m,is_day"
            ),
            "timezone": "Asia/Kolkata",
        },
        timeout=15,
    )
    response.raise_for_status()
    payload = response.json()
    current = payload["current"]
    weather_code = current["weather_code"]

    return {
        "city": settings.pilot_city,
        "local_time": current["time"],
        "timezone": payload["timezone"],
        "utc_offset_seconds": payload["utc_offset_seconds"],
        "temperature_c": current["temperature_2m"],
        "feels_like_c": current["apparent_temperature"],
        "humidity_pct": current["relative_humidity_2m"],
        "pressure_hpa": current["surface_pressure"],
        "wind_speed_kmh": current["wind_speed_10m"],
        "is_day": bool(current["is_day"]),
        "weather_code": weather_code,
        "weather_description": _WMO_DESCRIPTIONS.get(weather_code, "Unknown"),
        "climate_zone": CLIMATE_ZONE,
        "source": "Open-Meteo",
    }


def _get_accuweather_location_key(api_key: str) -> str:
    if _accuweather_location_key_cache["key"] is not None:
        return _accuweather_location_key_cache["key"]

    response = httpx.get(
        _ACCUWEATHER_GEOPOSITION_URL,
        params={"apikey": api_key, "q": f"{settings.pilot_lat},{settings.pilot_lon}"},
        timeout=15,
    )
    response.raise_for_status()
    location_key = response.json()["Key"]
    _accuweather_location_key_cache["key"] = location_key
    return location_key


def _fetch_from_accuweather() -> dict:
    # Admin-managed override (set via /api/admin/settings) takes priority over the
    # .env-loaded default, matching the pricing services' key-resolution pattern.
    api_key = get_setting("accuweather_api_key") or settings.accuweather_api_key
    if not api_key:
        raise RuntimeError(
            "ACCUWEATHER_API_KEY not set. Get a free key from developer.accuweather.com "
            "and add it to backend/.env, or set it via the admin settings panel, to enable "
            "the AccuWeather failsafe."
        )

    location_key = _get_accuweather_location_key(api_key)
    response = httpx.get(
        _ACCUWEATHER_CURRENT_CONDITIONS_URL.format(location_key=location_key),
        params={"apikey": api_key, "details": "true"},
        timeout=15,
    )
    response.raise_for_status()
    conditions = response.json()[0]

    return {
        "city": settings.pilot_city,
        "local_time": conditions["LocalObservationDateTime"],
        "timezone": "Asia/Kolkata",
        "utc_offset_seconds": 19800,
        "temperature_c": conditions["Temperature"]["Metric"]["Value"],
        "feels_like_c": conditions["RealFeelTemperature"]["Metric"]["Value"],
        "humidity_pct": conditions["RelativeHumidity"],
        "pressure_hpa": conditions["Pressure"]["Metric"]["Value"],
        "wind_speed_kmh": conditions["Wind"]["Speed"]["Metric"]["Value"],
        "is_day": conditions["IsDayTime"],
        "weather_code": None,
        "weather_description": conditions["WeatherText"],
        "climate_zone": CLIMATE_ZONE,
        "source": "AccuWeather (fallback)",
    }


def get_last_source() -> str | None:
    """Which provider actually served the most recently cached weather reading, if any —
    used by the admin data-sources card to show whether the AccuWeather failsafe has
    kicked in, without triggering a new fetch just to check."""
    data = _cache["data"]
    return data["source"] if data else None


def get_current_weather() -> dict:
    now = time.time()
    if _cache["data"] is not None and (now - _cache["fetched_at"]) < _CACHE_TTL_SECONDS:
        return _cache["data"]

    try:
        data = _fetch_from_open_meteo()
    except httpx.HTTPError as primary_exc:
        try:
            data = _fetch_from_accuweather()
        except (httpx.HTTPError, RuntimeError, KeyError, IndexError) as fallback_exc:
            raise RuntimeError(
                f"Open-Meteo request failed ({primary_exc}), and the AccuWeather "
                f"failsafe also failed ({fallback_exc})."
            ) from fallback_exc

    _cache["data"] = data
    _cache["fetched_at"] = now
    return data
