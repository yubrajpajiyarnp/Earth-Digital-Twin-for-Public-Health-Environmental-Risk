import networkx as nx

from app.db.database import SessionLocal
from app.db.models import KnowledgeGraphEdge

"""Knowledge graph of environmental-indicator -> health/environmental-outcome
relationships. `data_connected=True` marks edges whose source indicator has a real
ingestion pipeline behind it (NO2 via Sentinel-5P, deforestation via Sentinel-2 NDVI,
rainfall_extreme via CHIRPS, wildlife_activity via GBIF); standing_water and heat remain
schema placeholders for indicators not wired up yet.

This is now DB-backed (knowledge_graph_edges table), not hardcoded: `_SEED_EDGES` below
is only the one-time seed used by seed_graph_if_empty() on first startup. After that, the
table itself is the source of truth — admin edits via the API take effect immediately."""

_SEED_EDGES = [
    dict(
        source="no2_column_density",
        target="asthma",
        relation="increases_risk",
        mechanism=(
            "Elevated NO2/particulate pollution irritates airways and is an established "
            "trigger for asthma exacerbation."
        ),
        citation="WHO Global Air Quality Guidelines (2021); EPA ISA for Oxides of Nitrogen.",
        data_connected=True,
    ),
    dict(
        source="no2_column_density",
        target="respiratory_disease",
        relation="increases_risk",
        mechanism=(
            "Chronic exposure to NOx and co-emitted pollutants is linked to increased "
            "respiratory disease incidence and hospital admissions."
        ),
        citation="WHO Global Air Quality Guidelines (2021).",
        data_connected=True,
    ),
    dict(
        source="standing_water",
        target="dengue",
        relation="increases_risk",
        mechanism="Standing water is the primary breeding habitat for Aedes mosquitoes, the dengue vector.",
        citation="WHO Dengue guidelines; ICMR-NCVBDC.",
        data_connected=False,
    ),
    dict(
        source="heat",
        target="heatstroke",
        relation="increases_risk",
        mechanism=(
            "Elevated ambient temperature and heat index directly increase heatstroke "
            "incidence, especially during heatwaves."
        ),
        citation="NCDC (India) heat-related illness guidance.",
        data_connected=False,
    ),
    dict(
        source="deforestation",
        target="temperature_rise",
        relation="increases_risk",
        mechanism=(
            "Loss of vegetation cover reduces evapotranspiration and shade, raising local "
            "surface and air temperature (urban heat island effect)."
        ),
        citation="IPCC AR6 WG2.",
        data_connected=True,
    ),
    dict(
        source="rainfall_extreme",
        target="waterborne_disease",
        relation="increases_risk",
        mechanism=(
            "Heavy rainfall and flooding contaminate drinking water sources, increasing "
            "waterborne disease transmission."
        ),
        citation="WHO water sanitation and health guidance.",
        data_connected=True,
    ),
    dict(
        source="wildlife_activity",
        target="fauna_disruption",
        relation="decreases_risk",
        mechanism=(
            "A drop in recorded local wildlife activity/species richness can indicate "
            "habitat disruption from environmental stressors such as flooding, "
            "deforestation, and pollution."
        ),
        citation="IUCN habitat disruption guidance; GBIF citizen-science occurrence data.",
        data_connected=True,
    ),
]


def seed_graph_if_empty() -> None:
    with SessionLocal() as db:
        if db.query(KnowledgeGraphEdge).first() is not None:
            return
        for edge in _SEED_EDGES:
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
