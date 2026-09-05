# Earth Digital Twin for Public Health & Environmental Risk

A live "digital twin" dashboard for a pilot city (default: Vellore, India) that pulls real
environmental data — air quality, vegetation health, rainfall, and wildlife observations —
and turns it into forecasts, risk scores, and simulations that support public health and
environmental decision-making.

## What it does

- **Live monitoring** — current weather, AQI, NDVI (vegetation index), rainfall, and fauna
  (GBIF species observation) data for the pilot location, sourced from Google Earth Engine,
  CPCB/OpenAQ, IMD, and GBIF.
- **Forecasting** — short-term AQI forecasts with confidence bands, built on historical
  time series.
- **Risk assessment** — a knowledge-graph-driven risk model that scores air quality,
  vegetation, flood, and fauna risk together, with an explainability (XAI) layer showing
  which factors drive each forecast.
- **What-if simulation** — model the impact of disasters, traffic reduction, and
  afforestation programs on the local environment.
- **Budget optimization** — a reinforcement-learning-based optimizer for allocating
  mitigation budget across interventions.
- **AI narratives** — natural-language dashboard summaries and forecast narratives
  generated via a local LLM (Ollama).
- **Admin panel** — view data source health, manage historical records, and configure
  app settings, gated behind admin authentication.

## Stack

- **Backend**: FastAPI, SQLAlchemy, pandas/numpy/statsmodels, networkx, scikit-learn,
  SHAP, Gymnasium + Stable-Baselines3, Google Earth Engine API.
- **Frontend**: React 19 + Vite.

## Project structure

```
backend/
  app/
    api/        # FastAPI routes
    core/       # config/settings
    db/         # database models & session
    models/     # pydantic schemas
    services/
      admin/          # data source status, settings management
      cv/             # computer vision utilities
      fauna/          # GBIF species observation ingestion
      forecasting/    # time-series forecasting
      knowledge_graph/# risk assessment models (AQI, vegetation, flood, fauna)
      llm/            # Ollama-backed narrative & dashboard summary generation
      pricing/        # fuel & carbon price lookups
      rl/             # RL-based budget optimizer
      simulation/     # disaster/traffic/afforestation what-if engine
      weather/        # current weather lookup
      xai/            # forecast explainability
frontend/
  src/
    components/ # dashboard panels (AQI, vegetation, fauna, optimizer, admin, etc.)
```

## Getting started

### Backend

```bash
cd backend
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env   # fill in API keys and GEE project ID
.venv/bin/uvicorn app.main:app --reload --port 8000
```

Some data sources require one-time setup:
- Google Earth Engine: register a cloud project, then run `earthengine authenticate` once.
- CPCB AQI: [data.gov.in](https://data.gov.in) API key.
- OpenAQ: free API key from [openaq.org](https://openaq.org).
- IMD: requires a formal request / IP whitelisting.
- Copernicus, fuel price, and carbon price APIs: see `backend/.env.example` for the
  registration links each key needs.

### Frontend

```bash
cd frontend
npm install
npm run dev
```

### Run both together

```bash
./start.sh
```

This starts the backend on `http://127.0.0.1:8000` (API docs at `/docs`) and the
frontend on `http://localhost:5173`, waiting for both to become healthy.

## API overview

Key endpoints (see `/docs` for the full OpenAPI spec once running):

| Endpoint | Purpose |
|---|---|
| `GET /api/weather` | Current weather for the pilot location |
| `GET /api/aqi-proxy`, `/api/ndvi`, `/api/rainfall`, `/api/fauna` | Raw environmental data feeds |
| `GET /api/forecast/aqi` | AQI forecast with confidence bands |
| `GET /api/risk/aqi`, `/api/risk/vegetation`, `/api/risk/flood`, `/api/risk/fauna` | Risk scores per domain |
| `GET /api/explain/aqi` | XAI explanation of the AQI forecast |
| `GET /api/simulate/disaster`, `/api/simulate/traffic-reduction`, `/api/simulate/afforestation` | What-if simulations |
| `GET /api/optimize/budget` | RL-based mitigation budget optimizer |
| `GET /api/knowledge-graph` | Combined risk knowledge graph |
| `GET /api/summary` | AI-generated dashboard summary |
| `GET /api/history/*` | Historical time series per indicator |
| `/api/admin/*` | Admin-only data source, history, and settings management |
