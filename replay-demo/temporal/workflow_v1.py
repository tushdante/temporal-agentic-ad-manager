"""
Budget Decision Workflow — VERSION 1

Decision rule: if ROAS > 2.0 → increase budget

This is the "original" version deployed when the workflow starts.
After cycle 1 completes (ROAS=2.5 triggers increase_budget),
swapping to v2 (threshold=3.0) causes a NonDeterminismError on replay
because v2 would NOT have called increase_budget at ROAS=2.5.
"""

from dataclasses import dataclass
from datetime import timedelta

from temporalio import workflow

with workflow.unsafe.imports_passed_through():
    from activities import check_metrics, increase_budget, hold_steady


ROAS_THRESHOLD = 2.0  # v1 threshold — the line that changes


@dataclass
class BudgetWorkflowInput:
    campaign_id: str
    max_cycles: int = 5


@workflow.defn
class BudgetDecisionWorkflow:
    """Simple campaign budget optimizer with a hard-coded ROAS threshold.

    v1: increase budget when ROAS > 2.0
    v2: increase budget when ROAS > 3.0

    The workflow sleeps between cycles. When a worker restarts with v2 code,
    Temporal replays the event history and detects that v1 called
    increase_budget at ROAS=2.5 but v2 would not have — NonDeterminismError.
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

            # Step 2: Make decision based on ROAS threshold
            # ╔══════════════════════════════════════════════╗
            # ║  THIS IS THE LINE THAT DIVERGES IN V2       ║
            # ║  v1: ROAS_THRESHOLD = 2.0                   ║
            # ║  v2: ROAS_THRESHOLD = 3.0                   ║
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

            # Step 3: Wait before next cycle (this is where the worker swap happens)
            if cycle < input.max_cycles - 1:
                await workflow.sleep(timedelta(seconds=10))

        return {"decisions": decisions, "version": "v1", "threshold": ROAS_THRESHOLD}
