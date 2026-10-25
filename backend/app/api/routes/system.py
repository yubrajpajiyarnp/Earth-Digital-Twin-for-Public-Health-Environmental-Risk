from fastapi import APIRouter

from app.core.regions import REGIONS, resolve_region
from app.models.simulation.disaster_ml import model_status

router = APIRouter(tags=["system"])


@router.get("/health")
def health():
    return {
        "status": "ok",
        "pilot_region": resolve_region(None)["id"],
        "regions": [{"id": r["id"], "label": r["label"], "hazard": r["hazard"]} for r in REGIONS.values()],
    }


@router.get("/models/status")
def models_status():
    return model_status()
