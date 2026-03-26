"""
Generic Agentic Workflow Framework for Temporal.

This package provides a reusable agentic loop that can be configured with
any set of tools, goals, and system prompts. The workflow itself contains
NO domain-specific logic — all domain knowledge lives in tools and prompts.

Architecture:
    - AgentWorkflow: Generic Temporal workflow implementing the agentic loop
    - LLMActivities: Activity class for calling the LLM planner
    - dynamic_tool_activity: Dynamic activity for dispatching tool calls at runtime
    - ToolDefinition: Schema for declaring tools the LLM can invoke
    - AgentConfig: Configuration dataclass passed to start the workflow

Based on Temporal's recommended agentic architecture:
    https://docs.temporal.io/ai-cookbook/agentic-loop-tool-call-claude-python
"""

from .models import (
    AgentConfig,
    ConversationMessage,
    LLMResponse,
    ToolArgument,
    ToolCall,
    ToolDefinition,
)
from .workflow import AgentWorkflow

__all__ = [
    "AgentConfig",
    "AgentWorkflow",
    "ConversationMessage",
    "LLMResponse",
    "ToolArgument",
    "ToolCall",
    "ToolDefinition",
]
