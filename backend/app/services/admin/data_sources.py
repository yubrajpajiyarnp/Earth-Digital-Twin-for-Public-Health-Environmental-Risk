"""Reports where each piece of data on the dashboard actually comes from, for the admin
panel's "Data sources" card. This is read-only introspection — it doesn't change how any
pipeline fetches data, it just surfaces what's already true elsewhere in the codebase
(which APIs, whether a key is configured, whether the local LLM is reachable right now)
in one place instead of requiring a source-code read to find out.
"""

import httpx

from app.core.config import settings
from app.db.crud import get_setting
from app.services.weather import current_weather


def _check_ollama() -> tuple[bool, str]:
    if not settings.llm_narrative_enabled:
        return False, "Disabled in config (llm_narrative_enabled = false)."
    try:
        response = httpx.get(f"{settings.ollama_base_url}/api/tags", timeout=3)
        response.raise_for_status()
        models = [m.get("name", "") for m in response.json().get("models", [])]
    except httpx.HTTPError as exc:
        return False, f"Unreachable at {settings.ollama_base_url}: {exc}"

    have_model = any(m == settings.ollama_model or m.startswith(f"{settings.ollama_model}:") for m in models)
    if have_model:
        return True, f"Reachable at {settings.ollama_base_url}; model '{settings.ollama_model}' is pulled."
    pulled = ", ".join(models) or "none"
    return True, (
        f"Reachable at {settings.ollama_base_url}, but '{settings.ollama_model}' isn't "
        f"pulled yet (pulled models: {pulled}). Explanations will fall back to plain "
        "templates until it's pulled."
    )


def get_data_source_status() -> list[dict]:
    fuel_key = get_setting("fuel_price_api_key") or settings.fuel_price_api_key
    fuel_client = get_setting("fuel_price_client_id") or settings.fuel_price_client_id
    carbon_key = get_setting("carbon_price_api_key") or settings.carbon_price_api_key
    accuweather_key = get_setting("accuweather_api_key") or settings.accuweather_api_key
    ollama_ok, ollama_detail = _check_ollama()

    weather_last_source = current_weather.get_last_source()

    return [
        {
            "indicator": "Air quality (NO2 proxy)",
            "provider": "Google Earth Engine — Sentinel-5P",
            "status": "live",
            "detail": "COPERNICUS/S5P/OFFL/L3_NO2. No separate API key beyond Earth Engine auth.",
        },
        {
            "indicator": "Vegetation (NDVI)",
            "provider": "Google Earth Engine — Sentinel-2",
            "status": "live",
            "detail": "COPERNICUS/S2_SR_HARMONIZED, cloud-masked via the Scene Classification Layer.",
        },
        {
            "indicator": "Rainfall",
            "provider": "Google Earth Engine — CHIRPS",
            "status": "live",
            "detail": "UCSB-CHG/CHIRPS/DAILY. No separate API key beyond Earth Engine auth.",
        },
        {
            "indicator": "Wildlife observations",
            "provider": "GBIF Occurrence API",
            "status": "live",
            "detail": "Public API, no key required.",
        },
        {
            "indicator": "Weather & climate",
            "provider": "Open-Meteo (primary) · AccuWeather (failsafe)",
            "status": "live" if weather_last_source else "not yet queried",
            "detail": (
                f"Last served by {weather_last_source}."
                if weather_last_source
                else "No weather request made yet this session."
            )
            + (
                " AccuWeather failsafe key is set."
                if accuweather_key
                else " AccuWeather failsafe key not set — an Open-Meteo outage would fail outright."
            ),
        },
        {
            "indicator": "Fuel price (budget optimizer)",
            "provider": "PurePriceIO",
            "status": "configured" if (fuel_key and fuel_client) else "not configured",
            "detail": (
                "API key and Client ID are set."
                if (fuel_key and fuel_client)
                else "Needs both an API key and a Client ID — falls back to a manual entry or illustrative default."
            ),
        },
        {
            "indicator": "Carbon credit price (budget optimizer)",
            "provider": "Carbonmark (sandbox)",
            "status": "configured" if carbon_key else "not configured",
            "detail": (
                "API key is set."
                if carbon_key
                else "No API key set — the optimizer skips the carbon value estimate."
            ),
        },
        {
            "indicator": "AI-written explanations",
            "provider": f"Local Ollama ({settings.ollama_model})",
            "status": "live" if ollama_ok else "unreachable",
            "detail": ollama_detail,
        },
    ]
