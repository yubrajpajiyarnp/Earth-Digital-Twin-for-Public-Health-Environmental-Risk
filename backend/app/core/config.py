from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    pilot_city: str = "Vellore"
    pilot_lat: float = 12.9165
    pilot_lon: float = 79.1325

    gee_project_id: str = "course-506318"

    data_gov_in_api_key: str | None = None
    openaq_api_key: str | None = None
    imd_api_key: str | None = None
    copernicus_client_id: str | None = None
    copernicus_client_secret: str | None = None

    # PurePriceIO (purepriceio.com) — Bearer token + separate X-Client-ID header
    fuel_price_api_key: str | None = None
    fuel_price_client_id: str | None = None
    # Carbonmark sandbox — Bearer token for https://v19.api.carbonmark.com
    carbon_price_api_key: str | None = None


settings = Settings()
