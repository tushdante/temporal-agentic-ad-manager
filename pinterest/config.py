"""
Pinterest Ad Agent Configuration.

This is the ONLY Pinterest-specific file needed to run the agent.
It assembles the goal, tools, and system prompt, then creates an AgentConfig
that is passed to the generic AgentWorkflow.

To create a different agent (e.g., Google Ads, Meta Ads), create a similar
config file with different tools and prompts — NO changes to the workflow.
"""

from agent.models import AgentConfig, AgentContinueState
from pinterest.tools import get_tools

# ─────────────────────────────────────────────
# Pinterest System Prompt
# ─────────────────────────────────────────────

PINTEREST_SYSTEM_PROMPT = """You are an autonomous Pinterest ad campaign management agent.

## Your Capabilities
You manage the full lifecycle of Pinterest ad campaigns:
1. **Setup**: Create campaigns, ad groups, pins, and promote them as ads
2. **Creative**: Generate Pinterest-optimized pin creatives using AI
3. **Monitor**: Pull analytics and check ad review statuses
4. **Optimize**: Adjust budgets, pause underperformers, update targeting

## Pinterest-Specific Knowledge
- Pinterest is a VISUAL DISCOVERY platform — users plan purchases
- SAVES are a leading indicator — high save rate means purchase intent
- OUTBOUND_CLICK (not PIN_CLICK) measures actual traffic to destination
- Campaigns need 50+ conversions/week for algorithm optimization
- Pin performance improves over time as Pinterest's algorithm learns
- Typical benchmarks: CPC $0.10-$1.50, CPM $2-$5, save rate >1% is strong

## Optimization Guidelines
- Cycles 1-5: Be CONSERVATIVE. Pinterest needs time to learn.
- Cycles 6-15: Start optimizing. Pause lowest performers, test targeting.
- Cycles 15+: Aggressive optimization. Scale winners, cut losers.

## Guardrails (ENFORCED)
- Max budget increase: 20% per cycle
- Min active ads per group: 3
- Always check review_status before judging creative performance

## Workflow Pattern
When setting up a new campaign:
1. First, generate creatives with generate_creatives
2. Create the campaign with create_campaign
3. Create an ad group with create_ad_group
4. For each creative: create_pin then create_ad
5. Send a notification about the launch

When optimizing:
1. Pull analytics with pull_analytics
2. Check review statuses with check_review_status
3. Analyze the data and decide on action
4. Execute the action (update_budget, update_ad_status, etc.)
5. Report significant changes via send_notification

When you have completed all requested work, respond with "done".
"""


def create_pinterest_agent_config(
    campaign_name: str,
    product_description: str,
    target_audience: str,
    destination_url: str,
    ad_account_id: str,
    daily_budget_usd: float,
    max_budget_usd: float = 500.0,
    objective: str = "WEB_CONVERSIONS",
    demo_mode: bool = False,
    max_cycles: int = 5,
) -> AgentContinueState:
    """
    Create a fully configured Pinterest agent ready to start.

    This function is the single integration point between the generic
    agent framework and Pinterest-specific domain knowledge.

    Returns an AgentContinueState that can be passed directly to
    AgentWorkflow.run().
    """
    # Build the initial prompt that tells the agent what to do
    initial_prompt = f"""Set up and launch a Pinterest ad campaign with these details:

Campaign Name: {campaign_name}
Product: {product_description}
Target Audience: {target_audience}
Destination URL: {destination_url}
Ad Account ID: {ad_account_id}
Objective: {objective}
Daily Budget: ${daily_budget_usd}
Max Daily Budget: ${max_budget_usd}

Steps:
1. Generate 4 Pinterest-optimized creative variants for this product/audience
2. Create the campaign (objective: {objective}, budget: ${daily_budget_usd}/day)
3. Create an ad group with targeting for the described audience
4. Create a pin for each creative variant
5. Promote each pin as an ad in the ad group
6. Send a Slack notification about the launch

After setup, respond with "done" and include a summary of what was created
(campaign_id, ad_group_id, ad_ids, pin_ids)."""

    follow_up_prompt = f"""Run an optimization cycle for campaign '{campaign_name}':

1. Pull analytics for the campaign (use the campaign_id from previous results)
2. Check review statuses for all ads
3. Based on the metrics, decide if any action is needed:
   - If performance is good, report and done
   - If underperformers exist, pause them (unless min 3 active ads)
   - If budget is underspent and ROAS is good, consider increasing budget
   - If creative fatigue detected (declining CTR), generate new creatives
4. Send a notification if any significant changes were made

Respond with "done" and include the analytics summary and any actions taken."""

    config = AgentConfig(
        goal=f"Manage Pinterest ad campaign '{campaign_name}' — set up, monitor, and optimize.",
        tools=get_tools(),
        system_prompt=PINTEREST_SYSTEM_PROMPT,
        initial_prompt=initial_prompt,
        require_confirmation=False,
        max_iterations=50,
        follow_up_prompt=follow_up_prompt,
        follow_up_interval_seconds=15 if demo_mode else 21600,  # 15s demo, 6h prod
        max_cycles=max_cycles,
    )

    return AgentContinueState(config=config)
