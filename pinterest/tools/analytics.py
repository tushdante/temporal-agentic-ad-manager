"""
Pinterest Analytics & Monitoring tools.

Provides tools for pulling campaign performance metrics and checking ad review statuses.
[SIMULATED] — uses the simulator module for demo/testing.
"""

from agent.models import ToolArgument, ToolDefinition
from pinterest.shared import micro_to_usd
from pinterest.simulator import generate_simulated_analytics

# ─────────────────────────────────────────────
# pull_analytics
# ─────────────────────────────────────────────

pull_analytics_definition = ToolDefinition(
    name="pull_analytics",
    description=(
        "Pull performance analytics for a Pinterest campaign. Returns metrics including "
        "impressions, clicks, saves, closeups, conversions, spend, ROAS, and per-ad breakdown. "
        "Use this to evaluate campaign performance before making optimization decisions."
    ),
    arguments=[
        ToolArgument(name="ad_account_id", type="string", description="Pinterest ad account ID"),
        ToolArgument(name="campaign_id", type="string", description="Campaign ID to pull analytics for"),
        ToolArgument(name="cycle", type="number", description="Current optimization cycle number"),
        ToolArgument(name="budget_usd", type="number", description="Current daily budget in USD"),
        ToolArgument(name="creative_info", type="array", description="List of {ad_id, title, status} for each creative", required=False),
    ],
    timeout_seconds=120,
)


async def pull_analytics_handler(
    ad_account_id: str,
    campaign_id: str,
    cycle: int = 0,
    budget_usd: float = 75.0,
    creative_info: list[dict] = None,
) -> dict:
    """GET /ad_accounts/{ad_account_id}/campaigns/analytics [SIMULATED]"""
    from temporalio import activity

    analytics = generate_simulated_analytics(
        campaign_id=campaign_id,
        cycle=int(cycle),
        budget_usd=float(budget_usd),
        creatives=creative_info or [],
    )
    activity.logger.info(
        f"[SIM] Analytics cycle #{cycle}: "
        f"{analytics['IMPRESSION']} impressions, "
        f"{analytics['PIN_CLICK']} clicks, "
        f"{analytics['SAVE']} saves, "
        f"${micro_to_usd(analytics['SPEND_IN_MICRO_DOLLAR']):.2f} spend, "
        f"ROAS: {analytics['ROAS']}"
    )
    return analytics


# ─────────────────────────────────────────────
# check_review_status
# ─────────────────────────────────────────────

check_review_status_definition = ToolDefinition(
    name="check_review_status",
    description=(
        "Check the review status of Pinterest ads. Returns APPROVED, REJECTED, or PENDING "
        "for each ad. Ads must be approved before they can serve impressions. "
        "Always check review status before blaming poor performance on creative quality."
    ),
    arguments=[
        ToolArgument(name="ad_account_id", type="string", description="Pinterest ad account ID"),
        ToolArgument(name="ad_ids", type="array", description="List of ad IDs to check"),
    ],
    timeout_seconds=60,
)


async def check_review_status_handler(
    ad_account_id: str,
    ad_ids: list[str] = None,
) -> list[dict]:
    """GET /ad_accounts/{ad_account_id}/ads [SIMULATED]"""
    from temporalio import activity

    if not ad_ids:
        return []

    statuses = []
    for i, ad_id in enumerate(ad_ids):
        if i == 0 and len(ad_ids) > 2:
            review = "PENDING"
        else:
            review = "APPROVED"

        statuses.append({
            "ad_id": ad_id,
            "review_status": review,
            "rejected_reasons": [],
        })

    activity.logger.info(
        f"[SIM] Ad review statuses: "
        + ", ".join(f"{s['ad_id'][:15]}={s['review_status']}" for s in statuses)
    )
    return statuses
