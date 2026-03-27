"""
Restate Budget Decision Handler — VERSION 2

Decision rule: if ROAS > 3.0 → increase budget (CHANGED from 2.0)

When this replaces v1 mid-execution:
- Cycle 1 results are already in the journal (increase_budget at ROAS=2.5)
- Restate replays those journal entries as-is — no re-evaluation
- Cycle 2+ runs under v2 logic (threshold=3.0)
- Result: cycle 1 used v1 rules, cycle 2+ uses v2 rules — MIXED DECISIONS

No error. No warning. No drift detection. The execution completes "successfully"
with decisions made under two different rule sets.
"""

import restate
from restate import VirtualObject, ObjectContext

budget_optimizer = VirtualObject("BudgetOptimizer")

ROAS_THRESHOLD = 3.0  # v2 threshold — CHANGED from 2.0

SIMULATED_METRICS = [
    {"cycle": 1, "roas": 2.5, "spend": 45.00, "ctr": 0.012},
    {"cycle": 2, "roas": 1.8, "spend": 62.00, "ctr": 0.008},
    {"cycle": 3, "roas": 3.2, "spend": 58.00, "ctr": 0.015},
    {"cycle": 4, "roas": 2.7, "spend": 71.00, "ctr": 0.011},
    {"cycle": 5, "roas": 0.9, "spend": 80.00, "ctr": 0.005},
]


@budget_optimizer.handler()
async def optimize(ctx: ObjectContext, max_cycles: int = 5) -> dict:
    """Same handler, different threshold.

    Restate replays journaled results for completed steps, then runs
    new steps under v2 logic. No divergence check between old journal
    entries and what current code would have produced.
    """
    decisions = []

    for cycle in range(max_cycles):
        metrics = await ctx.run(
            f"check_metrics_{cycle}",
            lambda: SIMULATED_METRICS[min(cycle, len(SIMULATED_METRICS) - 1)]
        )

        roas = metrics["roas"]

        # CHANGED threshold — but Restate won't catch the inconsistency
        # for cycles that already ran under v1
        if roas > ROAS_THRESHOLD:
            result = await ctx.run(
                f"increase_budget_{cycle}",
                lambda: {
                    "action": "budget_increased",
                    "roas": roas,
                    "threshold_used": ROAS_THRESHOLD,
                    "version": "v2",
                }
            )
            decisions.append(
                f"cycle {cycle + 1}: ROAS={roas} > {ROAS_THRESHOLD} "
                f"→ INCREASED budget (v2 logic)"
            )
        else:
            result = await ctx.run(
                f"hold_steady_{cycle}",
                lambda: {
                    "action": "hold_steady",
                    "roas": roas,
                    "threshold_used": ROAS_THRESHOLD,
                    "version": "v2",
                }
            )
            decisions.append(
                f"cycle {cycle + 1}: ROAS={roas} <= {ROAS_THRESHOLD} "
                f"→ held steady (v2 logic)"
            )

        from datetime import timedelta
        await ctx.sleep(delta=timedelta(seconds=10))

    return {"decisions": decisions, "version": "v2", "threshold": ROAS_THRESHOLD}


app = restate.app(services=[budget_optimizer])

if __name__ == "__main__":
    import sys
    import hypercorn.asyncio
    import hypercorn.config

    port = sys.argv[1] if len(sys.argv) > 1 else "9081"
    config = hypercorn.config.Config()
    config.bind = [f"0.0.0.0:{port}"]
    print(f"Restate handler v2 (threshold={ROAS_THRESHOLD}) listening on :{port}")

    import asyncio
    asyncio.run(hypercorn.asyncio.serve(app, config))
