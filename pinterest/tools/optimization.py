"""
Pinterest Campaign Optimization tools.

Tools for adjusting budgets, pausing/activating ads, and updating targeting.
[SIMULATED] — All API calls are logged but not executed.
"""

import json

from agent.models import ToolArgument, ToolDefinition
from pinterest.shared import PINTEREST_API_BASE, usd_to_micro

# ─────────────────────────────────────────────
# update_budget
# ─────────────────────────────────────────────

update_budget_definition = ToolDefinition(
    name="update_budget",
    description=(
        "Update a Pinterest campaign's daily spend cap. "
        "GUARDRAIL: max increase of 20% per cycle is enforced server-side. "
        "Budget must be between $1 and the campaign's max_daily_budget."
    ),
    arguments=[
        ToolArgument(name="ad_account_id", type="string", description="Pinterest ad account ID"),
        ToolArgument(name="campaign_id", type="string", description="Campaign ID to update"),
        ToolArgument(name="new_daily_budget_usd", type="number", description="New daily budget in USD"),
    ],
    timeout_seconds=120,
    requires_confirmation=True,
)


async def update_budget_handler(
    ad_account_id: str,
    campaign_id: str,
    new_daily_budget_usd: float,
) -> dict:
    """PATCH /ad_accounts/{ad_account_id}/campaigns [SIMULATED]"""
    from temporalio import activity

    activity.logger.info(
        f"[SIM] PATCH campaign {campaign_id}: daily_spend_cap -> ${new_daily_budget_usd:.2f} "
        f"({usd_to_micro(new_daily_budget_usd)} microdollars)"
    )
    return {
        "success": True,
        "campaign_id": campaign_id,
        "new_daily_budget_usd": new_daily_budget_usd,
    }


# ─────────────────────────────────────────────
# update_ad_status
# ─────────────────────────────────────────────

update_ad_status_definition = ToolDefinition(
    name="update_ad_status",
    description=(
        "Pause or reactivate a specific Pinterest ad. "
        "GUARDRAIL: cannot pause below 3 active ads per ad group. "
        "Check review_status first — REJECTED ads should not be counted as underperformers."
    ),
    arguments=[
        ToolArgument(name="ad_account_id", type="string", description="Pinterest ad account ID"),
        ToolArgument(name="ad_id", type="string", description="Ad ID to update"),
        ToolArgument(name="status", type="string", description="New status: ACTIVE or PAUSED"),
    ],
    timeout_seconds=120,
    requires_confirmation=True,
)


async def update_ad_status_handler(
    ad_account_id: str,
    ad_id: str,
    status: str,
) -> dict:
    """PATCH /ad_accounts/{ad_account_id}/ads [SIMULATED]"""
    from temporalio import activity

    activity.logger.info(f"[SIM] PATCH ad {ad_id}: status -> {status}")
    return {
        "success": True,
        "ad_id": ad_id,
        "status": status,
    }


# ─────────────────────────────────────────────
# update_targeting
# ─────────────────────────────────────────────

update_targeting_definition = ToolDefinition(
    name="update_targeting",
    description=(
        "Update targeting parameters on a Pinterest ad group. "
        "Can modify keywords, interests, demographics, and geographic targeting."
    ),
    arguments=[
        ToolArgument(name="ad_account_id", type="string", description="Pinterest ad account ID"),
        ToolArgument(name="ad_group_id", type="string", description="Ad group ID to update"),
        ToolArgument(name="targeting_changes", type="object", description="Dict of targeting changes (e.g., {keywords: [...], interests: [...]})"),
    ],
    timeout_seconds=120,
    requires_confirmation=True,
)


async def update_targeting_handler(
    ad_account_id: str,
    ad_group_id: str,
    targeting_changes: dict,
) -> dict:
    """PATCH /ad_accounts/{ad_account_id}/ad_groups [SIMULATED]"""
    from temporalio import activity

    activity.logger.info(
        f"[SIM] PATCH ad_group {ad_group_id}: targeting -> {json.dumps(targeting_changes)}"
    )
    return {
        "success": True,
        "ad_group_id": ad_group_id,
        "targeting_changes": targeting_changes,
    }


# ─────────────────────────────────────────────
# suspend_ad_group
# ─────────────────────────────────────────────

suspend_ad_group_definition = ToolDefinition(
    name="suspend_ad_group",
    description=(
        "Suspend an entire Pinterest ad group. This pauses ALL ads in the group. "
        "Use when the ad group is consistently underperforming or overspending. "
        "This is a significant action — all ads in the group will stop serving."
    ),
    arguments=[
        ToolArgument(name="ad_account_id", type="string", description="Pinterest ad account ID"),
        ToolArgument(name="ad_group_id", type="string", description="Ad group ID to suspend"),
        ToolArgument(name="reason", type="string", description="Reason for suspension (logged for audit)"),
    ],
    timeout_seconds=120,
    requires_confirmation=True,
)


async def suspend_ad_group_handler(
    ad_account_id: str,
    ad_group_id: str,
    reason: str = "",
) -> dict:
    """PATCH /ad_accounts/{ad_account_id}/ad_groups [SIMULATED]"""
    from temporalio import activity

    activity.logger.info(
        f"[SIM] PATCH ad_group {ad_group_id}: status -> PAUSED (reason: {reason})"
    )
    return {
        "success": True,
        "ad_group_id": ad_group_id,
        "status": "PAUSED",
        "reason": reason,
    }


# ─────────────────────────────────────────────
# adjust_bid_strategy
# ─────────────────────────────────────────────

adjust_bid_strategy_definition = ToolDefinition(
    name="adjust_bid_strategy",
    description=(
        "Change the bidding strategy for a Pinterest ad group. "
        "Options: AUTOMATIC_BID (Pinterest optimizes), MAX_BID (set ceiling), "
        "TARGET_AVG (target average cost). Switch to AUTOMATIC_BID when performance "
        "is volatile, or TARGET_AVG when you have a clear CPA target."
    ),
    arguments=[
        ToolArgument(name="ad_account_id", type="string", description="Pinterest ad account ID"),
        ToolArgument(name="ad_group_id", type="string", description="Ad group ID to update"),
        ToolArgument(name="new_strategy", type="string", description="New bid strategy: AUTOMATIC_BID, MAX_BID, or TARGET_AVG"),
        ToolArgument(name="bid_amount_usd", type="number", description="Bid amount in USD (required for MAX_BID and TARGET_AVG)", required=False),
    ],
    timeout_seconds=120,
    requires_confirmation=True,
)


async def adjust_bid_strategy_handler(
    ad_account_id: str,
    ad_group_id: str,
    new_strategy: str,
    bid_amount_usd: float = None,
) -> dict:
    """PATCH /ad_accounts/{ad_account_id}/ad_groups [SIMULATED]"""
    from temporalio import activity

    bid_info = f" bid=${bid_amount_usd:.2f}" if bid_amount_usd else ""
    activity.logger.info(
        f"[SIM] PATCH ad_group {ad_group_id}: bid_strategy -> {new_strategy}{bid_info}"
    )
    return {
        "success": True,
        "ad_group_id": ad_group_id,
        "new_strategy": new_strategy,
        "bid_amount_usd": bid_amount_usd,
    }
