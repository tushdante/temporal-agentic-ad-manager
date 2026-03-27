"""
Worker for the budget decision replay demo.

Usage:
    python worker.py v1     # Start with v1 workflow (threshold=2.0)
    python worker.py v2     # Start with v2 workflow (threshold=3.0)
"""

import asyncio
import os
import sys

from dotenv import load_dotenv
from temporalio.client import Client
from temporalio.worker import Worker

from activities import check_metrics, increase_budget, hold_steady

TASK_QUEUE = "replay-demo"


async def create_client() -> Client:
    """Connect to Temporal Cloud (API key) or local dev server (no auth)."""
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

    version = sys.argv[1] if len(sys.argv) > 1 else "v1"

    if version == "v2":
        from workflow_v2 import BudgetDecisionWorkflow
        print("Loading workflow VERSION 2 (threshold=3.0)")
    else:
        from workflow_v1 import BudgetDecisionWorkflow
        print("Loading workflow VERSION 1 (threshold=2.0)")

    client = await create_client()
    print(f"Connected to {os.environ['TEMPORAL_ADDRESS']}")
    print(f"Task queue: {TASK_QUEUE}")
    print("Worker ready.\n")

    worker = Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[BudgetDecisionWorkflow],
        activities=[check_metrics, increase_budget, hold_steady],
    )
    await worker.run()


if __name__ == "__main__":
    asyncio.run(main())
