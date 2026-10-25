# CLAUDE.md

Project guidance for Claude Code. Part 1 is the task specification as given by the project
owner. Part 2 records how it was implemented and the data-driven decisions behind it. Read
both before changing anything.

---

# Part 1: Task Specification: Nepal Flood & Landslide Local ML Digital Twin with Historical Collinearity Analytics

## Objective
Refactor the project into a localized **Nepal Hydro-Geological Disaster Digital Twin**. Remove all legacy air quality (NO₂), vegetation (NDVI), wildlife (GBIF), and market pricing modules. Implement a fully local background-trained Machine Learning pipeline (`scikit-learn` persisted via `joblib` at `backend/data/models/nepal_disaster_model.joblib`) driven by **3 distinct API keys** (`WEATHER_API_KEY`, `FLOOD_API_KEY`, `LANDSLIDE_API_KEY`), focusing specifically on:
1. **Kathmandu Valley (KTM)** for multi-river flood predictions (Bagmati, Bishnumati, Dhobi Khola).
2. **Mugling-Narayangadh Highway / Trishuli Gorge Corridor** for weather-driven landslide susceptibility predictions.
3. **Historical Collinearity & Incident Line Graph** backtesting past weather triggers against actual disaster spikes locally.

## 1. Environment & Configuration (`backend/app/core/config.py` & `.env.example`)
Update configuration settings to load three explicit API keys and target regions:
- `WEATHER_API_KEY=` (General meteorological forecasting and historical archives)
- `FLOOD_API_KEY=` (Open-Meteo Flood / GloFAS basin data for KTM)
- `LANDSLIDE_API_KEY=` (Specialized soil mechanics & slope data for Nepal corridors)
- `PILOT_REGION=kathmandu_flood` (default, with support for `nepal_landslide`)

## 2. Codebase Clean-up (Delete Unused Files)
Permanently delete the following unused legacy files and routes:
- `backend/app/ingestion/earth_engine/` (entire folder: no2, ndvi, aqi_proxy)
- `backend/app/ingestion/gbif.py`, `fuel_price.py`, `carbon_price.py`
- `backend/app/models/forecasting/aqi_forecast.py`
- `backend/app/models/xai/` (entire folder)
- `backend/app/models/risk/air_quality.py`, `vegetation.py`, `fauna.py`
- `backend/app/models/rl/` (entire folder)
- Corresponding frontend panels (`AqiPanel.jsx`, `VegetationPanel.jsx`, `FaunaPanel.jsx`, `OptimizerPanel.jsx`)

## 3. New Ingestion Layer (`backend/app/ingestion/hydro_geology.py`)
Using `WEATHER_API_KEY`, `FLOOD_API_KEY`, and `LANDSLIDE_API_KEY`:
1. **KTM Flood Feed:** Fetches daily river discharge (`river_discharge` in m³/s) from Open-Meteo Flood API for Kathmandu (`lat: 27.7172, lon: 85.3240`) covering Bagmati, Bishnumati, and Dhobi Khola sub-basins.
2. **Mugling Landslide Feed:** Fetches deep soil moisture (`7–28cm`, `28–100cm`), hourly precipitation, and barometric pressure drops for the Mugling-Narayangadh corridor (`lat: 27.8000, lon: 84.5400`).
3. **Weather Forecast & Archive:** Pulls multi-variable forecast data (7–14 days) and 90-day historical baselines.

## 4. Local Background ML Engine & Analytics (`backend/app/models/simulation/disaster_ml.py`)
Build a self-contained local scikit-learn training pipeline persisted via `joblib`:
1. **Local Feature Engineering (X):**
   - Antecedent Precipitation Index (API) using a 7-day soil drainage decay constant (γ = 0.85).
   - Peak 1-hour cloudburst intensity (`precip_max_hourly_mm`).
   - Deep soil saturation levels (`7-28cm` & `28-100cm`).
   - Topographic slope gradient multipliers (steep mountain corridor vs. valley floor).
2. **Local Models (Trained in Python, Saved to Disk):**
   - **Flood Discharge Regressor (`HistGradientBoostingRegressor`):** Maps local weather features → river discharge volume (m³/s) across Kathmandu sub-basins.
   - **Landslide Susceptibility Model:** Maps deep soil moisture + peak hourly rain + slope gradient → slope shear failure probability (z-score).
3. **Surge Detection:**
   - Compares local ML forecast output against baseline Holt-Winters smoothing to detect **"Unexpected Future Surges"** (Δz_surprise ≥ 1.0).
4. **Historical Collinearity & Incident Correlation:**
   - Locally computes Pearson/Spearman correlation coefficients between weather trigger drivers and actual past disaster spikes, returning aligned historical time-series data for the incident graph.

## 5. API Routes (`backend/app/api/routes/simulation.py`)
Expose clean endpoints:
- `GET /api/predict/disaster/nepal?region=kathmandu_flood` (returns river-specific flood breakdown, peak discharge times, and surge warnings).
- `GET /api/predict/disaster/nepal?region=mugling_landslide` (returns slope stability index and landslide risk tier).
- `GET /api/analytics/disaster-collinearity?region=kathmandu_flood` (returns aligned historical time-series and correlation metrics for past incident graphing).
- `POST /api/simulate/disaster-interactive` (takes custom slider inputs for rain volume, cloudburst intensity, and soil saturation to run local model inferences).

## 6. Frontend Dashboard (`frontend/src/`)
- Streamline `App.jsx` and navigation to feature two primary operational tabs: **Kathmandu Flood Early Warning & Multi-River Breakdown** and **Mugling Corridor Landslide Risk & Interactive Simulator**.
- Integrate a **Historical Collinearity & Incident Line Chart** showing how past weather trigger curves mirrored actual past disaster peaks.
- Update `client.js` to point to the new endpoints and render real-time status pills, risk charts, and model attribution cards.

---

# Part 2: Implementation notes (decisions and caveats)

These follow from what the real data sources actually provide (verified against the live
APIs on 2026-10-20). Keep them consistent when extending the code.

## Data sources actually used

| Feed | Provider | Key used |
|---|---|---|
| Hourly precipitation, surface pressure, soil moisture 7–28 cm / 28–100 cm (forecast) | Open-Meteo Forecast API, `models=ecmwf_ifs025` (only model exposing the ERA5-style 7–28/28–100 cm layers, 15-day horizon) | KTM: `WEATHER_API_KEY`; Mugling: `LANDSLIDE_API_KEY` |
| Same variables, historical (training + baselines) | Open-Meteo Historical API (ERA5, ~5-day lag) | same split as above |
| Daily river discharge, history + 30-day GloFAS forecast | Open-Meteo Flood API (GloFAS, ~5 km grid) | `FLOOD_API_KEY` |
| Terrain slope | Open-Meteo Elevation API (Copernicus 90 m DEM) | `LANDSLIDE_API_KEY` |
| Current conditions | Open-Meteo (AccuWeather fallback) | `WEATHER_API_KEY` |
| **Actual past incidents** (ground-truth labels) | Nepal Government NDRRMA **BIPAD Portal** API (`bipadportal.gov.np/api/v1/incident/`, hazard 17 = Landslide, 11 = Flood) | none (public) |

- **All three keys are optional.** Open-Meteo is free without a key for non-commercial use.
  When a key is set (in `.env` or the admin settings table, where the admin value wins), the
  request goes to the matching `customer-*.open-meteo.com` host with `&apikey=`. No
  dedicated "soil-mechanics API" exists for Nepal, so `LANDSLIDE_API_KEY` covers the
  corridor's soil, rain and terrain requests.
- The NASA Global Landslide Catalog endpoints are offline, so BIPAD is the incident source:
  about 250 verified landslides within 35 km of Mugling and about 130 floods within 15 km
  of Kathmandu since 2011. BIPAD reporting density rises sharply after 2016, which is
  reporting bias and not necessarily more hazard.
- GloFAS is a ~5 km grid. Each river is queried at its own coordinate, and the three
  resolve to three distinct grid cells, but the Bishnumati and Dhobi Khola are small
  streams, so their cells approximate those sub-basins and are not gauge readings.
- `PILOT_REGION` accepts `kathmandu_flood`, `mugling_landslide`, and the alias
  `nepal_landslide`, which maps to `mugling_landslide`.

## ML design

- **Training data:** daily features from 2011-01-01 to the ERA5 archive end, with all days
  in Asia/Kathmandu local time.
- **Features (`FEATURES`):**
  - `precip_sum_mm`, `precip_3d_mm`, `precip_max_hourly_mm`
  - `api_mm`: 7-day Antecedent Precipitation Index, `Σ_{k=0..6} 0.85^k · P(t−k)`
  - `sm_7_28`, `sm_28_100`
  - `pressure_drop_hpa`: the largest 24-hour fall in surface pressure within the day
  - `slope_multiplier`
  - `doy_sin`, `doy_cos`
- **Slope multiplier:** `tan(mean slope) / tan(10°)`, where the mean slope is sampled from
  the DEM over each region's bounding box. Because it is constant within a region it adds
  no signal to a single-region model. It is kept as a feature so the schema supports pooled
  multi-region training. Its real effect enters through the physical slope-stability index
  below.
- **Flood model:** one `HistGradientBoostingRegressor` per river, mapping KTM weather
  features to GloFAS discharge.
- **Landslide model:** `HistGradientBoostingClassifier`. The label is "≥ 1 BIPAD landslide
  reported within the corridor radius that day". The output is that probability plus its
  z-score against the distribution of historical daily predictions. It is left
  uncalibrated-by-weighting on purpose, so the probability keeps its plain meaning.
- **Validation:** time-based holdout of the final 730 days. Holdout metrics (R²/MAE for
  floods, ROC-AUC/PR-AUC for landslides) and permutation importances are stored in the
  bundle. Final models are then refit on all data.
- **Slope stability index:** an infinite-slope factor of safety (FoS) using stated, generic
  parameters (c′ = 5 kPa, φ′ = 32°, γ = 19 kN/m³, depth 2 m) and wetness taken from deep
  soil moisture, scaled between the region's own historical 2nd and 99.5th percentiles.
  These are illustrative and not calibrated for the Trishuli gorge.
- **Tiers** (`typical` / `elevated` / `severe`):
  - Flood: the peak forecast discharge against that river's historical P90 and P99.
  - Landslide: z ≥ 1 or FoS < 1.3 gives `elevated`; z ≥ 2 or FoS < 1.0 gives `severe`.
- **Surge detection:**
  - Holt-Winters (additive damped trend, fit on log1p) is run on the last 90 days of
    discharge and compared with the ML forecast.
  - `Δz = (ML − HW) / σ_90d`. A day with `Δz ≥ 1.0` is flagged as an unexpected future
    surge.
  - ECMWF IFS soil moisture is used at inference while the model was trained on ERA5. This
    distribution shift is a known caveat.
- **Background training:** at startup the bundle is loaded from disk. If it is missing or
  older than `MODEL_MAX_AGE_DAYS` (7), it retrains in a background thread. Prediction
  endpoints return 503 with a "training in progress" message until it is ready. Admins can
  force a retrain with `POST /api/admin/models/retrain`.
- **Collinearity:** computed locally from the daily frame stored in the bundle.
  - Pearson and Spearman correlations (with p-values) between each driver and each target:
    discharge or incident counts.
  - The landslide region is resampled weekly by default, because daily incident counts are
    sparse.
  - The response also includes a driver-to-driver correlation matrix, VIF, and aligned
    series for the chart.

## Conventions (unchanged from before)

- Layering: `api` → `models` → `ingestion` → `db`. Ingestion raises `RuntimeError` with a
  readable message, which routes map to 503. `ValueError` maps to 400.
- The LLM (Ollama/Mistral) only phrases computed numbers and always has a template fallback.
- Every uncalibrated constant is a named constant with a comment, and is surfaced as an
  `assumption` string in responses.
- Admin "auth" (`core/security.py`) is a plain header check and must not be exposed beyond
  localhost.
