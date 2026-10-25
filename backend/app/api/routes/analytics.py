"""Historical analytics, knowledge graph and the cross-region AI summary."""

from fastapi import APIRouter, HTTPException

from app.core.regions import resolve_region
from app.models.llm.dashboard_summary import build_dashboard_summary
from app.models.risk.knowledge_graph import build_health_risk_graph
from app.models.simulation.disaster_ml import disaster_collinearity

router = APIRouter(tags=["analytics"])


@router.get("/summary")
def dashboard_summary():
    try:
        return build_dashboard_summary()
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/analytics/disaster-collinearity")
def collinearity(
    region: str | None = None,
    days_back: int = 730,
    resample: str | None = None,
    start: str | None = None,
    end: str | None = None,
):
    try:
        return disaster_collinearity(
            resolve_region(region)["id"], days_back=days_back, resample=resample, start=start, end=end
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/knowledge-graph")
def knowledge_graph():
    graph = build_health_risk_graph()
    return {
        "nodes": list(graph.nodes),
        "edges": [
            {"source": source, "target": target, **data}
            for source, target, data in graph.edges(data=True)
        ],
    }
