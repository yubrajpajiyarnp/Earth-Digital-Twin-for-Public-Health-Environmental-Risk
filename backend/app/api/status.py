"""Reports where each piece of data on the dashboard actually comes from, for the admin
panel's "Data sources" card. This is read-only introspection — it doesn't change how any
pipeline fetches data, it just surfaces what's already true elsewhere in the codebase
(which APIs, whether a key is configured, whether the local LLM is reachable right now)
in one place instead of requiring a source-code read to find out.
"""

import httpx

from app.core.config import settings
from app.db.crud import get_setting
from app.ingestion import weather as current_weather
from app.models.simulation.disaster_ml import model_status


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


def _key_detail(key_name: str) -> tuple[str, str]:
    key = get_setting(key_name) or getattr(settings, key_name)
    if key:
        return "configured", f"{key_name.upper()} is set — requests use the customer-*.open-meteo.com host."
    return "live (free tier)", f"{key_name.upper()} not set — using Open-Meteo's free non-commercial host."


def get_data_source_status() -> list[dict]:
    accuweather_key = get_setting("accuweather_api_key") or settings.accuweather_api_key
    ollama_ok, ollama_detail = _check_ollama()
    weather_last_source = current_weather.get_last_source()
    weather_status, weather_detail = _key_detail("weather_api_key")
    flood_status, flood_detail = _key_detail("flood_api_key")
    landslide_status, landslide_detail = _key_detail("landslide_api_key")
    model = model_status()

    return [
        {
            "indicator": "Kathmandu weather (forecast + ERA5 archive)",
            "provider": "Open-Meteo — ECMWF IFS 0.25° / ERA5",
            "status": weather_status,
            "detail": weather_detail,
        },
        {
            "indicator": "Kathmandu river discharge (Bagmati, Bishnumati, Dhobi Khola)",
            "provider": "Open-Meteo Flood API — GloFAS",
            "status": flood_status,
            "detail": flood_detail,
        },
        {
            "indicator": "Mugling corridor soil moisture, rain, pressure & terrain slope",
            "provider": "Open-Meteo — ECMWF IFS / ERA5 / Copernicus 90 m DEM",
            "status": landslide_status,
            "detail": landslide_detail,
        },
        {
            "indicator": "Past flood & landslide incidents (training labels)",
            "provider": "NDRRMA BIPAD Portal",
            "status": "live",
            "detail": "Public API, no key required. Reporting density rises after ~2016.",
        },
        {
            "indicator": "Current conditions",
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
            "indicator": "Local ML model (scikit-learn, joblib)",
            "provider": "Trained on this machine",
            "status": model["status"],
            "detail": (
                f"Trained {model['trained_at']} on {model['training_period']['start']} → {model['training_period']['end']}."
                if model["bundle_available"]
                else (model["error"] or "No model on disk yet — training in the background.")
            ),
        },
        {
            "indicator": "AI-written explanations",
            "provider": f"Local Ollama ({settings.ollama_model})",
            "status": "live" if ollama_ok else "unreachable",
            "detail": ollama_detail,
        },
    ]
