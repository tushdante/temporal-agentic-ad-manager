"""
Starter — Launch a Pinterest Ad Agent workflow on Temporal.

This file is small — just configuration, no orchestration logic.
All orchestration lives in the generic AgentWorkflow.

Usage:
    python starter.py
    python starter.py --campaign "Summer Sale 2026" --budget 100
"""

import argparse
import asyncio
import os
from datetime import timedelta

from dotenv import load_dotenv

from agent.workflow import AgentWorkflow
from pinterest.config import create_pinterest_agent_config
from worker import create_client


async def main():
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    load_dotenv(env_path, override=True)

    parser = argparse.ArgumentParser(description="Start a Pinterest Ad Agent workflow")
    parser.add_argument("--campaign", default="Spring Collection 2026", help="Campaign name")
    parser.add_argument("--budget", type=float, default=75.0, help="Initial daily budget (USD)")
    parser.add_argument("--max-budget", type=float, default=300.0, help="Max daily budget (USD)")
    parser.add_argument("--ad-account", default="demo_ad_account_001", help="Pinterest Ad Account ID")
    parser.add_argument("--cycles", type=int, default=5, help="Number of optimization cycles (default: 5, 0=unlimited)")
    args = parser.parse_args()

    # Create Pinterest agent configuration — this is the ONLY Pinterest-specific part
    agent_state = create_pinterest_agent_config(
        campaign_name=args.campaign,
        product_description=(
            "EcoWear Spring Collection — organic cotton dresses and tops, "
            "$45-$120 range. Free shipping over $75. New arrivals weekly."
        ),
        target_audience=(
            "Women 25-44 in the US interested in sustainable fashion, "
            "minimalist home decor, and spring outfit planning. "
            "High household income, active Pinterest users who save fashion pins."
        ),
        destination_url="https://ecowear.example.com/spring-2026",
        ad_account_id=args.ad_account,
        daily_budget_usd=args.budget,
        max_budget_usd=args.max_budget,
        objective="WEB_CONVERSIONS",
        demo_mode=os.environ.get("DEMO_MODE", "false").lower() == "true",
        max_cycles=args.cycles,
    )

    workflow_id = f"pinterest-agent-{args.campaign.lower().replace(' ', '-')}"

    print("Connecting to Temporal...")
    client = await create_client()

    print("Starting Pinterest Ad Agent workflow (generic agentic framework)...")
    print(f"  Workflow ID: {workflow_id}")
    print(f"  Campaign:    {args.campaign}")
    print(f"  Budget:      ${args.budget}/day (max ${args.max_budget})")
    print(f"  Ad Account:  {args.ad_account}")
    print(f"  Tools:       {len(agent_state.config.tools)} registered")
    print()

    handle = await client.start_workflow(
        AgentWorkflow.run,
        agent_state,
        id=workflow_id,
        task_queue="pinterest-ad-agents",
        execution_timeout=timedelta(days=90),
    )

    print(f"Workflow started: {handle.id}")
    print("View in Temporal UI or use run_demo.py to interact.")


if __name__ == "__main__":
    asyncio.run(main())
