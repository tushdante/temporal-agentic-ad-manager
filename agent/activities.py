"""
Activities for the Generic Agentic Workflow Framework.

Two activity types:
1. LLMActivities.llm_planner — calls the LLM with conversation history and tool definitions,
   returns a structured LLMResponse (tool_call / question / done).
2. dynamic_tool_activity — dynamic activity that dispatches tool calls by name at runtime.

Retries are handled by Temporal, NOT by the LLM client library.
"""

import inspect
import json
import uuid
from collections.abc import Sequence
from typing import Any

from temporalio import activity
from temporalio.common import RawValue

from .models import (
    ConversationMessage,
    LLMPlannerInput,
    LLMResponse,
    ToolCall,
    ToolDefinition,
)


# ─────────────────────────────────────────────
# LLM Planner Activity
# ─────────────────────────────────────────────


class LLMActivities:
    """
    Activity class that holds the LLM client.

    Instantiated once per worker with the desired model configuration.
    The llm_planner activity is the agent's "brain" — it decides what to do next.
    """

    def __init__(self, default_model: str = "claude-sonnet-4-20250514"):
        self._default_model = default_model

    @activity.defn(name="llm_planner")
    async def llm_planner(self, input: LLMPlannerInput) -> LLMResponse:
        """
        Call Claude with native tool_use API for reliable tool dispatch.

        Uses Claude's built-in tool calling instead of manual JSON parsing,
        which eliminates issues with preamble text or malformed responses.

        Retries are handled by Temporal (set max_retries=0 on the client).
        """
        import anthropic  # Lazy import for sandbox safety

        model = input.model or self._default_model

        system_message = f"""You are an autonomous AI agent working toward a goal.

## Your Goal
{input.goal}

{input.system_prompt if input.system_prompt else ""}

## Rules
- You may call MULTIPLE tools in a single response when they are independent.
  For example, creating 4 pins can be done in parallel. Use this aggressively.
- When tools depend on each other's results, call them sequentially.
- Use tool results to inform your next action.
- If a tool fails, analyze the error and try a different approach.
- Only stop when ALL requested work is fully completed.
- Be thorough — complete every step the user asked for.
- When finishing, include a concise summary of all actions taken and their outcomes."""

        # Build Claude-native tools from ToolDefinitions
        claude_tools = self._build_claude_tools(input.available_tools)

        # Build messages from conversation history
        messages = self._build_messages(input.conversation_history)

        activity.logger.info(
            f"LLM planner: {len(messages)} messages, "
            f"{len(claude_tools)} tools, model={model}"
        )

        # Call Claude with native tool_use — retries handled by Temporal
        client = anthropic.AsyncAnthropic(max_retries=0)
        response = await client.messages.create(
            model=model,
            max_tokens=4096,
            system=system_message,
            messages=messages,
            tools=claude_tools,
        )

        # Parse Claude's native response
        return self._parse_claude_response(response)

    def _build_claude_tools(self, tools: list[ToolDefinition]) -> list[dict]:
        """Convert ToolDefinitions to Claude's native tool format."""
        claude_tools = []
        for tool in tools:
            properties = {}
            required = []
            for arg in tool.arguments:
                prop_type = arg.type
                if prop_type == "array":
                    prop_type = "array"
                    properties[arg.name] = {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": arg.description,
                    }
                elif prop_type == "object":
                    properties[arg.name] = {
                        "type": "object",
                        "description": arg.description,
                    }
                else:
                    properties[arg.name] = {
                        "type": prop_type,
                        "description": arg.description,
                    }
                if arg.required:
                    required.append(arg.name)

            claude_tools.append({
                "name": tool.name,
                "description": tool.description,
                "input_schema": {
                    "type": "object",
                    "properties": properties,
                    "required": required,
                },
            })
        return claude_tools

    def _build_messages(self, history: list[ConversationMessage]) -> list[dict]:
        """
        Convert conversation history to Claude API message format.

        Handles batched tool_use blocks: consecutive assistant tool_call messages
        are merged into a single assistant message with multiple tool_use blocks,
        and their corresponding tool_result messages are merged into a single
        user message with multiple tool_result blocks.
        """
        messages = []
        i = 0
        while i < len(history):
            msg = history[i]

            if msg.role == "system":
                i += 1
                continue

            elif msg.role == "user":
                messages.append({"role": "user", "content": msg.content})

            elif msg.role == "assistant":
                if msg.tool_name and msg.tool_args is not None:
                    # Collect consecutive assistant tool_call messages into one.
                    # Use Claude's tool_use_id when available; generate UUID fallback.
                    # We pair assistant→result by position using batch_ids.
                    tool_use_blocks = []
                    batch_ids = []
                    while i < len(history) and history[i].role == "assistant" and history[i].tool_name:
                        m = history[i]
                        uid = m.tool_use_id if m.tool_use_id else f"toolu_{uuid.uuid4().hex[:24]}"
                        batch_ids.append(uid)
                        tool_use_blocks.append({
                            "type": "tool_use",
                            "id": uid,
                            "name": m.tool_name,
                            "input": m.tool_args or {},
                        })
                        i += 1

                    messages.append({"role": "assistant", "content": tool_use_blocks})

                    # Collect corresponding tool_result messages, pairing by position
                    tool_result_blocks = []
                    result_idx = 0
                    while i < len(history) and history[i].role == "tool_result":
                        m = history[i]
                        # Pair with the matching batch ID by position
                        if result_idx < len(batch_ids):
                            uid = batch_ids[result_idx]
                        else:
                            uid = m.tool_use_id if m.tool_use_id else f"toolu_{uuid.uuid4().hex[:24]}"
                        result_idx += 1
                        tool_result_blocks.append({
                            "type": "tool_result",
                            "tool_use_id": uid,
                            "content": m.content,
                        })
                        i += 1

                    if tool_result_blocks:
                        messages.append({"role": "user", "content": tool_result_blocks})

                    continue  # Skip the i += 1 at the bottom
                else:
                    messages.append({"role": "assistant", "content": msg.content})

            elif msg.role == "tool_result":
                # Standalone tool_result (shouldn't happen but handle gracefully)
                uid = msg.tool_use_id if msg.tool_use_id else f"toolu_{uuid.uuid4().hex[:24]}"
                messages.append({
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": uid,
                            "content": msg.content,
                        }
                    ],
                })

            i += 1

        if not messages:
            messages.append({"role": "user", "content": "Begin working on the goal."})

        # Claude requires first message to be user role
        if messages[0]["role"] != "user":
            messages.insert(0, {"role": "user", "content": "Begin working on the goal."})

        return messages

    def _parse_claude_response(self, response) -> LLMResponse:
        """
        Parse Claude's native API response into an LLMResponse.

        Claude can return multiple tool_use blocks in a single response —
        all are collected into LLMResponse.tool_calls for parallel execution.
        """
        if response.stop_reason == "tool_use":
            tool_calls = []
            for block in response.content:
                if block.type == "tool_use":
                    tool_calls.append(ToolCall(
                        tool_name=block.name,
                        tool_args=block.input if isinstance(block.input, dict) else {},
                        tool_use_id=block.id,
                    ))

            if tool_calls:
                names = ", ".join(tc.tool_name for tc in tool_calls)
                activity.logger.info(
                    f"LLM chose {len(tool_calls)} tool(s): {names}"
                )
                return LLMResponse(type="tool_calls", tool_calls=tool_calls)

        # No tool_use — extract text response
        text_content = ""
        for block in response.content:
            if block.type == "text":
                text_content += block.text

        if response.stop_reason == "end_turn":
            activity.logger.info(f"LLM says done: {text_content[:200]}")
            return LLMResponse(type="done", content=text_content)

        activity.logger.info(f"LLM response (stop_reason={response.stop_reason}): {text_content[:200]}")
        return LLMResponse(type="done", content=text_content)


# ─────────────────────────────────────────────
# Dynamic Tool Activity
# ─────────────────────────────────────────────

# TODO [Nexus-readiness]: When tools are exposed as Nexus Operations,
# this dynamic activity could be replaced (or supplemented) by
# Nexus Operation calls. Each tool would be a Nexus Operation behind
# a Nexus Service, and other teams could contribute tools by deploying
# their own Nexus Services and registering them at a Nexus Endpoint.
# The workflow would call workflow.execute_nexus_operation() for
# cross-namespace tools while still using dynamic activities for
# local tools.


@activity.defn(dynamic=True)
async def dynamic_tool_activity(args: Sequence[RawValue]) -> Any:
    """
    Dynamic activity that dispatches tool calls by name at runtime.

    The tool name comes from activity.info().activity_type (set by the workflow
    when it calls workflow.execute_activity(tool_name, ...)).

    The tool arguments come from the first payload argument.

    The handler is looked up from the tool registry (tools/__init__.py).
    This means changing tools requires NO changes to the agent workflow or this activity.
    """
    from pinterest.tools import get_handler

    raw_activity_type = activity.info().activity_type
    # Strip "tool_call:" prefix used for Temporal UI identification
    tool_name = raw_activity_type.removeprefix("tool_call:")
    tool_args = activity.payload_converter().from_payload(args[0].payload, dict)

    activity.logger.info(f"Dynamic tool dispatch: '{tool_name}' with args: {list(tool_args.keys())}")

    handler = get_handler(tool_name)
    if handler is None:
        raise ValueError(f"No handler registered for tool '{tool_name}'")

    # Clean tool_args: remove non-serializable values and filter to only
    # parameters the handler actually accepts (LLM may pass extras)
    sig = inspect.signature(handler)
    accepted_params = set(sig.parameters.keys())

    clean_args = {}
    for k, v in tool_args.items():
        if k not in accepted_params:
            continue
        if not isinstance(v, (str, int, float, bool, list, dict, type(None))):
            continue
        clean_args[k] = v

    # Execute handler with keyword arguments
    if inspect.iscoroutinefunction(handler):
        result = await handler(**clean_args)
    else:
        result = handler(**clean_args)

    # Ensure result is JSON-serializable by round-tripping through json.dumps/loads.
    # This catches any non-serializable values (functions, methods, etc.) that
    # may have leaked into the result dict.
    try:
        result = json.loads(json.dumps(result, default=str))
    except (TypeError, ValueError) as e:
        activity.logger.warning(f"Tool '{tool_name}' result not serializable, converting: {e}")
        result = {"result": str(result)}

    activity.logger.info(f"Tool '{tool_name}' completed successfully")
    return result
