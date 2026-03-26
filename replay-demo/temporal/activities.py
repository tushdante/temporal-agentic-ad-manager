"""
Activities for the budget decision workflow.

These simulate checking campaign metrics and taking budget actions.
The metrics are deterministic per cycle so the replay demo is reproducible.
"""

from dataclasses import dataclass
from temporalio import activity


# Simulated metrics per cycle — ROAS deliberately sits between v1 and v2 thresholds
SIMULATED_METRICS = [
    {"cycle": 1, "roas": 2.5, "spend": 45.00, "ctr": 0.012},  # ROAS 2.5: triggers v1 (>2.0), NOT v2 (>3.0)
    {"cycle": 2, "roas": 1.8, "spend": 62.00, "ctr": 0.008},  # Below both thresholds
    {"cycle": 3, "roas": 3.2, "spend": 58.00, "ctr": 0.015},  # Above both thresholds
    {"cycle": 4, "roas": 2.7, "spend": 71.00, "ctr": 0.011},  # Triggers v1, NOT v2
    {"cycle": 5, "roas": 0.9, "spend": 80.00, "ctr": 0.005},  # Below both thresholds
]


@activity.defn
async def check_metrics(campaign_id: str, cycle: int) -> dict:
    """Pull campaign metrics. Returns deterministic data per cycle."""
    idx = min(cycle, len(SIMULATED_METRICS) - 1)
    metrics = SIMULATED_METRICS[idx]
    activity.logger.info(
        f"[check_metrics] cycle={cycle} campaign={campaign_id} "
        f"roas={metrics['roas']} spend=${metrics['spend']}"
    )
    return metrics


@activity.defn
async def increase_budget(campaign_id: str, current_roas: float) -> dict:
    """Increase the daily budget. This is the action that diverges between v1/v2."""
    activity.logger.info(
        f"[increase_budget] campaign={campaign_id} roas={current_roas} — BUDGET INCREASED"
    )
    return {"action": "budget_increased", "campaign_id": campaign_id, "roas": current_roas}


@activity.defn
async def hold_steady(campaign_id: str, current_roas: float) -> dict:
    """Keep budget unchanged."""
    activity.logger.info(
        f"[hold_steady] campaign={campaign_id} roas={current_roas} — no change"
    )
    return {"action": "hold_steady", "campaign_id": campaign_id, "roas": current_roas}
