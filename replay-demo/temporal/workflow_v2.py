"""
Budget Decision Workflow — VERSION 2

Decision rule: if ROAS > 3.0 → increase budget

This is the "updated" version that gets deployed mid-flight.
The threshold changed from 2.0 to 3.0. When Temporal replays cycle 1
(where ROAS=2.5 triggered increase_budget under v1), this code would
NOT call increase_budget — causing a NonDeterminismError.

This is exactly the protection Temporal provides: it catches the drift
instead of silently mixing v1 and v2 decisions in the same execution.
"""

from dataclasses import dataclass
from datetime import timedelta

from temporalio import workflow

with workflow.unsafe.imports_passed_through():
    from activities import check_metrics, increase_budget, hold_steady


ROAS_THRESHOLD = 3.0  # v2 threshold — CHANGED from 2.0


@dataclass
class BudgetWorkflowInput:
    campaign_id: str
    max_cycles: int = 5


@workflow.defn
class BudgetDecisionWorkflow:
    """Same workflow class name, different threshold.

    Temporal replays the event history through this code. Since cycle 1 called
    increase_budget (ROAS=2.5 > 2.0 in v1) but this code would call hold_steady
    (ROAS=2.5 < 3.0 in v2), replay produces a different activity schedule.
    Temporal detects this and raises NonDeterminismError.
    """

    @workflow.run
    async def run(self, input: BudgetWorkflowInput) -> dict:
        decisions = []

        for cycle in range(input.max_cycles):
            workflow.logger.info(f"=== Cycle {cycle + 1}/{input.max_cycles} ===")

            # Step 1: Check metrics
            metrics = await workflow.execute_activity(
                check_metrics,
                args=[input.campaign_id, cycle],
                start_to_close_timeout=timedelta(seconds=30),
            )

            roas = metrics["roas"]

            # Step 2: Make decision — threshold is now 3.0
            # ╔══════════════════════════════════════════════╗
            # ║  CHANGED: was > 2.0, now > 3.0              ║
            # ║  ROAS=2.5 triggered increase_budget in v1   ║
            # ║  ROAS=2.5 triggers hold_steady in v2        ║
            # ║  Temporal catches this mismatch on replay    ║
            # ╚══════════════════════════════════════════════╝
            if roas > ROAS_THRESHOLD:
                result = await workflow.execute_activity(
                    increase_budget,
                    args=[input.campaign_id, roas],
                    start_to_close_timeout=timedelta(seconds=30),
                )
                decisions.append(f"cycle {cycle + 1}: ROAS={roas} > {ROAS_THRESHOLD} → INCREASED budget")
            else:
                result = await workflow.execute_activity(
                    hold_steady,
                    args=[input.campaign_id, roas],
                    start_to_close_timeout=timedelta(seconds=30),
                )
                decisions.append(f"cycle {cycle + 1}: ROAS={roas} <= {ROAS_THRESHOLD} → held steady")

            workflow.logger.info(decisions[-1])

            if cycle < input.max_cycles - 1:
                await workflow.sleep(timedelta(seconds=10))

        return {"decisions": decisions, "version": "v2", "threshold": ROAS_THRESHOLD}
