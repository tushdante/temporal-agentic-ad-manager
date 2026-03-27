"""
Start the budget decision workflow and query its state.

Usage:
    python starter.py                    # Start new workflow
    python starter.py --query            # Query running workflow
    python starter.py --workflow-id X    # Use specific workflow ID
"""

import argparse
import asyncio
import os

from dotenv import load_dotenv
from temporalio.client import Client

from workflow_v1 import BudgetDecisionWorkflow, BudgetWorkflowInput

TASK_QUEUE = "replay-demo"
DEFAULT_WORKFLOW_ID = "replay-demo-budget-decision"


async def create_client() -> Client:
    address = os.environ.get("TEMPORAL_ADDRESS", "localhost:7233")
    namespace = os.environ.get("TEMPORAL_NAMESPACE", "default")
    api_key = os.environ.get("TEMPORAL_API_KEY")
    if api_key:
        return await Client.connect(
            address,
            namespace=namespace,
            rpc_metadata={"temporal-namespace": namespace},
            api_key=api_key,
            tls=True,
        )
    else:
        return await Client.connect(
            address,
            namespace=namespace,
        )


async def main():
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "../../.env")
    load_dotenv(env_path, override=True)

    parser = argparse.ArgumentParser()
    parser.add_argument("--workflow-id", "-w", default=DEFAULT_WORKFLOW_ID)
    parser.add_argument("--query", action="store_true", help="Query existing workflow")
    parser.add_argument("--cycles", type=int, default=5)
    args = parser.parse_args()

    client = await create_client()

    if args.query:
        handle = client.get_workflow_handle(args.workflow_id)
        try:
            result = await handle.result()
            print(f"Workflow completed: {result}")
        except Exception as e:
            desc = await handle.describe()
            print(f"Workflow status: {desc.status}")
            print(f"Error: {e}")
        return

    print(f"Starting budget decision workflow...")
    print(f"  Workflow ID: {args.workflow_id}")
    print(f"  Cycles: {args.cycles}")
    print()

    handle = await client.start_workflow(
        BudgetDecisionWorkflow.run,
        BudgetWorkflowInput(
            campaign_id="demo-campaign-001",
            max_cycles=args.cycles,
        ),
        id=args.workflow_id,
        task_queue=TASK_QUEUE,
    )

    print(f"Workflow started: {args.workflow_id}")
    print(f"  View in Temporal UI")
    print()
    print("Now watching for result...")
    print("(Kill the v1 worker and start the v2 worker while this runs)")
    print()

    try:
        result = await handle.result()
        print(f"\nWorkflow completed successfully:")
        for d in result.get("decisions", []):
            print(f"  {d}")
        print(f"  version: {result.get('version')}, threshold: {result.get('threshold')}")
    except Exception as e:
        print(f"\nWorkflow failed: {e}")
        print("\n  ^ This is the NonDeterminismError — Temporal caught the drift!")


if __name__ == "__main__":
    asyncio.run(main())
