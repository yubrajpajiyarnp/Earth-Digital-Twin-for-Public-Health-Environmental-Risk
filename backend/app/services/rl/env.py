import gymnasium as gym
import numpy as np
from gymnasium import spaces

from app.services.simulation.engine import (
    project_ndvi_after_afforestation,
    project_no2_after_traffic_reduction,
)

# Afforestation cost-effectiveness stays a stated illustrative assumption, in ₹ but on a
# toy/illustrative scale (not a real-world per-hectare cost), per 1 percentage point of
# buffer area reforested — there's no real-time price source for tree-sapling/afforestation
# program costs to ground it in (checked Agmarknet; not covered). See CLAUDE.md.
COST_PER_PCT_AFFORESTATION = 3.0

# Traffic-reduction cost-effectiveness DEFAULT, used only as a fallback when no live fuel
# price is available. When it is, the optimizer computes this dynamically instead — see
# app/services/rl/optimizer.py and app/services/pricing/fuel_price.py.
DEFAULT_COST_PER_PCT_TRAFFIC_REDUCTION = 2.0

DEFAULT_BUDGET = 100.0


def _risk_score(z: float, invert: bool = False) -> float:
    """Continuous risk proxy for the RL reward: how far into 'worse than normal'
    territory, clipped at 0 so there's no reward bonus for being unusually good."""
    if invert:
        z = -z
    return max(0.0, z)


class BudgetAllocationEnv(gym.Env):
    """Given a fixed budget, choose how to split it between traffic-reduction and
    afforestation to minimize the resulting NO2- and NDVI-linked risk.

    This is a single-step (contextual-bandit-style) environment, not a multi-step MDP:
    there's no data on how Vellore's risk actually evolves day-to-day under a sustained
    intervention, so modeling multi-step dynamics would mean fabricating a trajectory
    model with nothing to validate it against. One episode = one allocation decision,
    evaluated immediately. Uses a snapshot of NO2/NDVI current + baseline values captured
    at construction time rather than live Earth Engine calls, since a training run takes
    thousands of steps.
    """

    metadata = {"render_modes": []}

    def __init__(
        self,
        no2_current: float,
        no2_baseline_mean: float,
        no2_baseline_std: float,
        ndvi_current: float,
        ndvi_baseline_mean: float,
        ndvi_baseline_std: float,
        budget: float = DEFAULT_BUDGET,
        cost_per_pct_traffic_reduction: float = DEFAULT_COST_PER_PCT_TRAFFIC_REDUCTION,
    ):
        super().__init__()
        self.no2_current = no2_current
        self.no2_baseline_mean = no2_baseline_mean
        self.no2_baseline_std = no2_baseline_std or 1e-12
        self.ndvi_current = ndvi_current
        self.ndvi_baseline_mean = ndvi_baseline_mean
        self.ndvi_baseline_std = ndvi_baseline_std or 1e-9
        self.budget = budget
        self.cost_per_pct_traffic_reduction = cost_per_pct_traffic_reduction

        # action: [traffic_fraction, afforestation_fraction] of the budget, each in
        # [0, 1]; normalized in step() so they never sum above 1.
        self.action_space = spaces.Box(low=0.0, high=1.0, shape=(2,), dtype=np.float32)
        # observation: starting NO2/NDVI z-scores. Fixed per episode here (single
        # snapshot), kept as a real observation rather than a constant so the interface
        # stays correct if this is later extended to vary per city/day.
        self.observation_space = spaces.Box(low=-10.0, high=10.0, shape=(2,), dtype=np.float32)

    def _initial_obs(self) -> np.ndarray:
        z_no2 = (self.no2_current - self.no2_baseline_mean) / self.no2_baseline_std
        z_ndvi = (self.ndvi_current - self.ndvi_baseline_mean) / self.ndvi_baseline_std
        return np.array([z_no2, z_ndvi], dtype=np.float32)

    def reset(self, *, seed=None, options=None):
        super().reset(seed=seed)
        return self._initial_obs(), {}

    def step(self, action: np.ndarray):
        frac = np.clip(action, 0.0, 1.0)
        total = float(frac.sum())
        if total > 1.0:
            frac = frac / total  # never allocate more than the full budget

        traffic_budget = float(frac[0]) * self.budget
        afforest_budget = float(frac[1]) * self.budget

        reduction_pct = min(100.0, traffic_budget / self.cost_per_pct_traffic_reduction)
        area_pct = min(100.0, afforest_budget / COST_PER_PCT_AFFORESTATION)

        no2_projected = project_no2_after_traffic_reduction(self.no2_current, reduction_pct)
        ndvi_projected = project_ndvi_after_afforestation(self.ndvi_current, area_pct)

        z_no2_after = (no2_projected - self.no2_baseline_mean) / self.no2_baseline_std
        z_ndvi_after = (ndvi_projected - self.ndvi_baseline_mean) / self.ndvi_baseline_std

        risk_after = _risk_score(z_no2_after) + _risk_score(z_ndvi_after, invert=True)
        # Risk is clipped at 0 (see _risk_score), so once an intervention drives risk to
        # the floor, further spend yields zero marginal reward and the policy has nothing
        # pushing it to economize. This small budget-efficiency term breaks that tie so
        # the optimizer only recommends spend that actually reduces risk, rather than
        # spending arbitrarily once risk is already at zero.
        budget_spent_frac = (traffic_budget + afforest_budget) / self.budget
        reward = -risk_after - 0.01 * budget_spent_frac

        obs = np.array([z_no2_after, z_ndvi_after], dtype=np.float32)
        info = {
            "reduction_pct": reduction_pct,
            "area_pct": area_pct,
            "traffic_budget": traffic_budget,
            "afforest_budget": afforest_budget,
            "no2_projected": no2_projected,
            "ndvi_projected": ndvi_projected,
            "risk_after": risk_after,
        }
        terminated = True  # single-step episode
        truncated = False
        return obs, reward, terminated, truncated, info
