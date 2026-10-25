# Nepal Hydro-Geological Disaster Digital Twin

A live early-warning dashboard for two Nepal hazard hotspots, driven by machine-learning
models that train and run entirely on your machine:

- **Kathmandu Valley floods**: 14-day discharge forecasts for the Bagmati, Bishnumati and
  Dhobi Khola, with flood tiers and "unexpected future surge" warnings.
- **Mugling–Narayangadh corridor landslides** (Trishuli gorge): daily slope-failure
  probability, a physical slope stability index, and an interactive what-if simulator.
- **Historical collinearity & incident graph**: backtests how past weather triggers lined
  up with actual reported disasters.

## How it works

1. **Data**:
   - Open-Meteo provides ECMWF forecasts, the ERA5 archive, GloFAS river discharge, and
     DEM terrain.
   - Nepal's NDRRMA **BIPAD** portal provides 15 years of real flood and landslide incident
     reports, which serve as ground truth.
2. **Features**:
   - 7-day Antecedent Precipitation Index (γ = 0.85)
   - peak 1-hour cloudburst intensity
   - deep soil moisture (7–28 cm, 28–100 cm)
   - 24-hour pressure drop
   - terrain slope multiplier
   - seasonality
3. **Local models** (scikit-learn, saved with joblib at
   `backend/data/models/nepal_disaster_model.joblib`):
   - One `HistGradientBoostingRegressor` per river, mapping weather to discharge.
   - A `HistGradientBoostingClassifier`, mapping weather to the probability that a landslide
     is reported in the corridor that day.
   - An infinite-slope factor of safety as a physical cross-check.
   - A Holt-Winters baseline for surge detection.
4. **Background training**: the model trains automatically in about 1 minute on first
   start, and refreshes weekly.
5. **AI narratives**: a local Mistral model (Ollama) phrases the computed numbers. It never
   produces them.

See [CLAUDE.md](CLAUDE.md) for the full specification and every modelling decision.

## Stack

- **Backend**: FastAPI, SQLAlchemy (SQLite), pandas, scikit-learn, statsmodels, SciPy,
  networkx.
- **Frontend**: React 19 + Vite, with hand-written SVG charts.

## Project structure

```
backend/app/
  main.py                 # FastAPI app; starts background model training
  api/routes/             # system, data, analytics, simulation, admin
  api/status.py           # data-source health for the admin panel
  core/                   # config.py (keys, paths), regions.py (KTM/Mugling geography), security.py
  db/                     # SQLite: knowledge-graph edges, admin settings
  ingestion/
    hydro_geology.py      # Open-Meteo weather/archive/flood/elevation + BIPAD incidents
    weather.py            # current conditions
  models/
    simulation/disaster_ml.py   # features, training, prediction, surges, simulator, collinearity
    forecasting/holt_winters.py # surge-detection baseline
    risk/knowledge_graph.py     # driver -> hazard -> outcome graph
    llm/                        # Ollama narratives & dashboard summary
    registry.py                 # catalogue of every module; `python -m app.models.registry`
frontend/src/
  pages/                  # / overview, /flood, /landslide, /admin — one page each
  router/                 # tiny History-API router (no dependency)
  api/client.js           # backend client
  components/panels/      # KathmanduFloodPanel, MuglingLandslidePanel, InteractiveSimulator,
                          # CollinearityPanel, KnowledgeGraph*
  components/ui/          # MultiLineChart, ModelAttributionCard, StatusPill, TabBar, ...
  components/dashboard/   # ConditionsBar, DashboardSummaryCard
  components/admin/       # admin login, data sources & retrain, graph edges, settings
```

## Getting started

```bash
# backend
cd backend
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env          # all keys optional (see below)

# frontend
cd ../frontend && npm install

# optional: AI narratives
ollama pull mistral

# run everything (from the project root)
./start.sh
```

Open http://localhost:5173. On the very first start the model trains in the background
(about 1 minute). The dashboard shows "Training…" and fills in once it's ready. To train
in the foreground instead, run `cd backend && .venv/bin/python -m app.models.registry --train`.

### API keys

`WEATHER_API_KEY`, `FLOOD_API_KEY` and `LANDSLIDE_API_KEY` are all optional. Left blank,
the app uses Open-Meteo's free non-commercial endpoints. When a key is set, the matching
feed uses the paid `customer-*.open-meteo.com` endpoint instead. Keys can also be changed
at runtime from the admin settings panel.

## API overview

| Endpoint | Purpose |
|---|---|
| `GET /api/predict/disaster/nepal?region=kathmandu_flood` | Per-river flood forecast, peak times, surge warnings |
| `GET /api/predict/disaster/nepal?region=mugling_landslide` | Failure probability, slope stability index, landslide tier |
| `GET /api/analytics/disaster-collinearity?region=…` | Aligned history + Pearson/Spearman/VIF |
| `POST /api/simulate/disaster-interactive` | What-if: rain volume, cloudburst, soil saturation |
| `GET /api/weather?region=…` | Current conditions |
| `GET /api/feeds/river-discharge`, `/api/feeds/incidents?region=…` | Raw feeds |
| `GET /api/models/status` | Local model training state and holdout metrics |
| `GET /api/summary` | AI-written outlook across both regions |
| `GET /api/knowledge-graph` | Driver → hazard → outcome graph |
| `/api/admin/*` | Data sources, `POST models/retrain`, graph edges, settings |

Full OpenAPI docs: http://127.0.0.1:8000/docs
