import time

import httpx

from app.core.config import settings

_URL = "https://purepriceio.com/api/v1/fuel/city/"

_cache: dict = {"price": None, "fetched_at": 0.0}
_CACHE_TTL_SECONDS = 3600  # retail fuel prices in India change at most once/day


def get_petrol_price_inr_per_litre(city: str = "Vellore", state: str = "TN") -> float:
    """Current petrol price (INR/litre) for `city`, via PurePriceIO's fuel price API.
    Cached for an hour.

    VERIFIED 2026-08-23 against a live key: `GET {_URL}?city=..&state=..` (note the
    trailing slash on the path — omitting it 301-redirects), auth needs BOTH an
    `Authorization: Bearer <key>` header AND a separate `X-Client-ID: <id>` header (a 403
    with a clear "Client ID not provided" message confirmed this before the client ID was
    available — see CLAUDE.md for status). Confirmed response shape from their docs:
    `{"city": ..., "state_code": ..., "rates": [{"fuel": "Petrol", "price": ...}, ...]}`.
    """
    now = time.time()
    if _cache["price"] is not None and now - _cache["fetched_at"] < _CACHE_TTL_SECONDS:
        return _cache["price"]

    if not settings.fuel_price_api_key:
        raise RuntimeError(
            "FUEL_PRICE_API_KEY not set. Get a key from your PurePriceIO dashboard and "
            "add it to backend/.env."
        )
    if not settings.fuel_price_client_id:
        raise RuntimeError(
            "FUEL_PRICE_CLIENT_ID not set. PurePriceIO requires a separate Client ID "
            "alongside the API key — find it on the same dashboard page and add it to "
            "backend/.env as FUEL_PRICE_CLIENT_ID."
        )

    try:
        resp = httpx.get(
            _URL,
            params={"city": city, "state": state},
            headers={
                "Authorization": f"Bearer {settings.fuel_price_api_key}",
                "X-Client-ID": settings.fuel_price_client_id,
            },
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
    except httpx.HTTPError as exc:
        raise RuntimeError(f"Fuel price API request failed: {exc}") from exc

    price = _extract_petrol_price(data)
    if price is None:
        raise RuntimeError(f"Could not find a Petrol rate in the API response: {data!r}")

    _cache["price"] = price
    _cache["fetched_at"] = now
    return price


def _extract_petrol_price(data) -> float | None:
    if not isinstance(data, dict):
        return None
    for rate in data.get("rates", []):
        if isinstance(rate, dict) and rate.get("fuel") == "Petrol":
            try:
                return float(rate["price"])
            except (TypeError, ValueError, KeyError):
                return None
    return None
