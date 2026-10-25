"""Local machine-learning engine for the Nepal hydro-geological digital twin.

Everything here trains and runs on this machine (scikit-learn, persisted with joblib at
settings.model_path) — no hosted model, no LLM involved in any number. Pipeline:

  1. Feature engineering: hourly Open-Meteo weather → one row per local day (FEATURES).
  2. Flood: one HistGradientBoostingRegressor per Kathmandu river, KTM weather → GloFAS
     discharge (m³/s).
  3. Landslide: HistGradientBoostingClassifier, Mugling weather → P(≥1 BIPAD landslide
     reported within the corridor radius that day), plus its z-score vs. the historical
     distribution of daily predictions.
  4. Physical cross-check: infinite-slope factor of safety from deep soil wetness + DEM
     slope (the "slope stability index").
  5. Surge detection: ML discharge forecast vs. a Holt-Winters baseline of the last 90 days.
  6. Historical collinearity: Pearson/Spearman between trigger drivers and actual past
     disaster spikes, computed from the daily frames stored in the bundle.

Training runs in a background thread at startup when the bundle is missing or stale (see
start_background_training); prediction calls raise RuntimeError (→ HTTP 503) until a
bundle is available. Every uncalibrated constant below is named and surfaced in the API
responses as an assumption — see CLAUDE.md Part 2.
"""

import logging
import math
import threading
import time
from datetime import date, datetime, timedelta, timezone

import joblib
import numpy as np
import pandas as pd
from scipy import stats
from sklearn.ensemble import HistGradientBoostingClassifier, HistGradientBoostingRegressor
from sklearn.inspection import permutation_importance
from sklearn.metrics import average_precision_score, mean_absolute_error, r2_score, roc_auc_score

from app.core.config import settings
from app.core.regions import KTM_RIVERS, REGIONS, TIMEZONE
from app.ingestion.hydro_geology import (
    fetch_hourly_weather,
    fetch_incidents,
    fetch_region_slope_deg,
    fetch_river_discharge,
)
from app.models.forecasting.holt_winters import holt_winters_baseline
from app.models.llm.narrative import enrich_disaster_outlook
from app.models.risk.knowledge_graph import linked_outcomes

logger = logging.getLogger(__name__)

BUNDLE_VERSION = 1
TRAINING_START = "2011-01-01"
# ERA5 in the Open-Meteo archive trails real time by ~5 days.
ARCHIVE_LAG_DAYS = 6
HOLDOUT_DAYS = 730

# --- Feature engineering ---
API_DECAY = 0.85  # soil-drainage decay constant γ for the Antecedent Precipitation Index
API_WINDOW_DAYS = 7
# Reference slope for the multiplier: tan(β_region) / tan(10°). Valley floors land below 1,
# steep mountain corridors well above it.
REFERENCE_SLOPE_DEG = 10.0

FEATURES = [
    "precip_sum_mm",
    "precip_3d_mm",
    "precip_max_hourly_mm",
    "api_mm",
    "sm_7_28",
    "sm_28_100",
    "pressure_drop_hpa",
    "slope_multiplier",
    "doy_sin",
    "doy_cos",
]
FEATURE_LABELS = {
    "precip_sum_mm": "daily rainfall",
    "precip_3d_mm": "3-day rainfall",
    "precip_max_hourly_mm": "peak 1-hour cloudburst intensity",
    "api_mm": "antecedent precipitation index (7-day, γ=0.85)",
    "sm_7_28": "soil moisture 7–28 cm",
    "sm_28_100": "soil moisture 28–100 cm",
    "pressure_drop_hpa": "24-h barometric pressure drop",
    "slope_multiplier": "terrain slope multiplier",
    "doy_sin": "seasonal cycle (sin)",
    "doy_cos": "seasonal cycle (cos)",
}

# --- Infinite-slope factor of safety (stated, generic residual-soil parameters — NOT
# calibrated for the Trishuli gorge; illustrative physics cross-check only) ---
COHESION_KPA = 5.0
FRICTION_ANGLE_DEG = 32.0
SOIL_UNIT_WEIGHT_KN_M3 = 19.0
WATER_UNIT_WEIGHT_KN_M3 = 9.81
FAILURE_DEPTH_M = 2.0

# --- Tier thresholds ---
FLOOD_ELEVATED_PCTL = 0.90
FLOOD_SEVERE_PCTL = 0.99
LANDSLIDE_ELEVATED_Z = 1.0
LANDSLIDE_SEVERE_Z = 2.0
FOS_ELEVATED = 1.3
FOS_SEVERE = 1.0
SURGE_DZ = 1.0  # Δz_surprise threshold for an "unexpected future surge"
SURGE_HISTORY_DAYS = 90

_state = {"bundle": None, "status": "idle", "error": None, "started_at": None, "finished_at": None}
_state_lock = threading.Lock()


# ---------------------------------------------------------------------------
# Feature engineering
# ---------------------------------------------------------------------------


def slope_multiplier(slope_deg: float) -> float:
    return math.tan(math.radians(slope_deg)) / math.tan(math.radians(REFERENCE_SLOPE_DEG))


def build_daily_features(hourly: pd.DataFrame, slope_deg: float) -> pd.DataFrame:
    """Hourly weather (precip_mm, pressure_hpa, sm_7_28, sm_28_100) → one row per local
    day with every column in FEATURES. Rolling features need a few days of lead-in, so the
    first API_WINDOW_DAYS rows are dropped."""
    day = hourly.index.floor("D")
    grouped = hourly.groupby(day)
    pressure_drop = (hourly["pressure_hpa"].shift(24) - hourly["pressure_hpa"]).clip(lower=0)

    daily = pd.DataFrame(
        {
            "precip_sum_mm": grouped["precip_mm"].sum(),
            "precip_max_hourly_mm": grouped["precip_mm"].max(),
            "sm_7_28": grouped["sm_7_28"].mean(),
            "sm_28_100": grouped["sm_28_100"].mean(),
            "pressure_drop_hpa": pressure_drop.groupby(day).max(),
        }
    )
    daily["precip_3d_mm"] = daily["precip_sum_mm"].rolling(3).sum()
    weights = API_DECAY ** np.arange(API_WINDOW_DAYS)  # weights[0] applies to today
    daily["api_mm"] = daily["precip_sum_mm"].rolling(API_WINDOW_DAYS).apply(lambda w: float(np.dot(w[::-1], weights)), raw=True)
    daily["slope_multiplier"] = slope_multiplier(slope_deg)
    doy = daily.index.dayofyear
    daily["doy_sin"] = np.sin(2 * np.pi * doy / 365.25)
    daily["doy_cos"] = np.cos(2 * np.pi * doy / 365.25)
    return daily.iloc[API_WINDOW_DAYS:][FEATURES].dropna()


def factor_of_safety(slope_deg: float, wetness: float) -> float:
    """Infinite-slope factor of safety: FoS = c′/(γ z sinβ cosβ) + (1 − m γw/γ)·tanφ′/tanβ,
    with m the saturated fraction of the failure depth. FoS < 1 means the slope's
    resisting strength no longer exceeds the driving stress."""
    beta = math.radians(max(slope_deg, 0.5))
    m = min(max(wetness, 0.0), 1.0)
    cohesion_term = COHESION_KPA / (SOIL_UNIT_WEIGHT_KN_M3 * FAILURE_DEPTH_M * math.sin(beta) * math.cos(beta))
    friction_term = (1 - m * WATER_UNIT_WEIGHT_KN_M3 / SOIL_UNIT_WEIGHT_KN_M3) * math.tan(math.radians(FRICTION_ANGLE_DEG)) / math.tan(beta)
    return cohesion_term + friction_term


def _wetness(sm: float, refs: dict) -> float:
    span = refs["sm_sat"] - refs["sm_dry"]
    return float(np.clip((sm - refs["sm_dry"]) / span, 0, 1)) if span > 0 else 0.0


# ---------------------------------------------------------------------------
# Training
# ---------------------------------------------------------------------------


def _region_training_frame(region: dict, end: str) -> tuple[pd.DataFrame, float]:
    slope = fetch_region_slope_deg(region)
    hourly = fetch_hourly_weather(region, start_date=TRAINING_START, end_date=end)
    return build_daily_features(hourly, slope), slope


def _incident_counts(region: dict, index: pd.DatetimeIndex) -> pd.Series:
    incidents = fetch_incidents(region, since=TRAINING_START)
    counts = incidents.groupby("date").size() if not incidents.empty else pd.Series(dtype=int)
    return counts.reindex(index, fill_value=0).astype(int)


def _split(frame: pd.DataFrame):
    cutoff = frame.index.max() - pd.Timedelta(days=HOLDOUT_DAYS)
    return frame[frame.index <= cutoff], frame[frame.index > cutoff]


def _importances(model, X: pd.DataFrame, y: pd.Series, scoring: str) -> list[dict]:
    result = permutation_importance(model, X, y, n_repeats=5, random_state=0, scoring=scoring)
    ranked = sorted(zip(FEATURES, result.importances_mean), key=lambda t: -t[1])
    return [{"feature": f, "label": FEATURE_LABELS[f], "importance": float(v)} for f, v in ranked]


def _train_flood(frame: pd.DataFrame, end: str) -> dict:
    rivers = {}
    for river in KTM_RIVERS:
        discharge = fetch_river_discharge(river, start_date=TRAINING_START, end_date=end)
        data = frame.join(discharge.rename("discharge"), how="inner").dropna()
        train, test = _split(data)

        def make():
            return HistGradientBoostingRegressor(max_iter=400, learning_rate=0.05, max_leaf_nodes=31, l2_regularization=1.0, random_state=0)

        holdout_model = make().fit(train[FEATURES], train["discharge"])
        predicted = holdout_model.predict(test[FEATURES])
        final = make().fit(data[FEATURES], data["discharge"])
        rivers[river["id"]] = {
            "model": final,
            "metrics": {
                "holdout_r2": float(r2_score(test["discharge"], predicted)),
                "holdout_mae_m3s": float(mean_absolute_error(test["discharge"], predicted)),
                "holdout_days": len(test),
                "train_days": len(data),
            },
            "importances": _importances(holdout_model, test[FEATURES], test["discharge"], "r2"),
            "thresholds": {
                "p90": float(data["discharge"].quantile(FLOOD_ELEVATED_PCTL)),
                "p99": float(data["discharge"].quantile(FLOOD_SEVERE_PCTL)),
                "max": float(data["discharge"].max()),
            },
            "discharge": data["discharge"],
        }
    return rivers


def _train_landslide(frame: pd.DataFrame, region: dict) -> dict:
    counts = _incident_counts(region, frame.index)
    labels = (counts > 0).astype(int)
    train, test = _split(frame)

    def make():
        return HistGradientBoostingClassifier(max_iter=300, learning_rate=0.05, max_leaf_nodes=15, l2_regularization=1.0, random_state=0)

    holdout_model = make().fit(train[FEATURES], labels[train.index])
    test_proba = holdout_model.predict_proba(test[FEATURES])[:, 1]
    final = make().fit(frame[FEATURES], labels)
    history_proba = final.predict_proba(frame[FEATURES])[:, 1]
    return {
        "model": final,
        "metrics": {
            "holdout_roc_auc": float(roc_auc_score(labels[test.index], test_proba)),
            "holdout_pr_auc": float(average_precision_score(labels[test.index], test_proba)),
            "holdout_base_rate": float(labels[test.index].mean()),
            "positive_days": int(labels.sum()),
            "incidents": int(counts.sum()),
            "train_days": len(frame),
        },
        "importances": _importances(holdout_model, test[FEATURES], labels[test.index], "roc_auc"),
        "proba_mean": float(history_proba.mean()),
        "proba_std": float(history_proba.std()) or 1e-9,
        "incident_counts": counts,
    }


def _soil_refs(frame: pd.DataFrame) -> dict:
    """Region's own soil-moisture range, used to turn m³/m³ into a 0–1 wetness and to map
    the simulator's saturation slider back onto realistic values."""
    return {
        "sm_dry": float(frame["sm_28_100"].quantile(0.02)),
        "sm_sat": float(frame["sm_28_100"].quantile(0.995)),
        "sm_7_28_dry": float(frame["sm_7_28"].quantile(0.02)),
        "sm_7_28_sat": float(frame["sm_7_28"].quantile(0.995)),
    }


def train_bundle() -> dict:
    """Fetch the full history, train every model, and return the bundle (not yet saved).
    Takes ~1–2 minutes, dominated by the archive download."""
    end = (date.today() - timedelta(days=ARCHIVE_LAG_DAYS)).isoformat()
    ktm = REGIONS["kathmandu_flood"]
    mug = REGIONS["mugling_landslide"]

    ktm_frame, ktm_slope = _region_training_frame(ktm, end)
    mug_frame, mug_slope = _region_training_frame(mug, end)
    flood = _train_flood(ktm_frame, end)
    landslide = _train_landslide(mug_frame, mug)

    monsoon = lambda f: f[f.index.month.isin([6, 7, 8, 9])][FEATURES].median().to_dict()  # noqa: E731
    return {
        "version": BUNDLE_VERSION,
        "trained_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "training_period": {"start": TRAINING_START, "end": end},
        "features": FEATURES,
        "regions": {
            ktm["id"]: {
                "slope_deg": ktm_slope,
                "frame": ktm_frame,
                "soil": _soil_refs(ktm_frame),
                "monsoon_median": monsoon(ktm_frame),
                "flood_incident_counts": _incident_counts(ktm, ktm_frame.index),
            },
            mug["id"]: {
                "slope_deg": mug_slope,
                "frame": mug_frame,
                "soil": _soil_refs(mug_frame),
                "monsoon_median": monsoon(mug_frame),
            },
        },
        "flood": flood,
        "landslide": landslide,
    }


# ---------------------------------------------------------------------------
# Background lifecycle
# ---------------------------------------------------------------------------


def _train_and_save() -> None:
    with _state_lock:
        if _state["status"] == "training":
            return
        _state.update(status="training", error=None, started_at=time.time())
    try:
        bundle = train_bundle()
        settings.model_path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(bundle, settings.model_path, compress=3)
        with _state_lock:
            _state.update(bundle=bundle, status="ready", finished_at=time.time())
        logger.info("Nepal disaster model trained and saved to %s", settings.model_path)
    except Exception as exc:  # noqa: BLE001 — any failure must surface in /models/status, not kill the thread silently
        logger.exception("Background model training failed")
        with _state_lock:
            _state.update(status="failed", error=str(exc), finished_at=time.time())


def start_background_training(force: bool = False) -> None:
    """Load the persisted bundle if present; (re)train in a daemon thread if it's missing,
    older than settings.model_max_age_days, from an older BUNDLE_VERSION, or `force`d.
    A stale-but-loadable bundle keeps serving predictions while the refresh runs."""
    path = settings.model_path
    if path.exists() and _state["bundle"] is None:
        try:
            bundle = joblib.load(path)
            if bundle.get("version") == BUNDLE_VERSION:
                with _state_lock:
                    _state.update(bundle=bundle, status="ready")
        except Exception as exc:  # noqa: BLE001 — a corrupt file just means retrain
            logger.warning("Could not load %s (%s); retraining", path, exc)

    age_days = (time.time() - path.stat().st_mtime) / 86400 if path.exists() else math.inf
    if force or _state["bundle"] is None or age_days > settings.model_max_age_days:
        threading.Thread(target=_train_and_save, name="disaster-ml-trainer", daemon=True).start()


def model_status() -> dict:
    with _state_lock:
        bundle = _state["bundle"]
        status = {
            "status": _state["status"],
            "error": _state["error"],
            "training_started_at": _iso(_state["started_at"]),
            "training_finished_at": _iso(_state["finished_at"]),
            "model_path": str(settings.model_path),
            "bundle_available": bundle is not None,
        }
    if bundle is not None:
        status.update(
            trained_at=bundle["trained_at"],
            training_period=bundle["training_period"],
            flood_models={rid: r["metrics"] for rid, r in bundle["flood"].items()},
            landslide_model=bundle["landslide"]["metrics"],
        )
    return status


def _iso(ts: float | None) -> str | None:
    return datetime.fromtimestamp(ts, timezone.utc).isoformat(timespec="seconds") if ts else None


def _bundle() -> dict:
    bundle = _state["bundle"]
    if bundle is None:
        if _state["status"] == "failed":
            raise RuntimeError(f"Local model training failed: {_state['error']}. An admin can retry via POST /api/admin/models/retrain.")
        raise RuntimeError("The local ML model is still training in the background (first run takes ~1–2 minutes). Try again shortly.")
    return bundle


# ---------------------------------------------------------------------------
# Inference
# ---------------------------------------------------------------------------


def _flood_tier(value: float, thresholds: dict) -> str:
    if value >= thresholds["p99"]:
        return "severe"
    if value >= thresholds["p90"]:
        return "elevated"
    return "typical"


def _landslide_tier(z: float, fos: float) -> str:
    if z >= LANDSLIDE_SEVERE_Z or fos < FOS_SEVERE:
        return "severe"
    if z >= LANDSLIDE_ELEVATED_Z or fos < FOS_ELEVATED:
        return "elevated"
    return "typical"


def _worst(tiers: list[str]) -> str:
    order = ["typical", "elevated", "severe"]
    return max(tiers, key=order.index) if tiers else "typical"


def _nepal_today() -> pd.Timestamp:
    return pd.Timestamp.now(tz=TIMEZONE).normalize().tz_localize(None)


def _forecast_features(region: dict, slope_deg: float, horizon_days: int) -> pd.DataFrame:
    hourly = fetch_hourly_weather(region, past_days=14, forecast_days=horizon_days)
    features = build_daily_features(hourly, slope_deg)
    return features[features.index >= _nepal_today()].iloc[:horizon_days]


def _attribution(name: str, technique: str, bundle: dict, metrics: dict, importances: list[dict]) -> dict:
    return {
        "model": name,
        "technique": technique,
        "trained_at": bundle["trained_at"],
        "training_period": bundle["training_period"],
        "metrics": metrics,
        "top_drivers": importances[:5],
    }


def predict_kathmandu_flood(horizon_days: int = 14, include_narrative: bool = True) -> dict:
    """Per-river ML discharge forecast for the next `horizon_days`, its flood tier against
    each river's own historical percentiles, the peak day, and surge warnings where the ML
    forecast exceeds the Holt-Winters baseline by Δz ≥ SURGE_DZ."""
    bundle = _bundle()
    region = REGIONS["kathmandu_flood"]
    features = _forecast_features(region, bundle["regions"][region["id"]]["slope_deg"], horizon_days)
    if features.empty:
        raise RuntimeError("No forecast days available from the ECMWF feed right now.")

    rivers = []
    for river in KTM_RIVERS:
        trained = bundle["flood"][river["id"]]
        ml = pd.Series(trained["model"].predict(features[FEATURES]).clip(min=0), index=features.index)
        recent = fetch_river_discharge(river, past_days=SURGE_HISTORY_DAYS, forecast_days=horizon_days)
        history = recent[recent.index < _nepal_today()]
        glofas_forecast = recent[recent.index >= _nepal_today()]
        baseline = holt_winters_baseline(history, len(ml))
        baseline.index = ml.index
        sigma = float(history.std()) or 1e-6
        dz = (ml - baseline) / sigma

        peak_date = ml.idxmax()
        surges = [
            {"date": d.strftime("%Y-%m-%d"), "ml_m3s": float(ml[d]), "baseline_m3s": float(baseline[d]), "delta_z": float(dz[d])}
            for d in ml.index
            if dz[d] >= SURGE_DZ
        ]
        rivers.append(
            {
                "river_id": river["id"],
                "river": river["name"],
                "risk_tier": _flood_tier(float(ml.max()), trained["thresholds"]),
                "current_m3s": float(history.iloc[-1]),
                "peak_m3s": float(ml.max()),
                "peak_date": peak_date.strftime("%Y-%m-%d"),
                "thresholds_m3s": trained["thresholds"],
                "surge_warning": bool(surges),
                "surges": surges,
                "max_delta_z": float(dz.max()),
                "forecast": [
                    {
                        "date": d.strftime("%Y-%m-%d"),
                        "ml_m3s": float(ml[d]),
                        "baseline_m3s": float(baseline[d]),
                        "glofas_m3s": float(glofas_forecast[d]) if d in glofas_forecast.index else None,
                        "delta_z": float(dz[d]),
                    }
                    for d in ml.index
                ],
                "history": [{"date": d.strftime("%Y-%m-%d"), "m3s": float(v)} for d, v in history.items()],
                "attribution": _attribution(
                    f"{river['name']} discharge regressor",
                    "HistGradientBoostingRegressor (scikit-learn), KTM weather → GloFAS discharge",
                    bundle,
                    trained["metrics"],
                    trained["importances"],
                ),
            }
        )

    risk_tier = _worst([r["risk_tier"] for r in rivers])
    surge = any(r["surge_warning"] for r in rivers)
    facts = [
        f"{r['river']}: {r['risk_tier']} — now {r['current_m3s']:.1f} m³/s, forecast peak {r['peak_m3s']:.1f} m³/s on "
        f"{r['peak_date']} (P90 {r['thresholds_m3s']['p90']:.1f}, P99 {r['thresholds_m3s']['p99']:.1f} m³/s)"
        + (f"; unexpected surge, Δz up to {r['max_delta_z']:.1f}" if r["surge_warning"] else "")
        for r in rivers
    ]
    fallback = (
        f"Kathmandu Valley flood outlook is {risk_tier} for the next {len(features)} days. "
        + " ".join(
            f"The {r['river']} is forecast to peak at {r['peak_m3s']:.1f} m³/s on {r['peak_date']}."
            for r in rivers
        )
        + (" At least one river shows an unexpected surge above its recent trend." if surge else "")
    )
    return {
        "region": region["id"],
        "region_label": region["label"],
        "hazard": "flood",
        "risk_tier": risk_tier,
        "surge_warning": surge,
        "horizon_days": len(features),
        "rivers": rivers,
        "drivers_forecast": _drivers_table(features),
        "linked_outcomes": linked_outcomes("river_discharge"),
        "narrative": enrich_disaster_outlook(region_label=region["label"], facts=facts, fallback=fallback)
        if include_narrative
        else fallback,
        "assumption": (
            f"Tiers compare each river's peak ML forecast with its own 2011–present GloFAS "
            f"discharge: ≥P{FLOOD_ELEVATED_PCTL * 100:.0f} elevated, ≥P{FLOOD_SEVERE_PCTL * 100:.0f} severe. "
            f"A surge is flagged where (ML − Holt-Winters baseline) / σ of the last {SURGE_HISTORY_DAYS} days ≥ {SURGE_DZ}. "
            "The model trains on ERA5 soil moisture but forecasts with ECMWF IFS, and GloFAS cells for the "
            "Bishnumati and Dhobi Khola approximate small sub-basins — treat values as indicative."
        ),
    }


def _landslide_assessment(row: pd.Series, bundle: dict) -> dict:
    trained = bundle["landslide"]
    refs = bundle["regions"]["mugling_landslide"]
    proba = float(trained["model"].predict_proba(row[FEATURES].to_frame().T.astype(float))[:, 1][0])
    z = (proba - trained["proba_mean"]) / trained["proba_std"]
    wetness = _wetness(float(row["sm_28_100"]), refs["soil"])
    fos = factor_of_safety(refs["slope_deg"], wetness)
    return {
        "failure_probability": proba,
        "failure_z": float(z),
        "wetness": wetness,
        "slope_stability_index": fos,
        "risk_tier": _landslide_tier(z, fos),
    }


def predict_mugling_landslide(horizon_days: int = 14, include_narrative: bool = True) -> dict:
    """Daily landslide outlook for the Mugling–Narayangadh corridor: ML failure probability
    and z-score, infinite-slope stability index, and the resulting tier."""
    bundle = _bundle()
    region = REGIONS["mugling_landslide"]
    refs = bundle["regions"][region["id"]]
    features = _forecast_features(region, refs["slope_deg"], horizon_days)
    if features.empty:
        raise RuntimeError("No forecast days available from the ECMWF feed right now.")

    days = []
    for d, row in features.iterrows():
        days.append({"date": d.strftime("%Y-%m-%d"), **_landslide_assessment(row, bundle), **{f: float(row[f]) for f in FEATURES[:7]}})
    peak = max(days, key=lambda x: x["failure_z"])
    trained = bundle["landslide"]
    risk_tier = _worst([d["risk_tier"] for d in days])
    facts = [
        f"Overall {len(days)}-day tier: {risk_tier}",
        f"Today: failure probability {days[0]['failure_probability']:.1%} (z {days[0]['failure_z']:+.1f}), "
        f"slope stability index {days[0]['slope_stability_index']:.2f}",
        f"How to read the slope stability index (a factor of safety): at or above {FOS_ELEVATED} the slope is stable, "
        f"below {FOS_ELEVATED} it is marginal, below {FOS_SEVERE} it is expected to fail",
        f"How to read z: it compares the failure probability with all past days; below {LANDSLIDE_ELEVATED_Z} is normal",
        f"Highest-risk day {peak['date']}: failure probability {peak['failure_probability']:.1%} (z {peak['failure_z']:+.1f}), "
        f"{peak['precip_sum_mm']:.0f} mm rain, peak {peak['precip_max_hourly_mm']:.1f} mm/h",
    ]
    fallback = (
        f"Mugling–Narayangadh landslide outlook is {risk_tier} for the next {len(days)} days. The highest-risk day is "
        f"{peak['date']}, with a modelled failure probability of {peak['failure_probability']:.1%} "
        f"and a slope stability index of {peak['slope_stability_index']:.2f}."
    )

    return {
        "region": region["id"],
        "region_label": region["label"],
        "hazard": "landslide",
        "risk_tier": risk_tier,
        "today": days[0],
        "peak": peak,
        "slope_deg": refs["slope_deg"],
        "slope_multiplier": slope_multiplier(refs["slope_deg"]),
        # Failure-probability levels matching the z tiers, for drawing threshold lines.
        "probability_thresholds": {
            "elevated": trained["proba_mean"] + LANDSLIDE_ELEVATED_Z * trained["proba_std"],
            "severe": trained["proba_mean"] + LANDSLIDE_SEVERE_Z * trained["proba_std"],
        },
        "fos_thresholds": {"elevated": FOS_ELEVATED, "severe": FOS_SEVERE},
        "horizon_days": len(days),
        "daily": days,
        "linked_outcomes": linked_outcomes("soil_saturation", "slope_failure"),
        "narrative": enrich_disaster_outlook(region_label=region["label"], facts=facts, fallback=fallback)
        if include_narrative
        else fallback,
        "attribution": _attribution(
            "Corridor landslide susceptibility classifier",
            "HistGradientBoostingClassifier (scikit-learn), corridor weather → P(≥1 BIPAD landslide within "
            f"{region['incident_radius_km']} km that day)",
            bundle,
            trained["metrics"],
            trained["importances"],
        ),
        "assumption": (
            f"failure_probability is the model's probability that at least one landslide is reported within "
            f"{region['incident_radius_km']} km of the corridor that day, learned from NDRRMA BIPAD records (reporting "
            f"bias applies). failure_z compares it with all historical days. The slope stability index is an "
            f"infinite-slope factor of safety with generic parameters (c′={COHESION_KPA:g} kPa, φ′={FRICTION_ANGLE_DEG:g}°, "
            f"depth {FAILURE_DEPTH_M:g} m) on the DEM mean slope of {refs['slope_deg']:.1f}° — illustrative, not site-calibrated. "
            f"Severe if z ≥ {LANDSLIDE_SEVERE_Z} or FoS < {FOS_SEVERE}; elevated if z ≥ {LANDSLIDE_ELEVATED_Z} or FoS < {FOS_ELEVATED}."
        ),
    }


def _drivers_table(features: pd.DataFrame) -> list[dict]:
    return [{"date": d.strftime("%Y-%m-%d"), **{f: float(row[f]) for f in FEATURES[:7]}} for d, row in features.iterrows()]


def simulate_interactive(
    rain_volume_mm: float,
    cloudburst_mm_per_hr: float,
    soil_saturation_pct: float,
    pressure_drop_hpa: float | None = None,
) -> dict:
    """Run the trained models on a hypothetical monsoon day. The sliders set today's
    rainfall, its peak hourly intensity and deep-soil saturation (0% = the region's own
    driest 2nd percentile, 100% = its wettest 99.5th); every other feature takes that
    region's monsoon (Jun–Sep) median, and the 7-day API is today's rain on top of the
    decayed monsoon-median antecedent rain."""
    if rain_volume_mm < 0 or cloudburst_mm_per_hr < 0:
        raise ValueError("Rain volume and cloudburst intensity must be non-negative.")
    if not 0 <= soil_saturation_pct <= 100:
        raise ValueError("soil_saturation_pct must be between 0 and 100.")
    cloudburst = min(cloudburst_mm_per_hr, rain_volume_mm) if rain_volume_mm else 0.0
    bundle = _bundle()
    frac = soil_saturation_pct / 100

    def scenario_row(region_id: str) -> pd.Series:
        refs = bundle["regions"][region_id]
        base = dict(refs["monsoon_median"])
        soil = refs["soil"]
        base.update(
            precip_sum_mm=rain_volume_mm,
            precip_max_hourly_mm=cloudburst,
            precip_3d_mm=rain_volume_mm + base["precip_3d_mm"] * 2 / 3,
            api_mm=rain_volume_mm + API_DECAY * base["api_mm"],
            sm_28_100=soil["sm_dry"] + frac * (soil["sm_sat"] - soil["sm_dry"]),
            sm_7_28=soil["sm_7_28_dry"] + frac * (soil["sm_7_28_sat"] - soil["sm_7_28_dry"]),
            slope_multiplier=slope_multiplier(refs["slope_deg"]),
        )
        if pressure_drop_hpa is not None:
            base["pressure_drop_hpa"] = pressure_drop_hpa
        return pd.Series(base)[FEATURES]

    ktm_row = scenario_row("kathmandu_flood")
    rivers = []
    for river in KTM_RIVERS:
        trained = bundle["flood"][river["id"]]
        value = float(max(trained["model"].predict(ktm_row.to_frame().T.astype(float))[0], 0))
        rivers.append(
            {
                "river_id": river["id"],
                "river": river["name"],
                "discharge_m3s": value,
                "risk_tier": _flood_tier(value, trained["thresholds"]),
                "pct_of_p99": value / trained["thresholds"]["p99"] * 100,
                "thresholds_m3s": trained["thresholds"],
            }
        )

    mug_row = scenario_row("mugling_landslide")
    return {
        "inputs": {
            "rain_volume_mm": rain_volume_mm,
            "cloudburst_mm_per_hr": cloudburst,
            "soil_saturation_pct": soil_saturation_pct,
            "pressure_drop_hpa": float(mug_row["pressure_drop_hpa"]),
        },
        "flood": {"risk_tier": _worst([r["risk_tier"] for r in rivers]), "rivers": rivers},
        "landslide": _landslide_assessment(mug_row, bundle),
        "assumption": (
            "Hypothetical single day. Unset features use each region's monsoon (Jun–Sep) median; saturation maps "
            "0–100% onto that region's own 2nd–99.5th percentile of ERA5 soil moisture. Cloudburst intensity is "
            "capped at the day's rain volume. Models extrapolate poorly beyond the historical range."
        ),
    }


# ---------------------------------------------------------------------------
# Historical collinearity
# ---------------------------------------------------------------------------

_COLLINEARITY_DRIVERS = {
    "kathmandu_flood": ["precip_sum_mm", "precip_3d_mm", "api_mm", "precip_max_hourly_mm", "sm_28_100"],
    "mugling_landslide": ["api_mm", "precip_max_hourly_mm", "sm_7_28", "sm_28_100", "pressure_drop_hpa"],
}
# How each column aggregates when resampling to weeks or months.
# resample code -> pandas frequency (None = keep daily rows). Weeks end on Sunday, months
# on their last day ("ME" is pandas' month-end alias).
_RESAMPLE_FREQ = {"D": None, "W": "W", "M": "ME"}
_RESAMPLE_HOW = {
    "precip_sum_mm": "sum",
    "precip_3d_mm": "max",
    "api_mm": "max",
    "precip_max_hourly_mm": "max",
    "sm_7_28": "mean",
    "sm_28_100": "mean",
    "pressure_drop_hpa": "max",
    "discharge_m3s": "max",
    "incidents": "sum",
}


def _corr(x: pd.Series, y: pd.Series) -> dict:
    data = pd.concat([x, y], axis=1).dropna()
    if len(data) < 10 or data.iloc[:, 0].std() == 0 or data.iloc[:, 1].std() == 0:
        return {"pearson_r": None, "pearson_p": None, "spearman_rho": None, "spearman_p": None, "n": len(data)}
    pr = stats.pearsonr(data.iloc[:, 0], data.iloc[:, 1])
    sr = stats.spearmanr(data.iloc[:, 0], data.iloc[:, 1])
    return {
        "pearson_r": float(pr.statistic),
        "pearson_p": float(pr.pvalue),
        "spearman_rho": float(sr.statistic),
        "spearman_p": float(sr.pvalue),
        "n": len(data),
    }


def _vif(frame: pd.DataFrame) -> dict:
    """Variance inflation factor per driver: 1 / (1 − R²) of that driver regressed on the
    others. >5 is commonly read as problematic collinearity, >10 as severe."""
    out = {}
    X = frame.dropna().to_numpy(dtype=float)
    for i, col in enumerate(frame.columns):
        others = np.delete(X, i, axis=1)
        A = np.column_stack([np.ones(len(X)), others])
        coef, *_ = np.linalg.lstsq(A, X[:, i], rcond=None)
        resid = X[:, i] - A @ coef
        ss_tot = ((X[:, i] - X[:, i].mean()) ** 2).sum()
        r2 = 1 - (resid**2).sum() / ss_tot if ss_tot else 0.0
        out[col] = float(1 / (1 - r2)) if r2 < 1 else None
    return out


def disaster_collinearity(
    region_id: str,
    days_back: int = 730,
    resample: str | None = None,
    start: str | None = None,
    end: str | None = None,
) -> dict:
    """Backtest how past weather triggers lined up with actual past disaster spikes, using
    only the data stored in the local model bundle. Targets: Kathmandu — Bagmati GloFAS
    discharge and BIPAD flood incident counts; Mugling — BIPAD landslide incident counts.
    The landslide region defaults to weekly resampling because daily incident counts are
    sparse; monthly ('M') suits multi-year views. `start`/`end` (YYYY-MM-DD, inclusive) select an explicit window, e.g. one month
    or one year; otherwise the trailing `days_back` days are used."""
    if region_id not in _COLLINEARITY_DRIVERS:
        raise ValueError(f"Unknown region {region_id!r}.")
    if resample not in (None, *_RESAMPLE_FREQ):
        raise ValueError("resample must be 'D' (daily), 'W' (weekly) or 'M' (monthly).")
    bundle = _bundle()
    refs = bundle["regions"][region_id]
    frame = refs["frame"]
    drivers = _COLLINEARITY_DRIVERS[region_id]

    data = frame[drivers].copy()
    if region_id == "kathmandu_flood":
        data["discharge_m3s"] = bundle["flood"]["bagmati"]["discharge"]
        data["incidents"] = refs["flood_incident_counts"]
        targets = {"discharge_m3s": "Bagmati discharge (GloFAS, m³/s)", "incidents": "Reported flood incidents (BIPAD)"}
        resample = resample or "D"
    else:
        data["incidents"] = bundle["landslide"]["incident_counts"]
        targets = {"incidents": "Reported landslide incidents (BIPAD)"}
        resample = resample or "W"

    available = {"start": data.index.min().strftime("%Y-%m-%d"), "end": data.index.max().strftime("%Y-%m-%d")}
    if start or end:
        try:
            lo = pd.Timestamp(start) if start else data.index.min()
            hi = pd.Timestamp(end) if end else data.index.max()
        except ValueError as exc:
            raise ValueError("start and end must be dates in YYYY-MM-DD format.") from exc
        data = data[(data.index >= lo) & (data.index <= hi)]
    else:
        data = data[data.index > data.index.max() - pd.Timedelta(days=days_back)]
    if data.empty:
        raise ValueError(f"No data in that window — history covers {available['start']} to {available['end']}.")
    if _RESAMPLE_FREQ[resample]:
        data = data.resample(_RESAMPLE_FREQ[resample]).agg({c: _RESAMPLE_HOW[c] for c in data.columns})

    correlations = [
        {"driver": d, "label": FEATURE_LABELS[d], "target": t, "target_label": targets[t], **_corr(data[d], data[t])}
        for d in drivers
        for t in targets
    ]
    driver_corr = data[drivers].corr()
    return {
        "region": region_id,
        "resample": resample,
        "period": {"start": data.index.min().strftime("%Y-%m-%d"), "end": data.index.max().strftime("%Y-%m-%d")},
        "available": available,
        "trained_at": bundle["trained_at"],
        "drivers": [{"id": d, "label": FEATURE_LABELS[d]} for d in drivers],
        "targets": [{"id": t, "label": label} for t, label in targets.items()],
        "correlations": correlations,
        "driver_correlation_matrix": {
            "labels": drivers,
            # A driver that is constant in the window (e.g. no rain all month) has no defined
            # correlation — sent as null rather than NaN, which isn't valid JSON.
            "matrix": [[None if pd.isna(v) else float(v) for v in row] for row in driver_corr.to_numpy()],
        },
        "vif": _vif(data[drivers]),
        "series": [
            {"date": d.strftime("%Y-%m-%d"), **{c: (None if pd.isna(v) else float(v)) for c, v in row.items()}}
            for d, row in data.iterrows()
        ],
        "assumption": (
            "Correlation is not causation, and BIPAD incident reporting density rises sharply after ~2016 "
            "(reporting bias). Drivers are ERA5 reanalysis at the region's reference point; discharge is the "
            "GloFAS reanalysis/forecast cell for the Bagmati."
        ),
    }
