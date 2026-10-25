"""Admin (gated by require_admin — see app/core/security.py for how trivial this check is
by explicit request). Manage knowledge-graph edges, API-key settings and model retraining."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.core.security import require_admin
from app.db import crud
from app.api.status import get_data_source_status
from app.models.simulation.disaster_ml import model_status, start_background_training

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/whoami")
def admin_whoami(email: str = Depends(require_admin)):
    return {"ok": True, "email": email}


@router.get("/data-sources")
def admin_data_sources(_: str = Depends(require_admin)):
    return {"sources": get_data_source_status()}


@router.post("/models/retrain")
def admin_retrain_models(_: str = Depends(require_admin)):
    start_background_training(force=True)
    return model_status()


@router.get("/settings")
def admin_list_settings(_: str = Depends(require_admin)):
    return {"settings": crud.list_settings()}


class SettingBody(BaseModel):
    key: str
    value: str


@router.post("/settings")
def admin_set_setting(body: SettingBody, _: str = Depends(require_admin)):
    crud.set_setting(body.key, body.value)
    return {"ok": True}


@router.delete("/settings/{key}")
def admin_delete_setting(key: str, _: str = Depends(require_admin)):
    if not crud.delete_setting(key):
        raise HTTPException(status_code=404, detail="Setting not found.")
    return {"ok": True}


@router.get("/knowledge-graph/edges")
def admin_list_kg_edges(_: str = Depends(require_admin)):
    return {"edges": crud.list_kg_edges()}


class KgEdgeBody(BaseModel):
    id: int | None = None
    source: str
    target: str
    relation: str
    mechanism: str
    citation: str
    data_connected: bool = False


@router.post("/knowledge-graph/edges")
def admin_upsert_kg_edge(body: KgEdgeBody, _: str = Depends(require_admin)):
    try:
        return crud.upsert_kg_edge(
            source=body.source,
            target=body.target,
            relation=body.relation,
            mechanism=body.mechanism,
            citation=body.citation,
            data_connected=body.data_connected,
            edge_id=body.id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.delete("/knowledge-graph/edges/{edge_id}")
def admin_delete_kg_edge(edge_id: int, _: str = Depends(require_admin)):
    if not crud.delete_kg_edge(edge_id):
        raise HTTPException(status_code=404, detail="Edge not found.")
    return {"ok": True}
