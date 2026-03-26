"""
Pinterest Campaign CRUD tools.

Each tool has:
1. A ToolDefinition (the LLM-facing schema)
2. An async handler function (the actual implementation)

[SIMULATED] — All API calls are logged but not executed.
Replace with real Pinterest v5 API calls for production.
"""

import uuid

from agent.models import ToolArgument, ToolDefinition
from pinterest.shared import PINTEREST_API_BASE, PinterestTargeting, usd_to_micro

# ─────────────────────────────────────────────
# create_campaign
# ─────────────────────────────────────────────

create_campaign_definition = ToolDefinition(
    name="create_campaign",
    description=(
        "Create a new Pinterest ad campaign container. "
        "Returns the campaign_id. Must be called before creating ad groups or ads."
    ),
    arguments=[
        ToolArgument(name="ad_account_id", type="string", description="Pinterest ad account ID"),
        ToolArgument(name="campaign_name", type="string", description="Name for the campaign"),
        ToolArgument(name="objective", type="string", description="Campaign objective: AWARENESS, CONSIDERATION, WEB_CONVERSIONS, CATALOG_SALES"),
        ToolArgument(name="daily_budget_usd", type="number", description="Daily spend cap in USD"),
    ],
    timeout_seconds=120,
    requires_confirmation=True,
)


async def create_campaign_handler(
    ad_account_id: str,
    campaign_name: str,
    objective: str,
    daily_budget_usd: float,
) -> dict:
    """POST /ad_accounts/{ad_account_id}/campaigns [SIMULATED]"""
    from temporalio import activity

    campaign_id = f"camp_{uuid.uuid4().hex[:12]}"
    activity.logger.info(
        f"[SIM] POST {PINTEREST_API_BASE}/ad_accounts/{ad_account_id}/campaigns "
        f"-> {campaign_id} (name: {campaign_name}, budget: ${daily_budget_usd}/day)"
    )
    return {
        "campaign_id": campaign_id,
        "name": campaign_name,
        "objective": objective,
        "daily_budget_usd": daily_budget_usd,
    }


# ─────────────────────────────────────────────
# create_ad_group
# ─────────────────────────────────────────────

create_ad_group_definition = ToolDefinition(
    name="create_ad_group",
    description=(
        "Create an ad group within a campaign. Ad groups hold targeting, budget, "
        "and bidding config. Must be called after create_campaign."
    ),
    arguments=[
        ToolArgument(name="ad_account_id", type="string", description="Pinterest ad account ID"),
        ToolArgument(name="campaign_id", type="string", description="Campaign ID to create the ad group in"),
        ToolArgument(name="name", type="string", description="Ad group name"),
        ToolArgument(name="daily_budget_usd", type="number", description="Daily budget for this ad group"),
        ToolArgument(name="bid_strategy", type="string", description="Bid strategy: AUTOMATIC_BID, MAX_BID, TARGET_AVG"),
        ToolArgument(name="countries", type="array", description="Target countries (e.g., ['US'])", required=False),
        ToolArgument(name="age_buckets", type="array", description="Target age ranges", required=False),
        ToolArgument(name="genders", type="array", description="Target genders", required=False),
        ToolArgument(name="interests", type="array", description="Pinterest interest IDs", required=False),
        ToolArgument(name="keywords", type="array", description="Search keywords for targeting", required=False),
    ],
    timeout_seconds=120,
    requires_confirmation=True,
)


async def create_ad_group_handler(
    ad_account_id: str,
    campaign_id: str,
    name: str,
    daily_budget_usd: float,
    bid_strategy: str = "AUTOMATIC_BID",
    countries: list[str] = None,
    age_buckets: list[str] = None,
    genders: list[str] = None,
    interests: list[str] = None,
    keywords: list[str] = None,
) -> dict:
    """POST /ad_accounts/{ad_account_id}/ad_groups [SIMULATED]"""
    from temporalio import activity

    ad_group_id = f"agrp_{uuid.uuid4().hex[:12]}"
    activity.logger.info(
        f"[SIM] POST {PINTEREST_API_BASE}/ad_accounts/{ad_account_id}/ad_groups "
        f"-> {ad_group_id} ({name}, ${daily_budget_usd}/day, {bid_strategy})"
    )
    return {
        "id": ad_group_id,
        "name": name,
        "budget_micro": usd_to_micro(daily_budget_usd),
        "bid_strategy": bid_strategy,
        "targeting": {
            "GEO": countries or ["US"],
            "AGE_BUCKET": age_buckets or ["25-34", "35-44"],
            "GENDER": genders or ["male", "female"],
            "INTEREST": interests or [],
            "KEYWORD": keywords or [],
        },
    }


# ─────────────────────────────────────────────
# create_pin
# ─────────────────────────────────────────────

create_pin_definition = ToolDefinition(
    name="create_pin",
    description=(
        "Create an organic Pinterest pin. Returns pin_id. "
        "The pin must be created before it can be promoted as an ad."
    ),
    arguments=[
        ToolArgument(name="ad_account_id", type="string", description="Pinterest ad account ID"),
        ToolArgument(name="title", type="string", description="Pin title (max 100 chars)"),
        ToolArgument(name="description", type="string", description="Pin description (max 500 chars)"),
        ToolArgument(name="link", type="string", description="Destination URL for the pin"),
        ToolArgument(name="image_url", type="string", description="URL of the pin image", required=False),
        ToolArgument(name="cta_type", type="string", description="CTA type: SHOP_NOW, LEARN_MORE, SIGN_UP, etc.", required=False),
    ],
    timeout_seconds=120,
    requires_confirmation=True,
)


async def create_pin_handler(
    ad_account_id: str,
    title: str,
    description: str,
    link: str,
    image_url: str = None,
    cta_type: str = "LEARN_MORE",
) -> dict:
    """POST /pins [SIMULATED]"""
    from temporalio import activity

    pin_id = f"pin_{uuid.uuid4().hex[:12]}"
    activity.logger.info(
        f"[SIM] POST {PINTEREST_API_BASE}/pins -> {pin_id} "
        f"(title: {title[:50]}...)"
    )
    return {
        "pin_id": pin_id,
        "title": title,
        "description": description,
        "link": link,
        "image_url": image_url or f"https://images.example.com/pins/{uuid.uuid4().hex[:8]}.jpg",
        "cta_type": cta_type,
    }


# ─────────────────────────────────────────────
# create_ad
# ─────────────────────────────────────────────

create_ad_definition = ToolDefinition(
    name="create_ad",
    description=(
        "Promote a pin as a paid ad within an ad group. Returns ad_id. "
        "The pin must already exist (use create_pin first)."
    ),
    arguments=[
        ToolArgument(name="ad_account_id", type="string", description="Pinterest ad account ID"),
        ToolArgument(name="ad_group_id", type="string", description="Ad group to place the ad in"),
        ToolArgument(name="pin_id", type="string", description="Pin ID to promote as an ad"),
        ToolArgument(name="name", type="string", description="Ad name for tracking"),
    ],
    timeout_seconds=120,
    requires_confirmation=True,
)


async def create_ad_handler(
    ad_account_id: str,
    ad_group_id: str,
    pin_id: str,
    name: str = "",
) -> dict:
    """POST /ad_accounts/{ad_account_id}/ads [SIMULATED]"""
    from temporalio import activity

    ad_id = f"ad_{uuid.uuid4().hex[:12]}"
    activity.logger.info(
        f"[SIM] POST {PINTEREST_API_BASE}/ad_accounts/{ad_account_id}/ads "
        f"-> {ad_id} (pin: {pin_id}, group: {ad_group_id})"
    )
    return {
        "ad_id": ad_id,
        "pin_id": pin_id,
        "ad_group_id": ad_group_id,
        "name": name,
        "status": "ACTIVE",
    }
