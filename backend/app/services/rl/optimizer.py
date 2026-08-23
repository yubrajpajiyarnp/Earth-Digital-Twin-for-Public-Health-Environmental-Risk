"""Budget-constrained intervention allocation via PPO (stable-baselines3) over
BudgetAllocationEnv — matches the architecture the abstract and CLAUDE.md specify for this
component.

This is explicitly the abstract's stretch/research-level extension, not part of the core
prototype: it recommends how to split a fixed budget between traffic-reduction and
afforestation to minimize the combined NO2/NDVI-linked risk, using the projection
assumptions documented in simulation/engine.py.

Two real-time price feeds inform the economics (both optional — the optimizer degrades
gracefully to the illustrative defaults if a key isn't configured, see CLAUDE.md):
  - Petrol price scales the traffic-reduction cost coefficient (fuel_price.py). Priority:
    a caller-supplied `manual_fuel_price_inr` wins over the live API (useful since the
    PurePriceIO integration currently needs a second credential not yet configured — see
    CLAUDE.md — and a person typing in today's pump price is at least as trustworthy as
    an API call anyway), which wins over the illustrative default.
  - Live carbon credit price monetizes the CO2 avoided by the chosen allocation
    (carbon_price.py) as an added "estimated_carbon_value_usd" output — a benefit
    estimate, kept separate from the cost math rather than blended into it.

A fresh policy is trained per request rather than persisted, since the "problem" being
optimized (Vellore's current NO2/NDVI baseline, and now the live prices) changes over
time and a stale trained policy would silently go out of date. Given only 2 continuous
action dimensions and a single-step, smooth reward surface, PPO converges in a few
thousand steps — this is a toy-scale RL problem by design, not a production pipeline.
"""

from stable_baselines3 import PPO

from app.core.config import settings
from app.services.cv.ndvi_timeseries import fetch_ndvi_series
from app.services.cv.no2_timeseries import fetch_no2_daily_series
from app.services.pricing.carbon_price import get_carbon_price_usd_per_ton
from app.services.pricing.fuel_price import get_petrol_price_inr_per_litre
from app.services.rl.env import (
    COST_PER_PCT_AFFORESTATION,
    DEFAULT_BUDGET,
    DEFAULT_COST_PER_PCT_TRAFFIC_REDUCTION,
    BudgetAllocationEnv,
)

# Reference petrol price (INR/litre, approx Tamil Nadu) that
# DEFAULT_COST_PER_PCT_TRAFFIC_REDUCTION was illustratively set against. When a live fuel
# price is available, the cost coefficient scales linearly from this reference — i.e.
# "traffic-reduction spend is assumed proportionally more expensive when fuel itself
# costs more." That scaling relationship is itself a stated assumption, layered on top of
# a now-real price input, not a calibrated economic model. See CLAUDE.md.
REFERENCE_PETROL_PRICE_INR_PER_LITRE = 100.0

# Order-of-magnitude estimate, NOT measured: assumes a Vellore-scale urban vehicle fleet
# where a 1-percentage-point cut in traffic avoids roughly 1,000 tons CO2/year. No local
# vehicle-count or emissions-inventory data exists to calibrate this. See CLAUDE.md.
CO2_TONS_PER_PCT_TRAFFIC_REDUCTION = 1000.0


def optimize_budget_allocation(
    budget: float = DEFAULT_BUDGET,
    training_steps: int = 4000,
    no2_days_back: int = 180,
    ndvi_days_back: int = 365,
    manual_fuel_price_inr: float | None = None,
) -> dict:
    if budget <= 0:
        raise ValueError("budget must be positive")
    if manual_fuel_price_inr is not None and manual_fuel_price_inr <= 0:
        raise ValueError("manual_fuel_price_inr must be positive")

    no2_history = fetch_no2_daily_series(days_back=no2_days_back)
    ndvi_history = fetch_ndvi_series(days_back=ndvi_days_back)

    fuel_price_inr = None
    fuel_price_error = None
    fuel_price_source = None
    if manual_fuel_price_inr is not None:
        fuel_price_inr = manual_fuel_price_inr
        fuel_price_source = "manual entry"
    else:
        try:
            fuel_price_inr = get_petrol_price_inr_per_litre()
            fuel_price_source = "PurePriceIO"
        except RuntimeError as exc:
            fuel_price_error = str(exc)

    if fuel_price_inr is not None:
        cost_per_pct_traffic_reduction = DEFAULT_COST_PER_PCT_TRAFFIC_REDUCTION * (
            fuel_price_inr / REFERENCE_PETROL_PRICE_INR_PER_LITRE
        )
    else:
        cost_per_pct_traffic_reduction = DEFAULT_COST_PER_PCT_TRAFFIC_REDUCTION

    env = BudgetAllocationEnv(
        no2_current=float(no2_history.iloc[-1]),
        no2_baseline_mean=float(no2_history.mean()),
        no2_baseline_std=float(no2_history.std()),
        ndvi_current=float(ndvi_history.iloc[-1]),
        ndvi_baseline_mean=float(ndvi_history.mean()),
        ndvi_baseline_std=float(ndvi_history.std()),
        budget=budget,
        cost_per_pct_traffic_reduction=cost_per_pct_traffic_reduction,
    )

    model = PPO("MlpPolicy", env, verbose=0, seed=0)
    model.learn(total_timesteps=training_steps)

    obs, _ = env.reset()
    action, _ = model.predict(obs, deterministic=True)
    _, _reward, _, _, info = env.step(action)

    carbon_price_usd = None
    carbon_price_error = None
    estimated_carbon_value_usd = None
    try:
        carbon_price_usd = get_carbon_price_usd_per_ton()
        co2_tons_avoided = info["reduction_pct"] * CO2_TONS_PER_PCT_TRAFFIC_REDUCTION
        estimated_carbon_value_usd = co2_tons_avoided * carbon_price_usd
    except RuntimeError as exc:
        carbon_price_error = str(exc)

    return {
        "city": settings.pilot_city,
        "budget": budget,
        "training_steps": training_steps,
        "pricing": {
            "fuel_price_inr_per_litre": fuel_price_inr,
            "fuel_price_source": fuel_price_source,
            "fuel_price_error": fuel_price_error,
            "carbon_price_usd_per_ton": carbon_price_usd,
            "carbon_price_source": "Carbonmark (sandbox)" if carbon_price_usd is not None else None,
            "carbon_price_error": carbon_price_error,
        },
        "assumptions": {
            "cost_per_pct_traffic_reduction": cost_per_pct_traffic_reduction,
            "cost_per_pct_traffic_reduction_is_live": fuel_price_inr is not None,
            "cost_per_pct_afforestation": COST_PER_PCT_AFFORESTATION,
            "co2_tons_per_pct_traffic_reduction": CO2_TONS_PER_PCT_TRAFFIC_REDUCTION,
            "note": (
                "Budget and allocation amounts are in ₹ but on an illustrative, toy scale — "
                "not a real-world program budget. Afforestation cost and the "
                "CO2-tons-per-%-reduction figure are stated illustrative assumptions (no "
                "local costing/emissions data exists to calibrate them). Traffic-reduction "
                "cost scales with a fuel price you enter manually if provided, else a live "
                "API price if configured, else falls back to the illustrative default; "
                "carbon value uses a live market price when CARBON_PRICE_API_KEY is set. "
                "See CLAUDE.md."
            ),
        },
        "recommended_allocation": {
            "traffic_reduction_budget": info["traffic_budget"],
            "traffic_reduction_pct": info["reduction_pct"],
            "afforestation_budget": info["afforest_budget"],
            "afforestation_area_pct": info["area_pct"],
        },
        "projected_no2": info["no2_projected"],
        "projected_ndvi": info["ndvi_projected"],
        "projected_risk_score": info["risk_after"],
        "estimated_carbon_value_usd": estimated_carbon_value_usd,
    }
