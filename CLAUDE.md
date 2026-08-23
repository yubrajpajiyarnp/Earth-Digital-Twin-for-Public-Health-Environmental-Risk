# Earth Digital Twin for Public Health & Environmental Risk

> Status: **All six components from the abstract are working end-to-end**, including the RL
> budget-optimizer stretch goal, PLUS a flood/rainfall pipeline and a fauna/wildlife pipeline added
> beyond the original abstract scope (per user request — the project is also about how natural
> disasters affect human life, vegetation, and fauna). Backend (FastAPI) and frontend (React/Vite)
> dashboard both work; all API routes below return real data for Vellore. This file documents the
> project as defined by the abstract (`Project_Abstract_Digital_Twin_Health-2.pdf`) plus implementation
> decisions and data-source verification done since. Keep this updated as real conventions emerge.

## Repo layout

```
backend/            FastAPI app
  app/main.py                          app entrypoint, CORS, router mount
  app/api/routes.py                    API routes: /api/health, /api/aqi-proxy, /api/forecast/aqi, /api/risk/aqi, /api/explain/aqi, /api/ndvi, /api/risk/vegetation, /api/rainfall, /api/risk/flood, /api/fauna, /api/risk/fauna, /api/simulate/traffic-reduction, /api/simulate/afforestation, /api/simulate/disaster (disaster_type=flood|fire|earthquake), /api/optimize/budget, /api/prices/fuel, /api/prices/carbon, /api/knowledge-graph
  app/core/config.py                   pydantic-settings config (pilot city/coords, GEE project, API keys from .env)
  app/services/cv/earth_engine_client.py   lazy ee.Initialize() wrapper, raises RuntimeError with a fix-it message if unauthenticated
  app/services/cv/aqi_proxy.py         Sentinel-5P NO2 proxy (single current-window mean) — see "Known gaps & risks" for the catalog-lag quirk this works around
  app/services/cv/no2_timeseries.py    daily-aggregated NO2 history for the pilot point, gap-interpolated to a continuous DatetimeIndex — feeds the forecaster and the XAI feature builder
  app/services/cv/ndvi_timeseries.py   cloud-masked (SCL-based) mean NDVI per usable Sentinel-2 scene near the pilot point — NOT reindexed to daily (real cloud gaps, e.g. ~6 weeks during monsoon, are left as gaps rather than interpolated)
  app/services/cv/rainfall_timeseries.py   daily rainfall (mm) near the pilot point from CHIRPS (UCSB-CHG/CHIRPS/DAILY) via the same GEE auth as NO2/NDVI — no new credential needed. One image per calendar day globally, so unlike NO2/NDVI no per-scene grouping is needed
  app/services/forecasting/aqi_forecast.py   Holt-Winters (statsmodels ExponentialSmoothing) forecast over the no2_timeseries history; weekly seasonality auto-enabled once ≥21 days of history exist
  app/services/fauna/gbif_observations.py   monthly GBIF species-occurrence counts (all taxa) within ~50km of the pilot point — fully keyless, open API. See "Known gaps & risks" for the observer-effort confound and publishing-lag caveat
  app/services/knowledge_graph/graph.py         networkx DiGraph of indicator→health/environmental-outcome edges. `data_connected=True` edges: no2_column_density→{asthma,respiratory_disease}, deforestation→temperature_rise, rainfall_extreme→waterborne_disease, wildlife_activity→fauna_disruption. Still schema-only placeholders: standing_water→dengue, heat→heatstroke
  app/services/knowledge_graph/anomaly.py       shared `classify_anomaly(z, invert=False)` used by every risk-assessment module, the simulation engines, and the RL environment, so "elevated/typical/reduced" means the same thing everywhere
  app/services/knowledge_graph/risk_assessment.py   turns the NO2 forecast into a risk statement per connected outcome — see "Known gaps & risks" for why this is baseline-relative (z-score/% change vs Vellore's own history), not an absolute AQI threshold
  app/services/knowledge_graph/vegetation_risk_assessment.py   same baseline-relative pattern as risk_assessment.py but for NDVI → deforestation → temperature_rise; anomaly direction is inverted (NDVI below baseline = elevated risk, not above)
  app/services/knowledge_graph/flood_risk_assessment.py   compares the recent 7-day rainfall TOTAL (not daily mean — flood risk is about short-window accumulation) against the distribution of same-length rolling totals, for rainfall_extreme→waterborne_disease
  app/services/knowledge_graph/fauna_risk_assessment.py   compares the most recent month's GBIF occurrence count against the distribution of prior months, for wildlife_activity→fauna_disruption; inverted like NDVI (fewer observations = elevated risk)
  app/services/xai/features.py         lag/rolling-average/day-of-week feature engineering over the daily NO2 series, shared by the explainer
  app/services/xai/explain_forecast.py   trains a small RandomForestRegressor on those features and explains its latest prediction with SHAP (TreeExplainer) — see "Known gaps & risks" for why this is a separate surrogate model, not a decomposition of the Holt-Winters forecast itself
  app/services/simulation/engine.py    "what if" traffic-reduction and afforestation scenarios — perturbs the live NO2/NDVI baselines using stated literature-informed effect-size assumptions, then reclassifies risk with the same anomaly.py logic used by the live pipeline. Exposes pure `project_*` functions (no I/O) reused by the RL environment. See "Known gaps & risks" for why the effect sizes are illustrative, not calibrated.
  app/services/simulation/disaster_engine.py   `simulate_disaster(disaster_type, severity_pct)` dispatches to per-type sims: flood (real rainfall baseline → waterborne_disease, + illustrative NDVI/fauna damage), fire (illustrative NO2-proxy "smoke" spike + illustrative NDVI/fauna damage — no live "current fire" indicator exists, severity is a pure hypothetical), earthquake (no environmental outcomes at all — deliberately, since earthquakes have no defensible link to this app's weather/vegetation indicators; only the reconstruction estimate). `estimate_reconstruction_fund()` is shared across all three: an order-of-magnitude ₹ estimate broken down by `INFRASTRUCTURE_CATEGORIES` (roads/water/electricity/healthcare/housing/schools/other) and sorted by a stated public-usage priority ranking. Flood/fire are slow by construction (fetch 2-3 live sources); earthquake is fast (pure math). See "Known gaps & risks" for the illustrative-coefficient and cost-model basis.
  app/services/rl/env.py               `BudgetAllocationEnv`, a Gymnasium env: given a fixed budget, choose the traffic-reduction/afforestation split that minimizes combined NO2+NDVI risk. Single-step (bandit-style), not a multi-step MDP — see "Known gaps & risks" for why, and for the budget-efficiency reward term that keeps it from over-recommending spend once risk is already at floor
  app/services/rl/optimizer.py         trains a fresh PPO (stable-baselines3) policy per request over BudgetAllocationEnv and returns its recommended allocation — explicitly the abstract's stretch/research-level component, not part of the core prototype. Pulls live fuel + carbon prices (below) to price the allocation, degrading gracefully to illustrative defaults if either key is missing
  app/services/pricing/fuel_price.py   live petrol price (INR/L, PurePriceIO) — scales the RL traffic-reduction cost coefficient. Cached 1h. Endpoint/response shape VERIFIED live; needs both FUEL_PRICE_API_KEY and FUEL_PRICE_CLIENT_ID (see "Known gaps & risks"). `/api/optimize/budget?fuel_price_inr=...` lets a caller supply today's price manually instead, which takes priority over this API and requires no key at all — the frontend's Optimizer panel exposes this as an input field
  app/services/pricing/carbon_price.py   live carbon credit price (USD/ton, Carbonmark) — monetizes the CO2 avoided by the RL-recommended allocation as a separate benefit estimate, not blended into the cost math. Cached 1h. VERIFIED working against a live Sandbox key (see "Known gaps & risks")
  requirements.txt
  .env.example        copy to .env and fill in API keys as they're obtained
frontend/            React + Vite dashboard. AQI/vegetation get their own always-visible sections; rainfall,
                      wildlife, and simulation are consolidated into ONE tabbed section (TabBar.jsx) that
                      lazily mounts only the active panel — each of those three panels makes slow live-data
                      calls (GBIF ~15-20s, NDVI 30-90s+), so tabbing avoids paying for all three on every
                      page load. RL optimizer (incl. live price badges) and the knowledge graph diagram
                      round it out, all wired to the backend endpoints below
```

Run backend: `cd backend && .venv/bin/uvicorn app.main:app --reload` → `/api/health`, `/api/aqi-proxy`,
`/api/forecast/aqi?horizon_days=7` (or `30`), `/api/risk/aqi?horizon_days=7`, `/api/explain/aqi`,
`/api/ndvi`, `/api/risk/vegetation`, `/api/rainfall`, `/api/risk/flood`, `/api/fauna`, `/api/risk/fauna`,
`/api/simulate/traffic-reduction?reduction_pct=30`, `/api/simulate/afforestation?area_pct=20`,
`/api/simulate/disaster?disaster_type=flood&severity_pct=50` (or `fire`/`earthquake`),
`/api/optimize/budget?budget=100`, `/api/prices/fuel`,
`/api/prices/carbon`, `/api/knowledge-graph`
Run frontend: `cd frontend && npm run dev` → `http://localhost:5173`

No new API keys were needed for either addition: rainfall reuses the existing Earth Engine auth
(CHIRPS is just another GEE dataset), and GBIF's occurrence-search API is fully open/keyless.

**Note on request latency:** NDVI-backed endpoints map over ~150-200 raw Sentinel-2 scenes server-side
(30-90s+, depending on Earth Engine load) and `/api/optimize/budget` trains a fresh PPO policy per
request (~10-20s at the default 4000 training steps) — these are the slow paths; give curl/clients a
generous timeout (120s+) rather than assuming a hang.

**One-time machine setup for Earth Engine:** `cd backend && .venv/bin/earthengine authenticate` (opens a
browser, caches credentials locally). Without this, `/api/aqi-proxy` returns a 503 with instructions.

## Project summary

AI-powered digital twin that couples real-time and forecasted environmental data (AQI, temperature,
rainfall, flood risk, green cover, industrial emissions, traffic pollution) with a public-health risk layer
for a single pilot region. It goes beyond a normal environmental dashboard by answering four questions
for the user:

1. What health risk does this condition translate to, and for whom?
2. Why is the risk elevated right now, in plain causal terms?
3. What happens to that risk if conditions change or we intervene?
4. Given limited resources, which interventions reduce risk the most?

**Pilot region: Vellore, Tamil Nadu, India** (decided — VIT is based here, easiest for local
validation/ground-truthing). The abstract also names Chennai, Kathmandu, and Janakpur as alternates if
Vellore's data coverage proves too sparse — see [Known gaps & risks](#known-gaps--risks).

**Core capabilities (must-have):** visualize current conditions → forecast near-term risk → explain the
causal drivers → simulate "what-if" interventions before they're implemented.

**Stretch capability:** a reinforcement-learning module that recommends how to allocate a fixed budget
across interventions (afforestation, wetland restoration, emissions control, drainage improvement) to
minimize aggregate health + environmental risk. Ship this only if time permits after the core pipeline
works.

## Architecture map

Six components from the abstract, mapped to concrete tooling for the chosen stack
(**Python backend + React frontend**):

| Component | Function | Recommended tooling |
|---|---|---|
| **Computer Vision** | Detect urban expansion, vegetation loss, water-body changes, land-use shifts from Sentinel-2 | **Google Earth Engine Python API** as primary route (Sentinel-2 NDVI/land-use/water composites with far less friction than raw tile handling); `rasterio` / `torchgeo` as fallback for raw-tile work outside GEE's catalog |
| **Time-Series Forecasting** | Predict AQI, temperature, rainfall, flood probability over 7- and 30-day horizons | `statsmodels` / `Prophet` for a fast baseline; `darts` if multiple models need benchmarking; revisit deep learning (TFT/LSTM) only if the classical baseline underperforms |
| **Knowledge Graph** | Encode pollution↔asthma, standing-water↔dengue, heat↔heatstroke, deforestation↔temperature-rise relationships | `networkx` to start (lightweight, in-process); migrate to Neo4j only if graph queries or edge count outgrow it |
| **Explainable AI** | Convert risk scores into causal, human-readable explanations | SHAP or LIME over the risk model, output templated into sentences (e.g. "Flood risk rose because rainfall increased 35%...") |
| **Simulation Engine** | Model projected effect of user-defined interventions (afforestation %, traffic reduction %, wetland restoration, rainfall change) on temperature/AQI/flood risk | A parametrized layer that re-runs the forecasting + KG pipeline with perturbed inputs; no need for a separate framework — this is orchestration logic over the existing models |
| **RL Policy Module** (stretch) | Recommend budget allocation across interventions to jointly minimize flood risk, pollution, health impact | `gymnasium` custom environment + `stable-baselines3` (PPO or similar) |
| **Backend** | Serve model outputs, orchestrate pipeline | FastAPI |
| **Frontend** | Dashboard: map view, forecast charts, simulation panel | React (map component + charting library, e.g. Recharts/deck.gl for geospatial layers) |

## Required APIs & data sources

The abstract names these sources; access details below reflect how each is *actually* consumed
programmatically (not always a clean REST API — noted where relevant).

| Data | Source | Access | Notes / Vellore caveats |
|---|---|---|---|
| Real-time air quality (AQI, PM2.5, PM10, SO₂, NO₂, O₃) | CPCB | Programmatic access is via **data.gov.in**'s CPCB real-time AQI resource (free data.gov.in account → API key), JSON/XML. `airquality.cpcb.gov.in` itself is the human dashboard, not a documented API. | **VERIFIED (2026-08-22): Vellore has no active CPCB/TNPCB real-time monitoring station.** TNPCB's own station list (`tnpcb.gov.in/aqi.php`) covers only Chennai, Coimbatore, Cuddalore, Gummidipoondi, and Thoothukudi — Vellore is absent. Plan on a fallback: nearest active station (likely Chennai, ~140km away, too far to be representative) or a satellite-derived proxy (Sentinel-5P NO₂/aerosol) as the realistic path for AQI in Vellore. |
| Historical continuous air quality (2015–2019, hourly, all CPCB stations) | CPCB via Princeton DataSpace | `dataspace.princeton.edu` — bulk downloadable dataset, **not a live API**. One-time ingestion into local storage. | Given no Vellore station exists in this window either, this dataset is useful for backtesting the *forecasting methodology* on a well-covered city, not for Vellore-specific ground truth. |
| Cross-validation / global air quality | OpenAQ | `openaq.org` — public REST API v3. **VERIFIED (2026-08-22): requires an `X-API-Key` header even for basic queries** (`curl` without a key returns 401 Unauthorized) — free registration needed before station coverage near Vellore can even be checked. | Register for a key, then re-check coverage — do this before assuming OpenAQ can fill the CPCB gap. |
| Satellite imagery (land use, vegetation, water bodies) | Copernicus Sentinel-2 | `dataspace.copernicus.eu` — OAuth2-based STAC/OData/openEO APIs, free registration. | Prefer **Google Earth Engine** for the actual CV pipeline (see Architecture map) — same imagery, much less plumbing. Use raw Copernicus Data Space only if GEE's processed catalog doesn't cover a needed band/product. |
| Rainfall & weather (India) | IMD (India Meteorological Department) | **VERIFIED (2026-08-22): a real documented REST API exists** at `api.imd.gov.in` (see `api_reference.html`) — city forecast (7-day), current weather, district-wise nowcast/rainfall endpoints, pattern `api.imd.gov.in/api/v1/<endpoint>?id=<city_id>`. **Requires an API key** — `curl` without one returns `{"error":"API key missing"}`. Getting a key appears to require a formal request / IP whitelisting (no self-serve signup found), see `mausam.imd.gov.in/responsive/apis.php`. | Before building on this, submit the key request and confirm turnaround time; `data.gov.in` weather datasets are the fallback if IMD access stalls. City ID for Vellore not yet resolved (blocked on the same API key). |
| Rainfall & weather (Nepal) | DHM (Dept. of Hydrology & Meteorology, Nepal) | `dhm.gov.np` | Only relevant if the pilot later extends to Kathmandu/Janakpur. Mostly bulletins/portals; DHM's flood forecasting portal has some machine-readable feeds but coverage is limited. Not verified — out of scope while pilot = Vellore. |
| Disease–environment relationships | Published epidemiological literature | Case-by-case citation during development (PubMed, WHO, ICMR-NCVBDC for India-specific dengue surveillance as optional supplementary source) | **Not an API.** This parameterizes the knowledge graph's edges (e.g. pollution↔asthma correlation strength) — it is not ground-truth incidence data. |

## Known gaps & risks

- **No granular geolocated disease incidence data** is publicly available at station-level resolution for
  South Asian cities. The health-risk layer is therefore knowledge-driven (built from published
  environmental-health correlations), not trained directly on local case data. This is a stated modeling
  assumption from the abstract, not something to paper over.
- **IMD has a real REST API but it's gated** (API key + likely IP whitelisting, no self-serve signup found)
  — CPCB doesn't have a clean public API at all (goes through `data.gov.in`). Budget time for the IMD key
  request, and don't assume it will land quickly.
- **CONFIRMED (2026-08-22): Vellore has no CPCB/TNPCB ground station for AQI.** This is no longer a
  theoretical risk. **DECIDED (2026-08-22): pilot stays Vellore; the AQI pipeline is built on a
  satellite-derived proxy (Sentinel-5P NO₂/aerosol index via Google Earth Engine) rather than
  ground-station readings.** Trade-off accepted knowingly: this is more novel (fits the abstract's
  emphasis on original contribution) but the proxy's accuracy against real AQI is unvalidated — treat
  the first version of this pipeline as needing explicit accuracy caveats in any dashboard output, and
  revisit switching to Chennai only if the proxy turns out unworkable.
- **VERIFIED (2026-08-23): the Earth Engine catalog for `COPERNICUS/S5P/OFFL/L3_NO2` lags real time by
  10+ days near Vellore** (freshest scene available was ~11 days old when checked), well beyond S5P's
  nominal same-day processing. `aqi_proxy.py` works around this by taking the most recent N available
  scenes (sorted by `system:time_start`) instead of filtering a fixed trailing date window — a fixed
  window silently returns an empty collection once the real lag exceeds the assumed one. If you add
  other Earth Engine time-series pulls (Sentinel-2 for the CV component, etc.), use the same
  latest-N-scenes pattern rather than assuming "last N days from today" works.
- **Health-risk statements are baseline-relative, not absolute-AQI.** Sentinel-5P NO2 is a tropospheric
  **column density** (mol/m²), not the ground-level **concentration** (µg/m³) that WHO/CPCB health
  thresholds are defined against — converting between the two requires a boundary-layer-height model
  this project doesn't have. `risk_assessment.py` therefore compares the forecast against Vellore's own
  recent history (z-score / % change) rather than an absolute limit. Don't silently start treating the
  NO2 proxy value as if it were a real AQI number — the units aren't comparable.
- **The SHAP explainer is a separate model from the Holt-Winters forecaster, by necessity.** Holt-Winters
  (`aqi_forecast.py`) has no discrete input features to attribute importance to — it recurses on the
  series itself — so SHAP can't explain it directly. `explain_forecast.py` instead trains a small,
  purpose-built RandomForestRegressor on engineered lag/rolling features from the *same* NO2 series and
  explains that model's prediction. Treat `/api/explain/aqi` as answering "what's driving the recent
  trend" (a companion diagnostic), not as a literal breakdown of the number `/api/forecast/aqi` returns
  — the two models can and will disagree slightly since they're different models over the same data.
- **VERIFIED (2026-08-23): `ee.Image.remap()` renames its output band to `"remapped"` by default**,
  not the input band's name — a `.get("<original_band_name>", default)` lookup after a `reduceRegion`
  on a remapped image will silently hit the "key missing" fallback every time instead of throwing,
  which is worse than a crash because it looks like valid data. Always `.rename(...)` immediately after
  `remap()`. Also: `reduceRegion().get(key, default)` only substitutes `default` when `key` is entirely
  absent from the dictionary — a fully-masked region can come back as `{key: null}` (present, but
  `None`), which needs handling on the Python side after `getInfo()`, not assumed away by the
  server-side default.
- **Simulation-engine effect sizes are stated assumptions, not calibrated coefficients.**
  `simulation/engine.py`'s traffic→NO2 attribution (60%) and afforestation→NDVI end-member (0.75) are
  generic literature reference values because there's no local traffic-emissions inventory or
  land-cover-change ground truth for Vellore to fit them against. Each scenario response includes an
  `assumption` field stating this explicitly — don't let a future dashboard present simulation output
  with the same confidence as the live-data pipeline without carrying that caveat through to the UI.
- **The RL budget optimizer is a single-step (bandit) decision, not a multi-step MDP.** There's no data
  on how Vellore's risk actually evolves day-to-day under a sustained intervention, so `BudgetAllocationEnv`
  evaluates one allocation decision per episode rather than fabricating multi-step dynamics with nothing
  to validate them against. It also trains a fresh PPO policy from scratch on every `/api/optimize/budget`
  request (no persisted model) since the problem itself — Vellore's current NO2/NDVI baseline — changes
  over time. VERIFIED (2026-08-23): the raw reward (just `-risk_after`, clipped at 0) let PPO recommend
  spending most of the budget even when risk was already at floor with nothing to fix, because clipping
  removes the gradient once risk hits 0 — fixed with a small budget-efficiency penalty term in the reward
  (`env.py`) so the optimizer only recommends spend that actually reduces risk. If this component is
  extended, re-check that any new reward term doesn't reintroduce a similar flat-optimum blind spot.
- **Carbon price (Carbonmark) is VERIFIED WORKING (2026-08-23) against a live Sandbox key** —
  `GET /prices` with a Bearer token returns a JSON array of listings, each with a `purchasePrice` field;
  `carbon_price.py` takes the median across all listings (2.8 USD/ton when checked). Whether Sandbox-tier
  data reflects true live market prices or a seeded test inventory is still unconfirmed — treat
  `estimated_carbon_value_usd` as illustrative until that's settled, but the plumbing itself works.
- **Fuel price switched providers: RapidAPI "Fuel Price API India" → PurePriceIO.** The RapidAPI listing
  was confirmed broken upstream (POST to its real endpoint reached the actual backend and consistently
  500'd regardless of body, across 3 tries — a dead third-party service, not a request-shape problem).
  `fuel_price.py` now targets PurePriceIO instead, confirmed against a live key: `GET
  https://purepriceio.com/api/v1/fuel/city/?city=..&state=..` (note the trailing slash — omitting it
  301-redirects), response shape `{"rates": [{"fuel": "Petrol", "price": ...}, ...]}`. **Needs TWO
  credentials, not one**: `FUEL_PRICE_API_KEY` (Bearer token, format `sk-live-...`) AND
  `FUEL_PRICE_CLIENT_ID` (separate `X-Client-ID` header) — confirmed via a live 403 ("Client ID not
  provided") before the client ID was available. As of 2026-08-23 the API key is set but the client ID
  is still missing, so this stays in graceful-fallback mode (`cost_per_pct_traffic_reduction_is_live:
  false`) until `FUEL_PRICE_CLIENT_ID` is added to `backend/.env`. Both price keys are optional either
  way: `optimize_budget_allocation()` degrades to the illustrative defaults if a price fetch fails, so
  this can never take down the core RL flow.
- **The traffic→fuel-price and CO2-avoided-per-%-reduction relationships are still assumptions**, even
  though the fuel and carbon *prices* feeding them are now real: `REFERENCE_PETROL_PRICE_INR_PER_LITRE`
  (linear cost scaling) and `CO2_TONS_PER_PCT_TRAFFIC_REDUCTION` (an order-of-magnitude, not measured,
  estimate — no Vellore vehicle-count or emissions-inventory data exists) are both stated in
  `rl/optimizer.py` and surfaced in the API's `assumptions.note`. Real price in, assumed shape still
  assumed — don't let a live number upstream imply the whole pipeline is now calibrated.
- **Tree-sapling / afforestation cost has no real-time price source** — checked Agmarknet (India's
  actual live commodity-price API); it covers ~200 mandi crop commodities, not nursery stock or
  afforestation labor. `COST_PER_PCT_AFFORESTATION` stays a stated illustrative constant by design,
  not an oversight — don't wire an unrelated commodity (e.g. timber) into it and present it as live.
- **GBIF fauna data measures reporting activity, not wildlife population health — and has its own
  catalog-lag problem.** Citizen-science platforms (iNaturalist etc.) feed most of GBIF's real-time
  data, so counts are confounded by observer effort (more people out on a nice day ≠ more animals).
  VERIFIED 2026-08-23: the most recent 30-day window read 11 observations vs a ~90-count typical month
  — almost certainly GBIF's own publishing lag (the same pattern seen with every other external source
  in this project), not a real activity drop, and `fauna_risk_assessment.py`'s output said so at the
  time. Don't "fix" this the way `aqi_proxy.py` fixed the Sentinel-5P lag (latest-N-available) — GBIF's
  query is inherently a fixed-window count, not a scannable time series, so the caveat is surfaced in
  the explanation text instead. Treat `wildlife_activity`/`fauna_disruption` readings as more
  illustrative than the satellite-derived indicators.
- **Disaster simulations mix real-baseline legs with illustrative-coefficient legs, and the mix
  differs by type.** Flood's `rainfall_extreme→waterborne_disease` is driven directly by real CHIRPS
  rainfall statistics (same rigor as the other risk assessments); fire has NO real "current fire"
  indicator at all, so its severity is a pure hypothetical input and its air-quality effect is an
  illustrative NO2-proxy spike, not a real smoke measurement; earthquake has no environmental legs
  whatsoever (deliberately — forcing NO2/NDVI/rainfall/fauna into an earthquake's causal story would be
  dishonest, they have no real link to seismic events). Every vegetation/fauna damage coefficient
  (`FLOOD_NDVI_DROP_AT_100PCT_SEVERITY`, `FIRE_NDVI_DROP_AT_100PCT_SEVERITY`, etc.) is a STATED,
  NOT-CALIBRATED assumption — same honesty pattern as `TRAFFIC_NO2_ATTRIBUTION`/`FOREST_NDVI` in
  `simulation/engine.py`. Fire's coefficients were set higher than flood's on the judgment that direct
  burning is more destructive than waterlogging — that comparison itself is not measured either.
- **The reconstruction-fund estimate — including the category breakdown and priority order — is
  order-of-magnitude/illustrative only, not real government or planning data.**
  `estimate_reconstruction_fund()`'s population (~50,000), per-person cost (~₹15,000), the 7
  `INFRASTRUCTURE_CATEGORIES` cost-share percentages, and their priority ranking (roads/water/power
  ranked above schools/other on assumed daily public dependence) are all stated assumptions from this
  session, not sourced from a specific study. In particular: (1) this session did NOT look up India's
  actual current SDRF/NDRF disaster-relief rate tables (real per-household/per-hectare compensation
  norms do exist, published by the Ministry of Home Affairs, but weren't fetched and verified the way
  other data sources in this project were); (2) the same cost-share/priority breakdown is currently
  applied identically across flood/fire/earthquake — a real model would vary this by disaster type
  (e.g. earthquakes disproportionately damage housing/buildings, floods disproportionately damage
  roads/water infrastructure). If either the total figure or the breakdown needs to be defensible
  rather than illustrative, the SDRF/NDRF lookup and a type-specific cost-share model are the next
  steps — don't present the current numbers as sourced from an actual government or planning document,
  because they aren't yet.
- **Patent/IP notes** (reference only, not engineering detail): under Indian Patents Act 1970 Section 3(k),
  algorithms "per se" are not patentable — protection would need to center on the specific integrated
  pipeline (forecast → KG risk → causal explanation → simulation → RL-optimized recommendation), not
  any individual technique. VIT's Technology Transfer/IPR cell is the intended filing path if pursued later.

## Working agreement for future sessions

- Pilot city is **Vellore** unless the user says otherwise.
- Stack is **Python (FastAPI) backend + React frontend** unless the user says otherwise.
- Prefer **Google Earth Engine** over raw Sentinel-2/Copernicus Data Space handling for the CV
  component unless a specific need forces the raw route.
- AQI for Vellore comes from a **Sentinel-5P satellite proxy via GEE**, not a ground station — there
  isn't one. Don't build code that assumes a CPCB/TNPCB Vellore station exists.
- The RL budget-optimizer was explicitly a **stretch component** — it's now built (see repo layout
  above), but treat any further RL work as lower priority than gaps in the core pipeline (e.g. the
  frontend still not consuming any of this, or unconnected knowledge-graph edges).
- Every backend component built so far only requires Earth Engine auth — no other `.env` key
  (IMD/OpenAQ/data.gov.in/Copernicus) is actually wired to working code yet, despite being present in
  `.env.example` as placeholders for indicators not built (temperature, rainfall, standing water).
- All 10 API routes are verified working against real Vellore data as of 2026-08-23 (see git-free
  session history — no version control is set up yet, so there's no commit log to check instead).
