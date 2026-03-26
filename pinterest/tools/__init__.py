"""
Pinterest Tool Registry.

Maps tool names to handler functions. The dynamic_tool_activity looks up
handlers here at runtime via get_handler(tool_name).

To add a new tool:
1. Create a new file in tools/ with a ToolDefinition and async handler
2. Import and register both in _TOOL_DEFINITIONS and _TOOL_HANDLERS below
3. No changes needed to the agent workflow or worker!

# TODO [Nexus-readiness]: Each tool could be exposed as a Nexus Operation
# behind a Nexus Service. Other teams could contribute tools by deploying
# their own Nexus Services with tool handlers and registering them at a
# shared Nexus Endpoint. The tool registry would then also map tool names
# to Nexus endpoints for cross-namespace dispatch.
"""

from typing import Callable, Optional

from agent.models import ToolDefinition

# ── Import all tool definitions and handlers ──

from .campaign_management import (
    create_ad_definition,
    create_ad_group_definition,
    create_ad_handler,
    create_ad_group_handler,
    create_campaign_definition,
    create_campaign_handler,
    create_pin_definition,
    create_pin_handler,
)
from .analytics import (
    check_review_status_definition,
    check_review_status_handler,
    pull_analytics_definition,
    pull_analytics_handler,
)
from .optimization import (
    adjust_bid_strategy_definition,
    adjust_bid_strategy_handler,
    suspend_ad_group_definition,
    suspend_ad_group_handler,
    update_ad_status_definition,
    update_ad_status_handler,
    update_budget_definition,
    update_budget_handler,
    update_targeting_definition,
    update_targeting_handler,
)
from .creative_generation import (
    generate_creatives_definition,
    generate_creatives_handler,
)
from .notifications import (
    send_notification_definition,
    send_notification_handler,
)

# ── Tool Registry ──

_TOOL_DEFINITIONS: dict[str, ToolDefinition] = {
    "create_campaign": create_campaign_definition,
    "create_ad_group": create_ad_group_definition,
    "create_pin": create_pin_definition,
    "create_ad": create_ad_definition,
    "pull_analytics": pull_analytics_definition,
    "check_review_status": check_review_status_definition,
    "update_budget": update_budget_definition,
    "update_ad_status": update_ad_status_definition,
    "update_targeting": update_targeting_definition,
    "suspend_ad_group": suspend_ad_group_definition,
    "adjust_bid_strategy": adjust_bid_strategy_definition,
    "generate_creatives": generate_creatives_definition,
    "send_notification": send_notification_definition,
}

_TOOL_HANDLERS: dict[str, Callable] = {
    "create_campaign": create_campaign_handler,
    "create_ad_group": create_ad_group_handler,
    "create_pin": create_pin_handler,
    "create_ad": create_ad_handler,
    "pull_analytics": pull_analytics_handler,
    "check_review_status": check_review_status_handler,
    "update_budget": update_budget_handler,
    "update_ad_status": update_ad_status_handler,
    "update_targeting": update_targeting_handler,
    "suspend_ad_group": suspend_ad_group_handler,
    "adjust_bid_strategy": adjust_bid_strategy_handler,
    "generate_creatives": generate_creatives_handler,
    "send_notification": send_notification_handler,
}


def get_tools() -> list[ToolDefinition]:
    """Return all registered tool definitions (for passing to the agent)."""
    return list(_TOOL_DEFINITIONS.values())


def get_handler(tool_name: str) -> Optional[Callable]:
    """Look up a tool handler by name. Returns None if not found."""
    return _TOOL_HANDLERS.get(tool_name)


def get_tool_definition(tool_name: str) -> Optional[ToolDefinition]:
    """Look up a tool definition by name."""
    return _TOOL_DEFINITIONS.get(tool_name)


def register_tool(definition: ToolDefinition, handler: Callable) -> None:
    """
    Register a new tool at runtime.

    This allows plugins or extensions to add tools without modifying this file.
    """
    _TOOL_DEFINITIONS[definition.name] = definition
    _TOOL_HANDLERS[definition.name] = handler
