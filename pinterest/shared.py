"""
Shared types, constants, and helpers for the Pinterest Ad Agent.

This module is imported by workflows, activities, starter, and demo scripts.
It must NOT import temporalio.workflow or temporalio.activity to stay sandbox-safe.
"""

import os
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Any, Optional

from temporalio.common import RetryPolicy


# ─────────────────────────────────────────────
# Constants — Pinterest API
# ─────────────────────────────────────────────

PINTEREST_API_BASE = "https://api.pinterest.com/v5"
MICROCURRENCY_FACTOR = 1_000_000  # 1 USD = 1,000,000 microdollars

DEMO_MODE = os.environ.get("DEMO_MODE", "false").lower() == "true"


# ─────────────────────────────────────────────
# Currency Helpers
# ─────────────────────────────────────────────

def usd_to_micro(usd: float) -> int:
    """Convert USD to Pinterest microcurrency (1 USD = 1,000,000)."""
    return int(usd * MICROCURRENCY_FACTOR)


def micro_to_usd(micro: int) -> float:
    """Convert Pinterest microcurrency to USD."""
    return micro / MICROCURRENCY_FACTOR


# ─────────────────────────────────────────────
# Data Models — dict-based for Temporal serialization
# ─────────────────────────────────────────────
# Temporal's default JSON payload converter handles plain dataclasses
# but struggles with Enum fields. We store enum values as strings.


@dataclass
class Guardrails:
    """Safety limits enforced in code — LLM decisions are checked against these."""
    max_daily_budget_usd: float = 500.0
    max_budget_increase_pct: float = 0.20
    min_observation_hours: int = 24
    max_changes_per_day: int = 3
    require_human_approval_above_usd: float = 1000.0
    max_total_spend_usd: float = 50000.0
    min_active_ads_per_group: int = 3       # Pinterest recommends ≥10, start small
    max_ad_groups_per_campaign: int = 5


@dataclass
class PinterestTargeting:
    """Maps to Pinterest ad_group targeting fields."""
    countries: list[str] = field(default_factory=lambda: ["US"])
    age_buckets: list[str] = field(default_factory=lambda: ["25-34", "35-44"])
    genders: list[str] = field(default_factory=lambda: ["male", "female"])
    interests: list[str] = field(default_factory=list)  # Pinterest interest IDs
    keywords: list[str] = field(default_factory=list)


@dataclass
class CampaignConfig:
    """Initial campaign configuration — immutable after workflow start."""
    campaign_name: str
    objective: str   # AWARENESS, CONSIDERATION, WEB_CONVERSIONS, CATALOG_SALES
    ad_account_id: str
    target_audience_description: str   # Natural language — fed to LLM
    product_description: str           # Natural language — fed to LLM
    destination_url: str               # Landing page for pins
    initial_daily_budget_usd: float
    targeting: PinterestTargeting = field(default_factory=PinterestTargeting)
    bid_strategy: str = "AUTOMATIC_BID"  # AUTOMATIC_BID, MAX_BID, TARGET_AVG
    guardrails: Guardrails = field(default_factory=Guardrails)
    evaluation_interval_hours: int = 6
    demo_mode: bool = False  # Use short sleep intervals for demos


@dataclass
class PinCreative:
    """Represents a Pinterest Pin used as an ad creative."""
    pin_id: Optional[str] = None       # Set after creation via API
    ad_id: Optional[str] = None        # Set after promoting pin as ad
    title: str = ""
    description: str = ""
    link: str = ""
    image_url: Optional[str] = None    # URL to pin image
    cta_type: str = "LEARN_MORE"       # SHOP_NOW, LEARN_MORE, SIGN_UP, etc.
    status: str = "draft"              # draft | active | paused | rejected
    review_status: Optional[str] = None  # APPROVED, REJECTED, PENDING


@dataclass
class AgentState:
    """Carried across ContinueAsNew boundaries."""
    config: CampaignConfig
    pinterest_campaign_id: Optional[str] = None
    ad_groups: list[dict] = field(default_factory=list)   # [{id, name, budget_micro, ...}]
    creatives: list[PinCreative] = field(default_factory=list)
    current_daily_budget_usd: float = 0.0
    total_spend_usd: float = 0.0
    cycle_count: int = 0
    changes_today: int = 0
    last_performance: Optional[dict] = None    # Full analytics snapshot
    decision_log: list[str] = field(default_factory=list)
    awaiting_human_approval: bool = False


@dataclass
class AgentDecision:
    """Output from the LLM evaluation activity."""
    action: str
    reasoning: str
    details: dict = field(default_factory=dict)
    requires_approval: bool = False


# ─────────────────────────────────────────────
# Retry Policies
# ─────────────────────────────────────────────

LLM_RETRY = RetryPolicy(
    initial_interval=timedelta(seconds=2),
    backoff_coefficient=2.0,
    maximum_attempts=3,
)

PINTEREST_RETRY = RetryPolicy(
    initial_interval=timedelta(seconds=5),
    backoff_coefficient=2.0,
    maximum_attempts=5,
    non_retryable_error_types=["PinterestValidationError", "PinterestAuthError"],
)
