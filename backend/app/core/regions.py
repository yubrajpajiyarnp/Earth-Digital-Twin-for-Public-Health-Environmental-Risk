"""The two monitored Nepal regions. Fixed geographic facts shared by ingestion, models and
routes — nothing here is fetched or computed."""

from app.core.config import settings

TIMEZONE = "Asia/Kathmandu"

# GloFAS (Open-Meteo Flood API) is a ~5 km grid, so each river is queried at a point on
# its own channel inside the valley; the three resolve to three distinct grid cells. The
# Bishnumati and Dhobi Khola are small streams, so their cells approximate those
# sub-basins rather than gauge them — see CLAUDE.md Part 2.
KTM_RIVERS = [
    {"id": "bagmati", "name": "Bagmati", "lat": 27.6936, "lon": 85.3197},
    {"id": "bishnumati", "name": "Bishnumati", "lat": 27.7330, "lon": 85.2990},
    {"id": "dhobi_khola", "name": "Dhobi Khola", "lat": 27.7100, "lon": 85.3400},
]

REGIONS = {
    "kathmandu_flood": {
        "id": "kathmandu_flood",
        "label": "Kathmandu Valley",
        "hazard": "flood",
        "lat": 27.7172,
        "lon": 85.3240,
        # Terrain sampled for the slope multiplier: the valley floor.
        "bbox": (27.66, 85.27, 27.76, 85.38),
        # BIPAD incidents within this radius count as this region's past disasters.
        "incident_radius_km": 15,
        "bipad_hazard_id": 11,  # Flood
        "key_name": "weather_api_key",
        "climate_zone": 'Subtropical highland climate (Koppen "Cwb")',
    },
    "mugling_landslide": {
        "id": "mugling_landslide",
        "label": "Mugling–Narayangadh corridor",
        "hazard": "landslide",
        "lat": 27.8000,
        "lon": 84.5400,
        # Trishuli gorge section of the highway between Mugling and Narayangadh.
        "bbox": (27.70, 84.42, 27.86, 84.57),
        "incident_radius_km": 35,
        "bipad_hazard_id": 17,  # Landslide
        "key_name": "landslide_api_key",
        "climate_zone": 'Humid subtropical climate (Koppen "Cwa")',
    },
}

_ALIASES = {"nepal_landslide": "mugling_landslide"}


def resolve_region(region_id: str | None) -> dict:
    """Region dict for an id (or the configured default). Raises ValueError for unknown
    ids so routes can map it to a 400."""
    key = _ALIASES.get(region_id or settings.pilot_region, region_id or settings.pilot_region)
    if key not in REGIONS:
        raise ValueError(f"Unknown region {region_id!r}. Choose from: {', '.join(REGIONS)}")
    return REGIONS[key]
