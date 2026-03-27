"""
Restate Budget Decision Handler — version controlled via env var.

Set ROAS_THRESHOLD env var to control the decision threshold.
Default is 2.0 (v1). Set to 3.0 for v2.

This simulates a real deploy where the same endpoint gets new code.
"""

import logging
import os
import sys
from datetime import timedelta

import restate
from restate import VirtualObject, ObjectContext

# Log to stderr so it's always flushed (stdout is buffered by hypercorn)
logging.basicConfig(
    stream=sys.stderr,
    level=logging.INFO,
    format="[%(asctime)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("handler")

budget_optimizer = VirtualObject("BudgetOptimizer")

ROAS_THRESHOLD = float(os.environ.get("ROAS_THRESHOLD", "2.0"))
HANDLER_VERSION = "v1" if ROAS_THRESHOLD <= 2.0 else "v2"

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

    log.info(f"[{HANDLER_VERSION}] Starting optimization: {max_cycles} cycles, threshold={threshold}")

    for cycle in range(max_cycles):
        metrics = await ctx.run(
            f"check_metrics_{cycle}",
            lambda c=cycle: SIMULATED_METRICS[min(c, len(SIMULATED_METRICS) - 1)]
        )

        roas = metrics["roas"]
        log.info(f"[{HANDLER_VERSION}] [CYCLE {cycle + 1}] check_metrics → ROAS={roas}, threshold={threshold}")

        # The ENTIRE decision — threshold check + action — is inside one
        # ctx.run so it gets journaled atomically. On replay, Restate
        # returns the journaled result (which used v1's threshold), making
        # the drift between v1 and v2 visible in the output.
        def make_decision(r=roas, t=threshold, c=cycle):
            if r > t:
                return {
                    "action": "budget_increased",
                    "roas": r,
                    "threshold_used": t,
                    "decision": f"cycle {c + 1}: ROAS={r} > {t} → INCREASED (threshold={t})",
                }
            else:
                return {
                    "action": "hold_steady",
                    "roas": r,
                    "threshold_used": t,
                    "decision": f"cycle {c + 1}: ROAS={r} <= {t} → held steady (threshold={t})",
                }

        result = await ctx.run(f"decide_and_act_{cycle}", make_decision)
        log.info(f"[{HANDLER_VERSION}] [DECIDED] {result['decision']}")
        decisions.append(result["decision"])

        if cycle < max_cycles - 1:
            await ctx.sleep(delta=timedelta(seconds=10))

    return {"decisions": decisions, "threshold_at_completion": threshold}


app = restate.app(services=[budget_optimizer])

if __name__ == "__main__":
    import hypercorn.asyncio
    import hypercorn.config

    config = hypercorn.config.Config()
    config.bind = ["0.0.0.0:9080"]
    log.info(f"[{HANDLER_VERSION}] Restate handler (threshold={ROAS_THRESHOLD}) listening on :9080")

    import asyncio
    asyncio.run(hypercorn.asyncio.serve(app, config))
