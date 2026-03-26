"""
Temporal Worker — Generic Agentic Framework + Pinterest Tools

Registers the generic AgentWorkflow, the LLM planner activity, and the
dynamic tool activity (which dispatches to the Pinterest tool registry).

Requires environment variables (see .env.example).
"""

import asyncio
import os

from dotenv import load_dotenv
from temporalio.client import Client
from temporalio.worker import Worker

from agent.activities import LLMActivities, dynamic_tool_activity
from agent.workflow import AgentWorkflow

TASK_QUEUE = "pinterest-ad-agents"


async def create_client() -> Client:
    """Connect to Temporal Cloud using API key authentication."""
    address = os.environ["TEMPORAL_ADDRESS"]
    namespace = os.environ["TEMPORAL_NAMESPACE"]
    api_key = os.environ["TEMPORAL_API_KEY"]

    return await Client.connect(
        address,
        namespace=namespace,
        rpc_metadata={"temporal-namespace": namespace},
        api_key=api_key,
        tls=True,
    )


async def main():
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    load_dotenv(env_path, override=True)

    print(f"Connecting to Temporal at {os.environ.get('TEMPORAL_ADDRESS', 'NOT SET')}...")
    client = await create_client()
    print(f"Connected to namespace: {os.environ.get('TEMPORAL_NAMESPACE', 'default')}")

    # Instantiate the LLM activities class (holds client configuration)
    llm_activities = LLMActivities()

    print(f"Starting worker on task queue: {TASK_QUEUE}")
    print(f"Registered: AgentWorkflow + LLM planner + dynamic tool dispatcher")
    print("Worker ready. Waiting for tasks...\n")

    worker = Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[AgentWorkflow],
        activities=[
            llm_activities.llm_planner,  # Named activity for LLM planning
            dynamic_tool_activity,       # Dynamic activity for tool dispatch
        ],
    )
    await worker.run()


if __name__ == "__main__":
    asyncio.run(main())
