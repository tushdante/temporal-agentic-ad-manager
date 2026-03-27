"""
Restate Budget Decision Handler — VERSION 1

Decision rule: if ROAS > 2.0 → increase budget

This is the Restate equivalent of the Temporal workflow. It uses Restate's
virtual object pattern with journaled side effects.

When the service restarts with v2 code:
- Restate replays the JOURNAL (recorded results), not the code
- Old decisions (increase_budget at ROAS=2.5) are replayed from the journal
- New decisions use v2 logic (threshold=3.0)
- Result: mixed v1/v2 decisions in the same execution — SILENT DRIFT

Key difference from Temporal:
- Temporal replays the CODE through the event history → detects divergence
- Restate replays the JOURNAL results → code changes go unnoticed for past steps
"""

import restate
from restate import VirtualObject, ObjectContext

budget_optimizer = VirtualObject("BudgetOptimizer")

ROAS_THRESHOLD = 2.0  # v1 threshold

# Same simulated metrics as Temporal side
SIMULATED_METRICS = [
    {"cycle": 1, "roas": 2.5, "spend": 45.00, "ctr": 0.012},
    {"cycle": 2, "roas": 1.8, "spend": 62.00, "ctr": 0.008},
    {"cycle": 3, "roas": 3.2, "spend": 58.00, "ctr": 0.015},
    {"cycle": 4, "roas": 2.7, "spend": 71.00, "ctr": 0.011},
    {"cycle": 5, "roas": 0.9, "spend": 80.00, "ctr": 0.005},
]


@budget_optimizer.handler()
async def optimize(ctx: ObjectContext, max_cycles: int = 5) -> dict:
    """Run the budget optimization loop.

    Each ctx.run() call is journaled. On replay after restart,
    Restate returns the journaled result WITHOUT re-executing the code.
    The decision logic inside ctx.run() is NOT re-evaluated.
    """
    decisions = []

    for cycle in range(max_cycles):
        # Side effect 1: "check metrics" — journaled
        metrics = await ctx.run(
            f"check_metrics_{cycle}",
            lambda: SIMULATED_METRICS[min(cycle, len(SIMULATED_METRICS) - 1)]
        )

        roas = metrics["roas"]

        # Decision logic — THIS IS WHERE DRIFT HAPPENS
        # When v2 code runs, this threshold changes to 3.0
        # But the JOURNAL already recorded the result of the action below
        # So Restate replays the old result without checking if the decision
        # would have been different under new code
        if roas > ROAS_THRESHOLD:
            result = await ctx.run(
                f"increase_budget_{cycle}",
                lambda: {
                    "action": "budget_increased",
                    "roas": roas,
                    "threshold_used": ROAS_THRESHOLD,
                    "version": "v1",
                }
            )
            decisions.append(
                f"cycle {cycle + 1}: ROAS={roas} > {ROAS_THRESHOLD} "
                f"→ INCREASED budget (v1 logic)"
            )
        else:
            result = await ctx.run(
                f"hold_steady_{cycle}",
                lambda: {
                    "action": "hold_steady",
                    "roas": roas,
                    "threshold_used": ROAS_THRESHOLD,
                    "version": "v1",
                }
            )
            decisions.append(
                f"cycle {cycle + 1}: ROAS={roas} <= {ROAS_THRESHOLD} "
                f"→ held steady (v1 logic)"
            )

        # Sleep between cycles — this is where the restart/swap happens
        from datetime import timedelta
        await ctx.sleep(delta=timedelta(seconds=10))

    return {"decisions": decisions, "version": "v1", "threshold": ROAS_THRESHOLD}


app = restate.app(services=[budget_optimizer])

if __name__ == "__main__":
    import hypercorn.asyncio
    import hypercorn.config

    config = hypercorn.config.Config()
    config.bind = ["0.0.0.0:9080"]
    print(f"Restate handler v1 (threshold={ROAS_THRESHOLD}) listening on :9080")

    import asyncio
    asyncio.run(hypercorn.asyncio.serve(app, config))
