"""
Interactive Demo — Pinterest Ad Agent on Temporal

Synchronous loop that follows the agent in real-time:
- Shows each new tool call with context (args summary) and result as it happens
- Prompts for HITL approval inline when the agent is waiting for confirmation
- Displays cycle summaries as they complete
- Exits when the workflow completes or max cycles reached

Usage:
    python run_demo.py                                      # Follow default workflow
    python run_demo.py -w pinterest-agent-summer-sale-2026   # Follow specific workflow
    python run_demo.py --poll 5                              # Poll every 5 seconds
"""

import argparse
import asyncio
import json
import os
import sys

from dotenv import load_dotenv

from agent.models import ConversationMessage
from agent.workflow import AgentWorkflow
from worker import create_client

DEFAULT_WORKFLOW_ID = "pinterest-agent-spring-collection-2026"

# ── ANSI Colors ──────────────────────────────

RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
BLUE = "\033[34m"
MAGENTA = "\033[35m"
CYAN = "\033[36m"
RED = "\033[31m"
WHITE = "\033[37m"


def _summarize_tool_args(tool_name: str, tool_args: dict) -> str:
    """Extract a human-readable context line from tool_args for display."""
    if not tool_args:
        return ""

    # Tool-specific summaries
    if tool_name == "create_campaign":
        name = tool_args.get("campaign_name", tool_args.get("name", ""))
        budget = tool_args.get("daily_budget_usd", "")
        obj = tool_args.get("objective", "")
        parts = [p for p in [name, f"${budget}/day" if budget else "", obj] if p]
        return " | ".join(parts)

    elif tool_name == "create_ad_group":
        name = tool_args.get("name", "")
        budget = tool_args.get("daily_budget_usd", "")
        strategy = tool_args.get("bid_strategy", "")
        parts = [p for p in [name, f"${budget}/day" if budget else "", strategy] if p]
        return " | ".join(parts)

    elif tool_name == "create_pin":
        title = tool_args.get("title", "")
        cta = tool_args.get("cta_type", "")
        return f"{title[:60]}{'...' if len(title) > 60 else ''}" + (f" [{cta}]" if cta else "")

    elif tool_name == "create_ad":
        name = tool_args.get("name", "")
        pin = tool_args.get("pin_id", "")
        return f"{name}" + (f" (pin: {pin[:20]})" if pin else "")

    elif tool_name == "pull_analytics":
        campaign = tool_args.get("campaign_id", "")
        cycle = tool_args.get("cycle", "")
        return f"campaign={campaign[:20]} cycle={cycle}"

    elif tool_name == "check_review_status":
        ids = tool_args.get("ad_ids", [])
        return f"{len(ids)} ad(s)"

    elif tool_name == "update_budget":
        new_budget = tool_args.get("new_daily_budget_usd", "")
        campaign = tool_args.get("campaign_id", "")
        return f"${new_budget}/day for {campaign[:20]}" if new_budget else ""

    elif tool_name == "update_ad_status":
        ad_id = tool_args.get("ad_id", "")
        status = tool_args.get("status", "")
        return f"{ad_id[:20]} -> {status}"

    elif tool_name == "update_targeting":
        group = tool_args.get("ad_group_id", "")
        changes = tool_args.get("targeting_changes", {})
        keys = ", ".join(changes.keys()) if isinstance(changes, dict) else str(changes)[:40]
        return f"{group[:20]}: {keys}"

    elif tool_name == "suspend_ad_group":
        group = tool_args.get("ad_group_id", "")
        reason = tool_args.get("reason", "")
        return f"{group[:20]}" + (f" ({reason[:40]})" if reason else "")

    elif tool_name == "adjust_bid_strategy":
        group = tool_args.get("ad_group_id", "")
        strategy = tool_args.get("new_strategy", "")
        return f"{group[:20]} -> {strategy}"

    elif tool_name == "generate_creatives":
        product = tool_args.get("product_description", "")
        n = tool_args.get("num_variants", 4)
        return f"{n} variants for: {product[:40]}..."

    elif tool_name == "send_notification":
        channel = tool_args.get("channel", "")
        message = tool_args.get("message", "")
        return f"[{channel}] {message[:80]}{'...' if len(message) > 80 else ''}"

    # Generic fallback: show first few key=value pairs
    items = []
    for k, v in list(tool_args.items())[:3]:
        v_str = str(v)[:30]
        items.append(f"{k}={v_str}")
    return ", ".join(items)


def print_message(msg: ConversationMessage, indent: str = "  "):
    """Print a single conversation message with formatting."""
    if msg.role == "assistant" and msg.tool_name:
        # Tool call with context
        context = _summarize_tool_args(msg.tool_name, msg.tool_args) if msg.tool_args else ""
        print(f"{indent}{CYAN}{BOLD}[TOOL CALL: {msg.tool_name}]{RESET}")
        if context:
            print(f"{indent}  {DIM}{context}{RESET}")
        print()

    elif msg.role == "assistant":
        # Agent text (done summary, etc.) — show full content
        print(f"{indent}{GREEN}{BOLD}[AGENT]{RESET}")
        content = msg.content
        for line in content.split("\n"):
            print(f"{indent}  {line}")
        print()

    elif msg.role == "tool_result":
        label = f"RESULT: {msg.tool_name}" if msg.tool_name else "RESULT"

        # Parse result for a cleaner display
        content = msg.content
        if content.startswith("Error"):
            print(f"{indent}{RED}{BOLD}[{label}]{RESET}")
            print(f"{indent}  {RED}{content[:200]}{RESET}")
        else:
            print(f"{indent}{MAGENTA}{BOLD}[{label}]{RESET}")
            # Try to parse JSON and show a summary
            try:
                data = json.loads(content)
                summary = _summarize_result(msg.tool_name, data)
                print(f"{indent}  {summary}")
            except (json.JSONDecodeError, TypeError):
                truncated = content[:300] + "..." if len(content) > 300 else content
                print(f"{indent}  {truncated}")
        print()

    elif msg.role == "user":
        print(f"{indent}{BLUE}{BOLD}[USER]{RESET}")
        content = msg.content
        if len(content) > 300:
            content = content[:300] + f" {DIM}...{RESET}"
        for line in content.split("\n")[:10]:
            print(f"{indent}  {line}")
        print()

    elif msg.role == "system":
        print(f"{indent}{DIM}[SYSTEM] {msg.content[:100]}{RESET}\n")


def _summarize_result(tool_name: str, data) -> str:
    """Produce a concise one-liner from a tool result dict."""
    if isinstance(data, list):
        # List result (creatives, review statuses)
        if len(data) > 0 and isinstance(data[0], dict):
            if "review_status" in data[0]:
                items = [f"{d.get('ad_id', '?')[:15]}={d.get('review_status', '?')}" for d in data]
                return ", ".join(items)
            elif "title" in data[0]:
                titles = [d.get("title", "?")[:40] for d in data]
                return f"{len(data)} items: " + " | ".join(titles)
        return f"{len(data)} items returned"

    if not isinstance(data, dict):
        return str(data)[:200]

    if tool_name == "create_campaign":
        return f"campaign_id={data.get('campaign_id', '?')} budget=${data.get('daily_budget_usd', '?')}/day"
    elif tool_name == "create_ad_group":
        return f"ad_group_id={data.get('id', '?')} strategy={data.get('bid_strategy', '?')}"
    elif tool_name == "create_pin":
        return f"pin_id={data.get('pin_id', '?')} [{data.get('cta_type', '')}] {data.get('title', '')[:40]}"
    elif tool_name == "create_ad":
        return f"ad_id={data.get('ad_id', '?')} pin={data.get('pin_id', '?')} status={data.get('status', '?')}"
    elif tool_name == "send_notification":
        return f"sent to {data.get('channel', '?')}"
    elif tool_name == "update_budget":
        return f"budget -> ${data.get('new_daily_budget_usd', '?')}/day"
    elif tool_name == "update_ad_status":
        return f"{data.get('ad_id', '?')} -> {data.get('status', '?')}"
    elif tool_name == "suspend_ad_group":
        return f"{data.get('ad_group_id', '?')} -> SUSPENDED"
    elif tool_name == "adjust_bid_strategy":
        return f"{data.get('ad_group_id', '?')} -> {data.get('new_strategy', '?')}"
    elif "IMPRESSION" in data:
        # Analytics result
        from pinterest.shared import micro_to_usd
        spend = micro_to_usd(data.get("SPEND_IN_MICRO_DOLLAR", 0))
        return (
            f"impressions={data.get('IMPRESSION', 0):,} "
            f"clicks={data.get('PIN_CLICK', 0)} "
            f"saves={data.get('SAVE', 0)} "
            f"spend=${spend:.2f} "
            f"ROAS={data.get('ROAS', 0)}"
        )

    # Generic: show key fields
    items = [f"{k}={str(v)[:25]}" for k, v in list(data.items())[:4]]
    return ", ".join(items)


def print_status_bar(status: dict):
    """Print a compact status bar."""
    state = status.get("state", "unknown")
    cycle = status.get("cycle_count", 0)
    iters = status.get("iterations", 0)
    tool = status.get("current_tool")

    state_color = {
        "thinking": YELLOW,
        "executing_tool": CYAN,
        "waiting_for_confirmation": RED,
        "sleeping_between_cycles": DIM,
        "waiting_for_prompt": BLUE,
        "done": GREEN,
    }.get(state, WHITE)

    parts = [
        f"{BOLD}Cycle {cycle}{RESET}",
        f"Iter {iters}",
        f"{state_color}{state}{RESET}",
    ]
    if tool:
        parts.append(f"{CYAN}{tool}{RESET}")

    print(f"  {DIM}{'─'*56}{RESET}")
    print(f"  {' | '.join(parts)}")
    print(f"  {DIM}{'─'*56}{RESET}")


async def follow_workflow(client, workflow_id: str, poll_interval: float = 3.0):
    """
    Synchronously follow the agent workflow, showing updates as they happen.
    Prompts for HITL approval inline when the agent is waiting.
    """
    handle = client.get_workflow_handle(workflow_id)

    print(f"\n{BOLD}{'='*60}{RESET}")
    print(f"  {BOLD}PINTEREST AD AGENT — LIVE DEMO{RESET}")
    print(f"  Workflow: {workflow_id}")
    print(f"{'='*60}\n")

    seen_messages = 0
    seen_cycles = 0
    last_state = None
    was_sleeping = False

    try:
        while True:
            # ── Query current state ──
            try:
                status = await handle.query(AgentWorkflow.get_status)
                history: list[ConversationMessage] = await handle.query(
                    AgentWorkflow.get_conversation_history
                )
                summaries: list[str] = await handle.query(
                    AgentWorkflow.get_cycle_summaries
                )
            except Exception as e:
                error_str = str(e)
                if "Workflow Task in failed state" in error_str:
                    print(f"\n  {RED}{BOLD}Workflow task failed!{RESET}")
                    print(f"  Check the Temporal UI for details.\n")
                    break
                elif "not found" in error_str.lower():
                    print(f"\n  {RED}Workflow not found: {workflow_id}{RESET}\n")
                    break
                else:
                    await asyncio.sleep(poll_interval)
                    continue

            state = status.get("state", "unknown")

            # ── Print new messages ──
            new_messages = history[seen_messages:]
            if new_messages:
                for msg in new_messages:
                    if msg.role == "system" and seen_messages == 0:
                        print(f"  {DIM}[SYSTEM] System prompt loaded ({len(msg.content)} chars){RESET}\n")
                    else:
                        print_message(msg)
                seen_messages = len(history)

            # ── Print new cycle summaries ──
            new_summaries = summaries[seen_cycles:]
            if new_summaries:
                for s in new_summaries:
                    cycle_num = seen_cycles + 1
                    print(f"  {GREEN}{BOLD}{'='*56}{RESET}")
                    print(f"  {GREEN}{BOLD}CYCLE {cycle_num} COMPLETE{RESET}")
                    # Show the full summary (strip the "Cycle N: " prefix)
                    summary_text = s
                    if summary_text.startswith(f"Cycle {cycle_num}: "):
                        summary_text = summary_text[len(f"Cycle {cycle_num}: "):]
                    for line in summary_text.split("\n"):
                        if line.strip():
                            print(f"  {GREEN}  {line.strip()}{RESET}")
                    print(f"  {GREEN}{BOLD}{'='*56}{RESET}\n")
                    seen_cycles += 1

            # ── Status bar ──
            if state != last_state:
                print_status_bar(status)
                last_state = state

            # ── Sleeping notification ──
            if state == "sleeping_between_cycles" and not was_sleeping:
                interval = status.get("follow_up_interval_s", 0)
                print(f"\n  {DIM}Sleeping {interval}s until next optimization cycle...{RESET}\n")
                was_sleeping = True
            elif state != "sleeping_between_cycles":
                was_sleeping = False

            # ── HITL Prompt ──
            if state == "waiting_for_confirmation":
                tool = status.get("current_tool", "unknown tool")

                # Show the pending tool calls with their context
                print(f"\n  {RED}{BOLD}{'─'*56}{RESET}")
                print(f"  {RED}{BOLD}HUMAN APPROVAL REQUIRED{RESET}")
                print(f"  {RED}{BOLD}{'─'*56}{RESET}")

                # Find the pending tool call messages (most recent assistant messages with tool_name)
                pending = []
                for msg in reversed(history):
                    if msg.role == "assistant" and msg.tool_name:
                        pending.insert(0, msg)
                    elif msg.role != "assistant" or not msg.tool_name:
                        if pending:
                            break

                for msg in pending:
                    context = _summarize_tool_args(msg.tool_name, msg.tool_args) if msg.tool_args else ""
                    print(f"  {CYAN}{BOLD}{msg.tool_name}{RESET}", end="")
                    if context:
                        print(f"  {DIM}{context}{RESET}")
                    else:
                        print()

                print()
                try:
                    response = await asyncio.to_thread(
                        input, f"  Approve? [y/n]: "
                    )
                    response = response.strip().lower()
                    if response in ("y", "yes", ""):
                        await handle.signal(AgentWorkflow.confirm)
                        print(f"  {GREEN}{BOLD}APPROVED{RESET}\n")
                    else:
                        await handle.signal(AgentWorkflow.deny)
                        print(f"  {RED}{BOLD}REJECTED{RESET}\n")
                except EOFError:
                    await handle.signal(AgentWorkflow.confirm)
                    print(f"  {YELLOW}Auto-approved (non-interactive){RESET}\n")

            # ── Check if workflow is done ──
            if state == "done" or state == "max_iterations_reached":
                print(f"\n{BOLD}{'='*60}{RESET}")
                print(f"  {GREEN}{BOLD}WORKFLOW COMPLETE{RESET}")
                print(f"  Cycles: {status.get('cycle_count', 0)} | "
                      f"Iterations: {status.get('iterations', 0)} | "
                      f"Messages: {status.get('history_length', 0)}")
                print(f"{'='*60}\n")
                break

            # ── Check if workflow was terminated ──
            try:
                desc = await handle.describe()
                wf_status = desc.status
                if wf_status and wf_status.name in ("TERMINATED", "CANCELLED", "FAILED", "TIMED_OUT"):
                    print(f"\n  {RED}Workflow {wf_status.name}{RESET}\n")
                    break
            except Exception:
                pass

            await asyncio.sleep(poll_interval)

    except KeyboardInterrupt:
        print(f"\n\n  {YELLOW}Detached from workflow (still running in Temporal){RESET}")
        print(f"  Re-attach: python run_demo.py -w {workflow_id}\n")


async def main():
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    load_dotenv(env_path, override=True)

    parser = argparse.ArgumentParser(
        description="Follow a Pinterest Ad Agent workflow in real-time"
    )
    parser.add_argument(
        "--workflow-id", "-w",
        default=DEFAULT_WORKFLOW_ID,
        help="Workflow ID to follow",
    )
    parser.add_argument(
        "--poll", "-p",
        type=float,
        default=3.0,
        help="Poll interval in seconds (default: 3)",
    )
    args = parser.parse_args()

    client = await create_client()
    await follow_workflow(client, args.workflow_id, args.poll)


if __name__ == "__main__":
    asyncio.run(main())
