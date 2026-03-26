"""
Generic Agentic Workflow for Temporal.

This workflow implements a reusable agentic loop:
    1. Wait for user prompt (Signal) or process initial_prompt
    2. Call LLM planner Activity with goal, conversation history, and available tools
    3. LLM returns: "tool_call", "question", or "done"
    4. If tool_call: optionally wait for user confirmation, then execute via dynamic Activity
    5. Append result to conversation_history
    6. ContinueAsNew when history exceeds threshold

The workflow is domain-agnostic. All domain-specific logic lives in:
    - Tools (registered in the tool registry, dispatched via dynamic Activities)
    - The system prompt and goal (passed via AgentConfig)

Based on Temporal's recommended architecture:
    https://docs.temporal.io/ai-cookbook/agentic-loop-tool-call-claude-python
    https://temporal.io/blog/building-an-agentic-system-thats-actually-production-ready
"""

import asyncio
import json
from dataclasses import asdict
from datetime import timedelta
from typing import Optional

from temporalio import workflow
from temporalio.common import RetryPolicy

from .models import (
    AgentConfig,
    AgentContinueState,
    ConversationMessage,
    LLMPlannerInput,
    LLMResponse,
    ToolCall,
    ToolDefinition,
)

# Activity reference for the LLM planner (registered as a named activity)
LLM_RETRY = RetryPolicy(
    initial_interval=timedelta(seconds=2),
    backoff_coefficient=2.0,
    maximum_attempts=3,
)

TOOL_RETRY = RetryPolicy(
    initial_interval=timedelta(seconds=5),
    backoff_coefficient=2.0,
    maximum_attempts=3,
)


@workflow.defn
class AgentWorkflow:
    """
    Generic agentic workflow that orchestrates LLM planning and tool execution.

    Signals:
        user_prompt(prompt: str) — send a new message to the agent
        confirm() — approve a pending tool execution (HITL)
        deny() — reject a pending tool execution (HITL)

    Queries:
        get_conversation_history() — full conversation history
        get_status() — current agent state (waiting, thinking, executing, etc.)
    """

    def __init__(self):
        self._config: Optional[AgentConfig] = None
        self._conversation_history: list[ConversationMessage] = []
        self._iterations: int = 0
        self._cycle_count: int = 0
        self._cycle_summaries: list[str] = []
        self._status: str = "initializing"

        # Signal state
        self._prompt_queue: list[str] = []
        self._confirmed: Optional[bool] = None
        self._current_tool: Optional[str] = None

    # ── Signals ──────────────────────────────

    @workflow.signal
    async def user_prompt(self, prompt: str):
        """Send a new prompt/message to the agent."""
        self._prompt_queue.append(prompt)

    @workflow.signal
    async def confirm(self):
        """Approve a pending tool execution (HITL gate)."""
        self._confirmed = True

    @workflow.signal
    async def deny(self):
        """Reject a pending tool execution (HITL gate)."""
        self._confirmed = False

    # ── Queries ──────────────────────────────

    @workflow.query
    def get_conversation_history(self) -> list[ConversationMessage]:
        """Return the full conversation history."""
        return self._conversation_history

    @workflow.query
    def get_status(self) -> dict:
        """Return the current agent status."""
        return {
            "state": self._status,
            "iterations": self._iterations,
            "cycle_count": self._cycle_count,
            "current_tool": self._current_tool,
            "history_length": len(self._conversation_history),
            "goal": self._config.goal if self._config else "",
            "has_follow_up": bool(self._config.follow_up_prompt) if self._config else False,
            "follow_up_interval_s": self._config.follow_up_interval_seconds if self._config else 0,
        }

    @workflow.query
    def get_cycle_summaries(self) -> list[str]:
        """Return summaries of each completed cycle."""
        return self._cycle_summaries

    # ── Main Workflow Entry Point ────────────

    @workflow.run
    async def run(self, input: AgentContinueState) -> str:
        """
        Main agentic loop.

        Accepts AgentContinueState to support ContinueAsNew with preserved history.
        On first run, pass AgentContinueState(config=your_config).
        """
        self._config = input.config
        self._conversation_history = list(input.conversation_history)
        self._iterations = input.iterations
        self._cycle_count = input.cycle_count
        self._cycle_summaries = list(input.cycle_summaries)

        # Add system prompt to history on first run
        if not self._conversation_history and input.config.system_prompt:
            self._conversation_history.append(
                ConversationMessage(role="system", content=input.config.system_prompt)
            )

        # If there's an initial_prompt (for autonomous agents), enqueue it
        if not input.conversation_history and input.config.initial_prompt:
            self._prompt_queue.append(input.config.initial_prompt)

        # Track whether the initial prompt has been processed
        initial_done = bool(input.conversation_history)

        # ── Outer loop: wait for prompts ──
        while self._iterations < input.config.max_iterations:
            self._status = "waiting_for_prompt"

            # Wait until we have a prompt to process
            await workflow.wait_condition(lambda: len(self._prompt_queue) > 0)

            prompt = self._prompt_queue.pop(0)
            self._conversation_history.append(
                ConversationMessage(role="user", content=prompt)
            )

            # ── Inner loop: agentic tool-calling loop for this prompt ──
            result = await self._agentic_loop()

            if result is not None:
                # Agent said "done" for this prompt — record cycle summary
                self._cycle_count += 1
                summary = f"Cycle {self._cycle_count}: {result[:300]}"
                self._cycle_summaries.append(summary)
                workflow.logger.info(summary)

                if not initial_done:
                    initial_done = True

                # If there's a follow_up_prompt configured, schedule next cycle
                # (cycle 1 is setup; follow-up cycles are 2+)
                max_cycles = input.config.max_cycles
                cycles_remaining = max_cycles == 0 or self._cycle_count < (max_cycles + 1)

                if input.config.follow_up_prompt and cycles_remaining:
                    self._status = "sleeping_between_cycles"
                    await workflow.sleep(
                        timedelta(seconds=input.config.follow_up_interval_seconds)
                    )
                    # Enqueue the follow-up prompt for next cycle
                    self._prompt_queue.append(input.config.follow_up_prompt)
                    continue
                elif input.config.follow_up_prompt and not cycles_remaining:
                    # All cycles completed
                    workflow.logger.info(
                        f"Completed {max_cycles} follow-up cycles. Workflow done."
                    )
                    return result
                else:
                    # No follow-up loop — workflow is truly done
                    return result

            # Use Temporal's built-in heuristic to decide when event history
            # is getting too large and a ContinueAsNew is needed.
            if workflow.info().is_continue_as_new_suggested():
                workflow.logger.info(
                    f"Temporal suggests ContinueAsNew "
                    f"(history: {len(self._conversation_history)} messages, "
                    f"iterations: {self._iterations}). Continuing as new."
                )
                workflow.continue_as_new(
                    AgentContinueState(
                        config=input.config,
                        conversation_history=self._conversation_history,
                        iterations=self._iterations,
                        cycle_count=self._cycle_count,
                        cycle_summaries=self._cycle_summaries,
                    )
                )

        self._status = "max_iterations_reached"
        return f"Agent reached max iterations ({input.config.max_iterations})."

    # ── Agentic Loop ─────────────────────────

    async def _agentic_loop(self) -> Optional[str]:
        """
        Inner agentic loop: repeatedly call LLM → execute tool until
        the LLM returns "question" (needs user input) or "done".
        """
        config = self._config

        while self._iterations < config.max_iterations:
            self._iterations += 1
            self._status = "thinking"

            # Step 1: Call LLM planner
            planner_input = LLMPlannerInput(
                goal=config.goal,
                system_prompt=config.system_prompt,
                conversation_history=self._conversation_history,
                available_tools=config.tools,
                model=config.model,
            )

            llm_response: LLMResponse = await workflow.execute_activity(
                "llm_planner",
                planner_input,
                start_to_close_timeout=timedelta(seconds=120),
                retry_policy=LLM_RETRY,
                result_type=LLMResponse,
            )

            # Step 2: Handle LLM response
            if llm_response.type == "done":
                self._conversation_history.append(
                    ConversationMessage(role="assistant", content=llm_response.content)
                )
                self._status = "done"
                return llm_response.content

            elif llm_response.type == "question":
                self._conversation_history.append(
                    ConversationMessage(role="assistant", content=llm_response.content)
                )
                self._status = "waiting_for_prompt"
                return None  # Break inner loop, wait for next user prompt

            elif llm_response.type in ("tool_calls", "tool_call"):
                await self._handle_tool_calls(llm_response.tool_calls, config)

            else:
                workflow.logger.warning(f"Unknown LLM response type: {llm_response.type}")
                self._conversation_history.append(
                    ConversationMessage(
                        role="system",
                        content=f"Unknown response type '{llm_response.type}'. Retrying.",
                    )
                )

        return None

    # ── Tool Execution ───────────────────────

    async def _handle_tool_calls(self, tool_calls: list[ToolCall], config: AgentConfig):
        """
        Execute one or more tool calls from the LLM.

        When the LLM returns multiple tool_use blocks, they are executed
        in parallel via asyncio.gather for maximum throughput.
        """
        known_tools = {t.name for t in config.tools}
        tool_timeout_map = {t.name: t.timeout_seconds for t in config.tools}

        # Record all assistant tool_call intents first
        tool_names = ", ".join(tc.tool_name for tc in tool_calls)
        workflow.logger.info(f"Executing {len(tool_calls)} tool(s): {tool_names}")

        for tc in tool_calls:
            self._conversation_history.append(
                ConversationMessage(
                    role="assistant",
                    content=f"Calling tool: {tc.tool_name}",
                    tool_name=tc.tool_name,
                    tool_args=tc.tool_args,
                    tool_use_id=tc.tool_use_id,
                )
            )

        # ── HITL Gate ──
        # Check which tools in this batch require confirmation
        confirmation_tools = {t.name for t in config.tools if t.requires_confirmation}
        tools_needing_approval = [
            tc.tool_name for tc in tool_calls if tc.tool_name in confirmation_tools
        ]
        needs_confirmation = config.require_confirmation or len(tools_needing_approval) > 0

        if needs_confirmation:
            display_names = ", ".join(tools_needing_approval) if tools_needing_approval else tool_names
            approved = await self._wait_for_confirmation(display_names)
            if not approved:
                for tc in tool_calls:
                    self._conversation_history.append(
                        ConversationMessage(
                            role="tool_result",
                            content=f"User denied execution of tool '{tc.tool_name}'.",
                            tool_name=tc.tool_name,
                            tool_use_id=tc.tool_use_id,
                        )
                    )
                return

        # ── Execute tools ──
        self._status = "executing_tool"
        self._current_tool = tool_names

        async def _execute_one(tc: ToolCall) -> ConversationMessage:
            """Execute a single tool call, returning a ConversationMessage with the result."""
            if tc.tool_name not in known_tools:
                return ConversationMessage(
                    role="tool_result",
                    content=f"Error: Unknown tool '{tc.tool_name}'. Available: {', '.join(known_tools)}",
                    tool_name=tc.tool_name,
                    tool_use_id=tc.tool_use_id,
                )

            timeout = tool_timeout_map.get(tc.tool_name, 120)

            try:
                # Dynamic dispatch: activity name IS the tool name.
                # TODO [Nexus-readiness]: For cross-namespace tools, this would become:
                #   result = await workflow.execute_nexus_operation(
                #       nexus_endpoint, tc.tool_name, tc.tool_args, ...
                #   )
                # Prefix activity name with "tool_call:" so it's
                # clearly identifiable in the Temporal UI event history.
                result = await workflow.execute_activity(
                    f"tool_call:{tc.tool_name}",
                    tc.tool_args,
                    start_to_close_timeout=timedelta(seconds=timeout),
                    retry_policy=TOOL_RETRY,
                )
                result_str = json.dumps(result, default=str) if not isinstance(result, str) else result
                return ConversationMessage(
                    role="tool_result",
                    content=result_str,
                    tool_name=tc.tool_name,
                    tool_use_id=tc.tool_use_id,
                )
            except Exception as e:
                workflow.logger.error(f"Tool '{tc.tool_name}' failed: {e}")
                return ConversationMessage(
                    role="tool_result",
                    content=f"Error executing tool '{tc.tool_name}': {str(e)}",
                    tool_name=tc.tool_name,
                    tool_use_id=tc.tool_use_id,
                )

        # Execute in parallel when multiple tool calls, sequentially for single
        if len(tool_calls) == 1:
            result_msg = await _execute_one(tool_calls[0])
            self._conversation_history.append(result_msg)
        else:
            # Parallel execution via asyncio.gather
            workflow.logger.info(f"Running {len(tool_calls)} tools in parallel")
            results = await asyncio.gather(
                *[_execute_one(tc) for tc in tool_calls]
            )
            for result_msg in results:
                self._conversation_history.append(result_msg)

        self._current_tool = None

    # ── HITL Confirmation ────────────────────

    async def _wait_for_confirmation(self, tool_name: str) -> bool:
        """Wait for user confirmation before executing a tool."""
        self._status = "waiting_for_confirmation"
        self._current_tool = tool_name
        self._confirmed = None

        try:
            await workflow.wait_condition(
                lambda: self._confirmed is not None,
                timeout=timedelta(hours=4),
            )
        except asyncio.TimeoutError:
            workflow.logger.warning(f"Confirmation timeout for tool '{tool_name}'")
            self._confirmed = None
            return False

        approved = self._confirmed
        self._confirmed = None
        return bool(approved)
