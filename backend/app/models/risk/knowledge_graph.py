"""Knowledge graph of hydro-geological driver -> hazard/health outcome relationships for
the Nepal regions. `data_connected=True` marks edges whose source has a live feed behind it
(river_discharge via GloFAS, rainfall_extreme and soil_saturation via Open-Meteo,
slope_failure via the landslide model); standing_water remains a placeholder.

DB-backed (knowledge_graph_edges table): `_SEED_EDGES` only seeds the table on startup,
after which the table is the source of truth and admin edits take effect immediately."""

import networkx as nx

from app.db.database import SessionLocal
from app.db.tables import KnowledgeGraphEdge

_SEED_EDGES = [
    dict(
        source="rainfall_extreme",
        target="river_discharge",
        relation="increases_risk",
        mechanism=(
            "Intense and prolonged monsoon rain over the Kathmandu Valley's small, steep, heavily "
            "urbanised catchments converts quickly to runoff, raising river discharge within hours."
        ),
        citation="NDRRMA BIPAD Portal incident records (bipadportal.gov.np); GloFAS river discharge reanalysis.",
        data_connected=True,
    ),
    dict(
        source="river_discharge",
        target="flood_inundation",
        relation="increases_risk",
        mechanism=(
            "Discharge beyond channel capacity overtops the Bagmati, Bishnumati and Dhobi Khola "
            "banks, inundating riverside settlements built on the floodplain."
        ),
        citation="NDRRMA BIPAD Portal incident records (bipadportal.gov.np).",
        data_connected=True,
    ),
    dict(
        source="river_discharge",
        target="waterborne_disease",
        relation="increases_risk",
        mechanism=(
            "Flooding contaminates drinking-water sources and sewer lines, increasing waterborne "
            "disease transmission."
        ),
        citation="WHO water sanitation and health guidance.",
        data_connected=True,
    ),
    dict(
        source="rainfall_extreme",
        target="soil_saturation",
        relation="increases_risk",
        mechanism=(
            "Sustained rainfall infiltrates and raises pore-water pressure in the deep soil layer "
            "of hillslopes, reducing effective stress."
        ),
        citation="Iverson (2000), Landslide triggering by rain infiltration, Water Resources Research 36(7).",
        data_connected=True,
    ),
    dict(
        source="soil_saturation",
        target="slope_failure",
        relation="increases_risk",
        mechanism=(
            "Saturated soil on steep slopes loses shear strength; combined with an intense "
            "cloudburst it can exceed the slope's resisting force and fail."
        ),
        citation=(
            "Dahal & Hasegawa (2008), Representative rainfall thresholds for landslides in the "
            "Nepal Himalaya, Geomorphology 100."
        ),
        data_connected=True,
    ),
    dict(
        source="slope_failure",
        target="road_blockage",
        relation="increases_risk",
        mechanism=(
            "Debris from failed slopes buries the Mugling–Narayangadh highway, Nepal's main link "
            "between Kathmandu and the Terai, cutting off traffic and supply routes."
        ),
        citation="NDRRMA BIPAD Portal incident records (bipadportal.gov.np).",
        data_connected=True,
    ),
    dict(
        source="slope_failure",
        target="injury_and_death",
        relation="increases_risk",
        mechanism=(
            "Landslides strike vehicles and roadside settlements with little warning; they are "
            "among Nepal's deadliest recurring hazards."
        ),
        citation="Petley et al. (2007), Trends in landslide occurrence in Nepal, Natural Hazards 43.",
        data_connected=True,
    ),
    dict(
        source="standing_water",
        target="dengue",
        relation="increases_risk",
        mechanism="Standing water left after floods is the primary breeding habitat for Aedes mosquitoes, the dengue vector.",
        citation="WHO Dengue guidelines; Nepal EDCD dengue situation reports.",
        data_connected=False,
    ),
]

# Edges seeded by the retired Vellore air-quality/vegetation/wildlife modules — removed on
# startup so the graph only describes indicators this app still measures.
_LEGACY_SOURCES = {"no2_column_density", "deforestation", "wildlife_activity", "heat"}


def seed_graph_if_empty() -> None:
    """Drop legacy edges, then insert any seed edge whose (source, target) pair is missing.
    Admin-edited text on an existing pair is left untouched."""
    with SessionLocal() as db:
        db.query(KnowledgeGraphEdge).filter(KnowledgeGraphEdge.source.in_(_LEGACY_SOURCES)).delete(synchronize_session=False)
        existing = {(r.source, r.target) for r in db.query(KnowledgeGraphEdge).all()}
        for edge in _SEED_EDGES:
            if (edge["source"], edge["target"]) not in existing:
                db.add(KnowledgeGraphEdge(**edge))
        db.commit()


def build_health_risk_graph() -> nx.DiGraph:
    g = nx.DiGraph()
    with SessionLocal() as db:
        rows = db.query(KnowledgeGraphEdge).all()
    for r in rows:
        g.add_edge(
            r.source,
            r.target,
            id=r.id,
            relation=r.relation,
            mechanism=r.mechanism,
            citation=r.citation,
            data_connected=r.data_connected,
        )
    return g


def linked_outcomes(*sources: str) -> list[dict]:
    """Outcomes downstream of the given driver nodes, for attaching to predictions."""
    graph = build_health_risk_graph()
    return [
        {"source": s, "outcome": t, "mechanism": d["mechanism"], "citation": d["citation"]}
        for s in sources
        if s in graph
        for _, t, d in graph.out_edges(s, data=True)
    ]
