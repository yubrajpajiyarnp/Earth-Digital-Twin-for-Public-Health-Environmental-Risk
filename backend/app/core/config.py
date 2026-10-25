from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Default region for endpoints called without ?region= — see app/core/regions.py.
    # Accepts kathmandu_flood, mugling_landslide, or the alias nepal_landslide.
    pilot_region: str = "kathmandu_flood"

    # Three Open-Meteo keys, one per feed family (see CLAUDE.md Part 2). All optional:
    # blank means the free non-commercial endpoint; set means the customer-* endpoint.
    # An admin-settings override (same key name, lowercase) wins over these.
    weather_api_key: str | None = None
    flood_api_key: str | None = None
    landslide_api_key: str | None = None

    # Local ML bundle (scikit-learn, persisted with joblib) and how stale it may get before
    # the background trainer refreshes it on startup.
    model_path: Path = BACKEND_DIR / "data" / "models" / "nepal_disaster_model.joblib"
    model_max_age_days: int = 7

    # Local Ollama server used to turn computed numbers into natural-language explanations.
    # Never used for the numeric predictions themselves — see app/models/llm/narrative.py.
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "mistral"
    llm_narrative_enabled: bool = True

    # AccuWeather — failsafe fallback for ingestion/weather.py, only called if the primary
    # Open-Meteo request fails. Free-tier key from developer.accuweather.com.
    accuweather_api_key: str | None = None


settings = Settings()
