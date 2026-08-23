import statistics
import time

import httpx

from app.core.config import settings

_BASE_URL = "https://v19.api.carbonmark.com"

_cache: dict = {"price": None, "fetched_at": 0.0}
_CACHE_TTL_SECONDS = 3600


def get_carbon_price_usd_per_ton() -> float:
    """Current voluntary carbon credit price (USD/ton CO2e): the median `purchasePrice`
    across every listing Carbonmark's /prices endpoint returns (median over mean since a
    single popular credit token can appear as many near-duplicate listings, which would
    skew a plain average). Cached for an hour.

    VERIFIED 2026-08-23 against a live Sandbox key: GET /prices with a Bearer token
    returns a JSON array of listing objects, each with a `purchasePrice` field (e.g.
    2.8). Whether Sandbox-tier data reflects true live market prices or a seeded test
    inventory is unconfirmed — see CLAUDE.md.
    """
    now = time.time()
    if _cache["price"] is not None and now - _cache["fetched_at"] < _CACHE_TTL_SECONDS:
        return _cache["price"]

    if not settings.carbon_price_api_key:
        raise RuntimeError(
            "CARBON_PRICE_API_KEY not set. Generate a free Sandbox test key at "
            "developers.carbonmark.com (Keys page) and add it to backend/.env."
        )

    try:
        resp = httpx.get(
            f"{_BASE_URL}/prices",
            headers={"Authorization": f"Bearer {settings.carbon_price_api_key}"},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
    except httpx.HTTPError as exc:
        raise RuntimeError(f"Carbon price API request failed: {exc}") from exc

    price = _extract_price(data)
    if price is None:
        raise RuntimeError(f"Could not find a price field in the API response: {data!r}")

    _cache["price"] = price
    _cache["fetched_at"] = now
    return price


def _extract_price(data) -> float | None:
    items = data.get("items", data) if isinstance(data, dict) else data
    if not isinstance(items, list) or not items:
        return None
    prices = []
    for item in items:
        if not isinstance(item, dict):
            continue
        value = item.get("purchasePrice")
        if value is None:
            continue
        try:
            prices.append(float(value))
        except (TypeError, ValueError):
            continue
    if not prices:
        return None
    return statistics.median(prices)
