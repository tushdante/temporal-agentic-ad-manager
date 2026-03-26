"""
Notification tool.

Sends alerts via Slack, email, or other channels.
Currently logs to console for demo purposes.
"""

from agent.models import ToolArgument, ToolDefinition

# ─────────────────────────────────────────────
# send_notification
# ─────────────────────────────────────────────

send_notification_definition = ToolDefinition(
    name="send_notification",
    description=(
        "Send a notification to the team via Slack, email, or other channels. "
        "Use for important events: campaign launches, HITL approvals needed, "
        "budget alerts, or campaign pauses."
    ),
    arguments=[
        ToolArgument(name="channel", type="string", description="Notification channel: 'slack', 'email', 'sms'"),
        ToolArgument(name="message", type="string", description="Notification message content"),
    ],
    timeout_seconds=30,
)


async def send_notification_handler(channel: str, message: str) -> dict:
    """Send notification. Logs to console in demo mode."""
    from temporalio import activity

    activity.logger.info(f"{'='*60}")
    activity.logger.info(f"NOTIFICATION [{channel.upper()}]")
    activity.logger.info(f"{message}")
    activity.logger.info(f"{'='*60}")
    return {"success": True, "channel": channel}
