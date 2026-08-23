import networkx as nx

"""Knowledge graph of environmental-indicator -> health/environmental-outcome
relationships. `data_connected=True` marks edges whose source indicator has a real
ingestion pipeline behind it (NO2 via Sentinel-5P, deforestation via Sentinel-2 NDVI,
rainfall_extreme via CHIRPS, wildlife_activity via GBIF); standing_water and heat remain
schema placeholders for indicators not wired up yet."""


def build_health_risk_graph() -> nx.DiGraph:
    g = nx.DiGraph()

    g.add_edge(
        "no2_column_density",
        "asthma",
        relation="increases_risk",
        mechanism=(
            "Elevated NO2/particulate pollution irritates airways and is an established "
            "trigger for asthma exacerbation."
        ),
        citation="WHO Global Air Quality Guidelines (2021); EPA ISA for Oxides of Nitrogen.",
        data_connected=True,
    )
    g.add_edge(
        "no2_column_density",
        "respiratory_disease",
        relation="increases_risk",
        mechanism=(
            "Chronic exposure to NOx and co-emitted pollutants is linked to increased "
            "respiratory disease incidence and hospital admissions."
        ),
        citation="WHO Global Air Quality Guidelines (2021).",
        data_connected=True,
    )
    g.add_edge(
        "standing_water",
        "dengue",
        relation="increases_risk",
        mechanism="Standing water is the primary breeding habitat for Aedes mosquitoes, the dengue vector.",
        citation="WHO Dengue guidelines; ICMR-NCVBDC.",
        data_connected=False,
    )
    g.add_edge(
        "heat",
        "heatstroke",
        relation="increases_risk",
        mechanism=(
            "Elevated ambient temperature and heat index directly increase heatstroke "
            "incidence, especially during heatwaves."
        ),
        citation="NCDC (India) heat-related illness guidance.",
        data_connected=False,
    )
    g.add_edge(
        "deforestation",
        "temperature_rise",
        relation="increases_risk",
        mechanism=(
            "Loss of vegetation cover reduces evapotranspiration and shade, raising local "
            "surface and air temperature (urban heat island effect)."
        ),
        citation="IPCC AR6 WG2.",
        data_connected=True,
    )
    g.add_edge(
        "rainfall_extreme",
        "waterborne_disease",
        relation="increases_risk",
        mechanism=(
            "Heavy rainfall and flooding contaminate drinking water sources, increasing "
            "waterborne disease transmission."
        ),
        citation="WHO water sanitation and health guidance.",
        data_connected=True,
    )
    g.add_edge(
        "wildlife_activity",
        "fauna_disruption",
        relation="decreases_risk",
        mechanism=(
            "A drop in recorded local wildlife activity/species richness can indicate "
            "habitat disruption from environmental stressors such as flooding, "
            "deforestation, and pollution."
        ),
        citation="IUCN habitat disruption guidance; GBIF citizen-science occurrence data.",
        data_connected=True,
    )
    return g
