"""
Restate Budget Decision Handler — version controlled via env var.

Set ROAS_THRESHOLD env var to control the decision threshold.
Default is 2.0 (v1). Set to 3.0 for v2.

This simulates a real deploy where the same endpoint gets new code.
"""

import os
from datetime import timedelta

import restate
from restate import VirtualObject, ObjectContext

budget_optimizer = VirtualObject("BudgetOptimizer")

ROAS_THRESHOLD = float(os.environ.get("ROAS_THRESHOLD", "2.0"))

SIMULATED_METRICS = [
    {"cycle": 1, "roas": 2.5, "spend": 45.00, "ctr": 0.012},
    {"cycle": 2, "roas": 1.8, "spend": 62.00, "ctr": 0.008},
    {"cycle": 3, "roas": 3.2, "spend": 58.00, "ctr": 0.015},
    {"cycle": 4, "roas": 2.7, "spend": 71.00, "ctr": 0.011},
    {"cycle": 5, "roas": 0.9, "spend": 80.00, "ctr": 0.005},
]


@budget_optimizer.handler()
async def optimize(ctx: ObjectContext, max_cycles: int = 5) -> dict:
    """Run budget optimization. Threshold comes from env at handler startup time."""
    decisions = []
    threshold = ROAS_THRESHOLD  # Captured at import time

    for cycle in range(max_cycles):
        metrics = await ctx.run(
            f"check_metrics_{cycle}",
            lambda c=cycle: SIMULATED_METRICS[min(c, len(SIMULATED_METRICS) - 1)]
        )

        roas = metrics["roas"]

        if roas > threshold:
            result = await ctx.run(
                f"action_{cycle}",
                lambda r=roas, t=threshold: {
                    "action": "budget_increased",
                    "roas": r,
                    "threshold": t,
                }
            )
            decisions.append(f"cycle {cycle + 1}: ROAS={roas} > {threshold} → INCREASED (threshold={threshold})")
        else:
            result = await ctx.run(
                f"action_{cycle}",
                lambda r=roas, t=threshold: {
                    "action": "hold_steady",
                    "roas": r,
                    "threshold": t,
                }
            )
            decisions.append(f"cycle {cycle + 1}: ROAS={roas} <= {threshold} → held steady (threshold={threshold})")

        if cycle < max_cycles - 1:
            await ctx.sleep(delta=timedelta(seconds=10))

    return {"decisions": decisions, "threshold": threshold}


app = restate.app(services=[budget_optimizer])

if __name__ == "__main__":
    import hypercorn.asyncio
    import hypercorn.config

    config = hypercorn.config.Config()
    config.bind = ["0.0.0.0:9080"]
    print(f"Restate handler (threshold={ROAS_THRESHOLD}) listening on :9080")

    import asyncio
    asyncio.run(hypercorn.asyncio.serve(app, config))
