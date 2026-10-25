# Nepal Hydro-Geological Disaster Digital Twin: Full Project Context

> **Note to the AI assistant reading this:** this document describes my software project
> in full. You do not have access to the code, so treat this as the source of truth for
> how it is built. When you suggest changes, use the file paths, function names and
> conventions described here. If something isn't covered, ask instead of guessing.

---

## 1. What the software is

A full-stack web dashboard: a "digital twin" for flood and landslide early warning in two
regions of Nepal.

1. **Kathmandu Valley** (lat 27.7172, lon 85.3240): river-flood prediction for the
   **Bagmati, Bishnumati and Dhobi Khola**.
2. **Mugling–Narayangadh highway / Trishuli gorge corridor** (lat 27.80, lon 84.54):
   weather-driven landslide susceptibility.
3. **Historical collinearity analytics**: backtests how past weather triggers lined up
   with actual reported disasters.

All machine learning trains and runs **locally** with scikit-learn, persisted via joblib.
A local LLM (Mistral via Ollama) only phrases already-computed numbers. It never computes
or invents them, and every LLM text has a template fallback.

This is an academic/research prototype running on localhost. It replaced an earlier
Vellore (India) air-quality/vegetation version; all of that code has been deleted.

### Design principles

- **Real ground truth.** The landslide model learns from real incident reports (Nepal
  NDRRMA BIPAD portal). The flood model learns from GloFAS river-discharge reanalysis.
- **Honest assumptions.** Every uncalibrated constant is a named constant and appears in
  the API response as an `"assumption"` string.
- **Graceful degradation.** A failing source returns HTTP 503 with a readable message.
  While the model is still training, prediction endpoints return 503 "training in
  progress".
- **Time-based validation.** The final 730 days are held out. Metrics are stored with the
  model and shown in the UI.

---

## 2. Tech stack

| Layer | Technology |
|---|---|
| Backend | Python 3.14, FastAPI, Uvicorn, Pydantic Settings, httpx |
| ML / stats | scikit-learn (HistGradientBoosting), joblib, statsmodels (Holt-Winters), SciPy (Pearson/Spearman), pandas, numpy |
| Graph | networkx |
| DB | SQLite via SQLAlchemy (only knowledge-graph edges + admin settings) |
| LLM | Ollama, model `mistral` (optional) |
| Frontend | React 19 + Vite 8, plain CSS, hand-written SVG charts |

---

## 3. Repository layout

```
Projrct-1/
├── CLAUDE.md               # task specification + implementation decisions
├── PROJECT_CONTEXT.md      # this file
├── README.md
├── start.sh                # starts Ollama (if present) + backend :8000 + frontend :5173
├── backend/
│   ├── requirements.txt
│   ├── .env.example
│   ├── data/app.db                              # SQLite (git-ignored)
│   ├── data/models/nepal_disaster_model.joblib  # trained bundle (git-ignored)
│   └── app/
│       ├── main.py             # init DB, seed knowledge graph, start background training, mount /api
│       ├── api/
│       │   ├── routes/         # system.py, data.py, analytics.py, simulation.py, admin.py
│       │   └── status.py       # data-source + model health for the admin panel
│       ├── core/
│       │   ├── config.py       # settings (keys, model path, Ollama)
│       │   ├── regions.py      # REGIONS, KTM_RIVERS, resolve_region()
│       │   └── security.py     # require_admin (plain header check — localhost only)
│       ├── db/                 # database.py, tables.py, crud.py
│       ├── ingestion/
│       │   ├── hydro_geology.py  # all external feeds (see §5)
│       │   └── weather.py        # current conditions (Open-Meteo, AccuWeather fallback)
│       └── models/
│           ├── simulation/disaster_ml.py   # the ML engine (see §6)
│           ├── forecasting/holt_winters.py # surge baseline
│           ├── risk/knowledge_graph.py     # driver → hazard → outcome graph
│           ├── llm/{ollama_client.py, narrative.py, dashboard_summary.py}
│           └── registry.py                 # catalogue + CLI of all modules
└── frontend/src/
    ├── App.jsx                 # nav + route → page
    ├── router/                 # router.js (navigate, useRoute), Link.jsx
    ├── pages/                  # OverviewPage, FloodPage, LandslidePage, AdminPage
    ├── api/client.js           # every backend call
    ├── context/AdminContext.jsx
    └── components/
        ├── panels/   KathmanduFloodPanel, MuglingLandslidePanel, InteractiveSimulator,
        │             CollinearityPanel, KnowledgeGraphPanel, KnowledgeGraphDiagram
        ├── ui/       MultiLineChart (+ChartLegend), ModelAttributionCard, StatTile,
        │             StatusPill, TabBar, NextRefreshCard, RiskScaleLegend
        ├── dashboard/ ConditionsBar, DashboardSummaryCard
        └── admin/    AdminLogin, AdminPanel, AdminDataSourcesPanel (with Retrain),
                      AdminKnowledgeGraphPanel, AdminSettingsPanel
```

**Layering:** `api` → `models` → `ingestion` → `db`. Ingestion never imports models.

---

## 4. Regions (`core/regions.py`)

| id | Label | Hazard | Point | Incident radius | BIPAD hazard id | Key |
|---|---|---|---|---|---|---|
| `kathmandu_flood` | Kathmandu Valley | flood | 27.7172, 85.3240 | 15 km | 11 | `WEATHER_API_KEY` |
| `mugling_landslide` | Mugling–Narayangadh corridor | landslide | 27.80, 84.54 | 35 km | 17 | `LANDSLIDE_API_KEY` |

- `nepal_landslide` is accepted as an alias for `mugling_landslide`, and `PILOT_REGION`
  sets the default.
- Rivers are queried at their own coordinates:
  - Bagmati: 27.6936, 85.3197
  - Bishnumati: 27.7330, 85.2990
  - Dhobi Khola: 27.7100, 85.3400
- These land in three distinct GloFAS ~5 km cells. The two small streams' cells are
  approximations, not gauge readings.

---

## 5. Data ingestion (`ingestion/hydro_geology.py`)

| Function | Source | Notes |
|---|---|---|
| `fetch_hourly_weather(region, start_date=, end_date=)` | Open-Meteo ERA5 archive | precip_mm, pressure_hpa, sm_7_28, sm_28_100; Asia/Kathmandu time; ~5-day lag |
| `fetch_hourly_weather(region, past_days=14, forecast_days=14)` | Open-Meteo forecast, `models=ecmwf_ifs025` | the only model exposing the 7–28 / 28–100 cm soil layers; 15-day max |
| `fetch_river_discharge(river, ...)` | Open-Meteo Flood API (GloFAS) | daily m³/s, history 1984+ and a forecast |
| `fetch_region_slope_deg(region)` | Open-Meteo Elevation (Copernicus 90 m DEM) | 6×6 grid over the region bbox, finite-difference slope; Mugling ≈ 17.4°, KTM valley ≈ 6.4° |
| `fetch_incidents(region, since)` | NDRRMA BIPAD `bipadportal.gov.np/api/v1/incident/` | paged, filtered by haversine distance; ~250 landslides near Mugling and ~130 floods near KTM since 2011 |

- **Keys:** `open_meteo_get(service, path, params, key_name)` uses the free host when the
  key is blank, and `customer-<service>.open-meteo.com` with `&apikey=` when it is set. An
  admin-settings override wins over `.env`.
- **Caching:** forecasts and discharge are cached for 15 minutes, incidents for 6 hours,
  and slope for the life of the process.

---

## 6. ML engine (`models/simulation/disaster_ml.py`)

**Features** (`build_daily_features`, one row per local day):

- `precip_sum_mm`
- `precip_3d_mm`
- `precip_max_hourly_mm` (cloudburst)
- `api_mm`: 7-day Antecedent Precipitation Index, `Σ_{k=0..6} 0.85^k · P(t−k)`
- `sm_7_28`, `sm_28_100`
- `pressure_drop_hpa`: the largest 24-hour fall in the day
- `slope_multiplier` = `tan(slope) / tan(10°)`. It is constant within a region and kept so
  the schema supports pooled training.
- `doy_sin`, `doy_cos`

**Training** (`train_bundle`, about 40 s; data from 2011-01-01 to today − 6 days):

- **Flood:** one `HistGradientBoostingRegressor` per river (400 iterations, learning rate
  0.05), mapping KTM weather to GloFAS discharge. Holdout R² is about 0.53 per river,
  using weather only.
- **Landslide:** `HistGradientBoostingClassifier`, where the label is "≥ 1 BIPAD landslide
  within 35 km that day". Holdout ROC-AUC is about 0.80 and PR-AUC about 0.29, against a
  base rate of about 0.066.
- **Also stored:** permutation importances, historical P90/P99 discharge thresholds, the
  probability mean/std (for z-scores), soil-moisture percentile references, monsoon
  medians, and the daily frames used for collinearity.

**Lifecycle:**

- `start_background_training(force=False)`, called at startup, loads the bundle and
  retrains in a daemon thread if it is missing, older than 7 days, or from an old version.
- `model_status()` reports training state and metrics.
- An admin can force a retrain with `POST /api/admin/models/retrain`.

**Predictions:**

- **`predict_kathmandu_flood(horizon_days=14)`**, for each river:
  - The ML forecast from ECMWF features.
  - A Holt-Winters baseline (damped additive trend on log1p) over the last 90 days.
  - `Δz = (ML − HW) / σ_90d`, with surges flagged where Δz ≥ 1.0.
  - A tier from the peak against P90 (`elevated`) and P99 (`severe`), the peak date, and
    the GloFAS forecast for reference.
- **`predict_mugling_landslide(horizon_days=14)`**, daily:
  - `failure_probability` and `failure_z`.
  - `slope_stability_index`: an infinite-slope factor of safety with c′ = 5 kPa, φ′ = 32°,
    γ = 19 kN/m³ and depth 2 m. Wetness comes from deep soil moisture scaled between the
    region's own 2nd and 99.5th percentiles.
  - Tier: `severe` if z ≥ 2 or FoS < 1.0; `elevated` if z ≥ 1 or FoS < 1.3.
- **Both** also return a narrative (LLM or template), `linked_outcomes` from the knowledge
  graph, and an `attribution` (model, technique, metrics, top drivers).
- **`simulate_interactive(rain_volume_mm, cloudburst_mm_per_hr, soil_saturation_pct,
  pressure_drop_hpa=None)`**: builds a hypothetical monsoon day and runs both models.
  - Unset features take the monsoon medians.
  - Saturation maps 0–100% onto the region's own soil-moisture range.
- **`disaster_collinearity(region_id, days_back=730, resample=None)`**:
  - Pearson and Spearman correlations, with p-values, between drivers and targets.
    Targets are Bagmati discharge and flood incidents for KTM (daily by default), and
    landslide incidents for Mugling (weekly by default).
  - Also returns a driver-to-driver correlation matrix, VIF, and aligned series for the
    chart.

---

## 7. REST API (`http://127.0.0.1:8000/api`, docs at `/docs`)

| Method | Endpoint | Notes |
|---|---|---|
| GET | `/health` | pilot region + region list |
| GET | `/models/status` | training state, period, holdout metrics |
| GET | `/weather?region=` | current conditions |
| GET | `/feeds/river-discharge?past_days=90&forecast_days=14` | three rivers |
| GET | `/feeds/incidents?region=&since=2011-01-01` | BIPAD incidents |
| GET | `/predict/disaster/nepal?region=kathmandu_flood\|mugling_landslide&horizon_days=14&include_narrative=true` | main prediction |
| GET | `/analytics/disaster-collinearity?region=&days_back=730&start=&end=&resample=D\|W\|M` | backtest (trailing window or explicit start/end) |
| POST | `/simulate/disaster-interactive` | body `{rain_volume_mm 0–600, cloudburst_mm_per_hr 0–200, soil_saturation_pct 0–100, pressure_drop_hpa?}` |
| GET | `/summary` | LLM summary across both regions |
| GET | `/knowledge-graph` | nodes + edges |
| — | `/admin/*` | `whoami`, `data-sources`, `POST models/retrain`, `settings` (GET/POST/DELETE), `knowledge-graph/edges` (GET/POST/DELETE); requires the `X-Admin-Email` header |

Errors: 400 for an unknown region or bad parameter, 422 for body validation, and 503 for a
source outage or a model that is still training.

---

## 8. Knowledge graph (DB table `knowledge_graph_edges`)

Seed edges (missing ones are inserted on startup; legacy Vellore edges are deleted):

- `rainfall_extreme` → `river_discharge`, `soil_saturation` (and a pre-existing →
  `waterborne_disease` edge)
- `river_discharge` → `flood_inundation`, `waterborne_disease`
- `soil_saturation` → `slope_failure`
- `slope_failure` → `road_blockage`, `injury_and_death`
- `standing_water` → `dengue` (placeholder; no live feed)

Citations include Iverson (2000), Dahal & Hasegawa (2008), Petley et al. (2007), WHO and
BIPAD. The frontend draws it as a layered (longest-path) diagram.

---

## 9. Frontend

Four separate pages with their own URLs, using a small History-API router
(`src/router/`; no routing dependency). Pages live in `src/pages/`:

- **`/` Overview (`OverviewPage`):**
  - conditions bar with both regions' weather and the model status tile
  - two region cards, each showing a live tier and headline and linking to its page
  - AI summary card and the knowledge graph
- **`/flood` Kathmandu flood (`FloodPage`, blue accent):**
  - Kathmandu weather only and a flood-specific risk legend
  - multi-river forecast: narrative, 15-minute auto-refresh, surge banner, per-river
    charts (observed, ML forecast, GloFAS forecast, Holt-Winters baseline, P90/P99 lines,
    surge markers), driver table and model attribution
  - flood-only scenario simulator
  - "Past floods" collinearity panel
- **`/landslide` Mugling landslide (`LandslidePage`, ochre accent):**
  - Mugling weather only and a landslide-specific legend
  - corridor outlook: today's metrics, 14-day failure-probability and stability-index
    charts, daily table and model attribution
  - landslide-only scenario simulator
  - "Past landslides" collinearity panel
- **`/admin` (`AdminPage`):** visible in the nav once verified. Data sources with a
  Retrain button, graph edges, and settings.
- **Collinearity panel:**
  - View dropdown (last 1/2/5 years, all time, by year, by month) with Year/Month dropdowns and ‹ › stepping; Resolution dropdown (daily / weekly / monthly; month view is always daily)
  - normalised multi-line chart with red incident ticks and toggleable legend
  - correlation table, driver heatmap and VIF table
- **Tiers:** `typical` (grey), `elevated` (amber), `severe` (red).

---

## 10. Configuration (`backend/.env`)

```
PILOT_REGION=kathmandu_flood
WEATHER_API_KEY=        # optional
FLOOD_API_KEY=          # optional
LANDSLIDE_API_KEY=      # optional
MODEL_MAX_AGE_DAYS=7
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=mistral
LLM_NARRATIVE_ENABLED=true
ACCUWEATHER_API_KEY=    # optional weather failsafe
```

---

## 11. Running

```bash
cd backend && python3 -m venv .venv && .venv/bin/pip install -r requirements.txt && cp .env.example .env
cd ../frontend && npm install
./start.sh                                           # from the project root
cd backend && .venv/bin/python -m app.models.registry --train   # optional foreground training
```

---

## 12. Known limitations

- BIPAD reporting density rises sharply after about 2016 (reporting bias). Labels mean
  "reported", not "occurred".
- The model trains on ERA5 soil moisture but forecasts with ECMWF IFS soil moisture, which
  introduces distribution shift.
- The flood model uses weather only. It has no upstream gauges, so holdout R² is about
  0.53.
- FoS parameters are generic and not calibrated for the site. The slope is a regional mean,
  not per-slope.
- The simulator extrapolates poorly beyond historical extremes.
- The admin check is not real authentication.
- There are no automated tests.
- The SQLite file may still contain unused legacy Vellore tables, which are harmless.
