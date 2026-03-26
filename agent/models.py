"""
Generic data models for the Agentic Workflow Framework.

These models are domain-agnostic — they describe the structure of tools,
conversations, and agent configuration without any Pinterest-specific logic.

All models use plain dataclasses for Temporal serialization compatibility.
"""

from dataclasses import dataclass, field
from typing import Any, Optional


# ─────────────────────────────────────────────
# Tool Definition — what the LLM sees
# ─────────────────────────────────────────────


@dataclass
class ToolArgument:
    """Schema for a single tool argument, presented to the LLM."""

    name: str
    type: str  # "string", "number", "boolean", "object", "array"
    description: str
    required: bool = True


@dataclass
class ToolDefinition:
    """
    Declares a tool the LLM can invoke.

    The `name` must match a registered handler in the tool registry.
    The `arguments` schema is sent to the LLM so it knows how to call the tool.
    The `timeout_seconds` allows per-tool timeout configuration for the Activity.

    # TODO [Nexus-readiness]: Each ToolDefinition could map to a Nexus Operation.
    # When tools are exposed as Nexus Operations behind a Nexus Service,
    # the workflow would call workflow.execute_nexus_operation() instead of
    # workflow.execute_activity() for cross-namespace tool invocations.
    """

    name: str
    description: str
    arguments: list[ToolArgument] = field(default_factory=list)
    timeout_seconds: int = 120
    requires_confirmation: bool = False  # Override per-tool HITL


# ─────────────────────────────────────────────
# Conversation History
# ─────────────────────────────────────────────


@dataclass
class ConversationMessage:
    """A single message in the agent's conversation history."""

    role: str  # "user", "assistant", "tool_result", "system"
    content: str
    tool_name: Optional[str] = None
    tool_args: Optional[dict] = None
    tool_use_id: Optional[str] = None  # Claude's tool_use block ID


# ─────────────────────────────────────────────
# LLM Planner Response
# ─────────────────────────────────────────────


@dataclass
class ToolCall:
    """A single tool invocation requested by the LLM."""

    tool_name: str
    tool_args: dict = field(default_factory=dict)
    tool_use_id: str = ""  # Claude's unique ID for this tool_use block


@dataclass
class LLMResponse:
    """
    Structured response from the LLM planner activity.

    The LLM returns one of three types:
    - "tool_calls": invoke one or more tools (executed in parallel when >1)
    - "question": ask the user for more information (breaks the inner loop)
    - "done": the goal has been achieved, return final result
    """

    type: str  # "tool_calls", "question", "done"
    content: str = ""  # Text for question or done
    tool_calls: list[ToolCall] = field(default_factory=list)  # For tool_calls


# ─────────────────────────────────────────────
# Agent Configuration — passed to start the workflow
# ─────────────────────────────────────────────


@dataclass
class AgentConfig:
    """
    Configuration for a generic agent workflow instance.

    This is the single input to AgentWorkflow.run(). It contains everything
    the agent needs: its goal, available tools, system prompt, and guardrails.

    Domain-specific agents (e.g., Pinterest) create an AgentConfig with their
    own tools and prompts, then start the generic AgentWorkflow with it.
    """

    goal: str
    tools: list[ToolDefinition]
    system_prompt: str = ""
    initial_prompt: str = ""  # Auto-sent as first user message (for autonomous agents)
    require_confirmation: bool = False  # Global HITL gate before any tool execution
    max_iterations: int = 50
    model: str = "claude-sonnet-4-20250514"
    # Autonomous loop: after initial_prompt completes, auto-send follow_up_prompt
    # on a recurring schedule. Set to "" to disable.
    follow_up_prompt: str = ""
    follow_up_interval_seconds: int = 21600  # 6 hours default (15s in demo mode)
    max_cycles: int = 5  # Max follow-up cycles (read analytics, eval, act). 0 = unlimited.


# ─────────────────────────────────────────────
# LLM Planner Input — sent to the LLM activity
# ─────────────────────────────────────────────


@dataclass
class LLMPlannerInput:
    """Input to the LLM planner activity."""

    goal: str
    system_prompt: str
    conversation_history: list[ConversationMessage]
    available_tools: list[ToolDefinition]
    model: str = "claude-sonnet-4-20250514"


# ─────────────────────────────────────────────
# Agent State — for ContinueAsNew
# ─────────────────────────────────────────────


@dataclass
class AgentContinueState:
    """State carried across ContinueAsNew boundaries."""

    config: AgentConfig
    conversation_history: list[ConversationMessage] = field(default_factory=list)
    iterations: int = 0
    cycle_count: int = 0
    cycle_summaries: list[str] = field(default_factory=list)
