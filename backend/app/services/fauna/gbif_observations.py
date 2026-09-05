import time
from datetime import date, timedelta

import httpx

from app.core.config import settings
from app.db.crud import save_fauna_windows

_URL = "https://api.gbif.org/v1/occurrence/search"

# fetch_monthly_occurrence_counts makes _NUM_RETRIES+1 * num_months sequential requests in
# the worst case, so a single transient GBIF blip (rate-limit, brief timeout) used to fail
# the ENTIRE series — which is disproportionate for a wildlife-observation *count* that's
# already the noisiest signal in the app. Retry each individual window a couple times with
# a short backoff before giving up on it.
_NUM_RETRIES = 2
_RETRY_BACKOFF_SECONDS = 1.5


def _get_occurrence_count(start: date, end: date, radius_deg: float) -> int:
    lat_range = f"{settings.pilot_lat - radius_deg},{settings.pilot_lat + radius_deg}"
    lon_range = f"{settings.pilot_lon - radius_deg},{settings.pilot_lon + radius_deg}"
    last_error = None
    for attempt in range(_NUM_RETRIES + 1):
        try:
            resp = httpx.get(
                _URL,
                params={
                    "decimalLatitude": lat_range,
                    "decimalLongitude": lon_range,
                    "eventDate": f"{start.isoformat()},{end.isoformat()}",
                    "limit": 0,
                },
                timeout=15,
            )
            resp.raise_for_status()
            return resp.json()["count"]
        except httpx.HTTPError as exc:
            last_error = exc
            if attempt < _NUM_RETRIES:
                time.sleep(_RETRY_BACKOFF_SECONDS * (attempt + 1))
    raise RuntimeError(
        f"GBIF occurrence API request failed after {_NUM_RETRIES + 1} attempts: {last_error}"
    ) from last_error


def fetch_monthly_occurrence_counts(num_months: int = 13, chunk_days: int = 30, radius_deg: float = 0.45) -> list[dict]:
    """Wildlife-observation-activity series near the pilot city: total GBIF species
    occurrence records reported per trailing `chunk_days`-day window, for `num_months`
    consecutive windows (most recent last). No API key required — GBIF's occurrence
    search is fully open.

    This measures RECORDED OBSERVATIONS (citizen-science platforms like iNaturalist feed
    most of GBIF's real-time data), not a validated wildlife population survey — reporting
    volume is confounded by how many people were out looking, not just what's actually
    there. Treat it as a coarse, illustrative activity signal — see CLAUDE.md.
    """
    today = date.today()
    windows = []
    for i in range(num_months):
        end = today - timedelta(days=i * chunk_days)
        start = end - timedelta(days=chunk_days)
        windows.append((start, end))
    windows.reverse()  # oldest first

    results = [
        {
            "start": start.isoformat(),
            "end": end.isoformat(),
            "count": _get_occurrence_count(start, end, radius_deg),
        }
        for start, end in windows
    ]
    save_fauna_windows(settings.pilot_city, results)
    return results
