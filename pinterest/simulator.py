"""
Simulated Pinterest analytics engine.

Generates realistic, evolving campaign metrics for demo/testing purposes.
Designed to FORCE the LLM agent to make decisions across cycles:

  Cycle 1: Learning phase — low metrics, underspend (agent should hold steady)
  Cycle 2: One ad is a clear underperformer + one is a star (agent should pause the loser)
  Cycle 3: Budget is underspent, ROAS is strong (agent should increase budget)
  Cycle 4: Creative fatigue — declining CTR across all ads (agent should refresh creatives)
  Cycle 5: Overspend + low ROAS (agent should reduce budget or pause campaign)

Replace this module with real Pinterest API calls for production use.
"""

import hashlib
import random

from .shared import micro_to_usd, usd_to_micro


def _seed_from(seed_str: str) -> random.Random:
    """Deterministic random from a string seed for reproducible sim data."""
    h = int(hashlib.md5(seed_str.encode()).hexdigest()[:8], 16)
    return random.Random(h)


# ─────────────────────────────────────────────
# Cycle Scenarios
# ─────────────────────────────────────────────

def _cycle_1_learning(rng, budget_usd, creatives):
    """Learning phase: low volume, algorithm warming up, don't touch anything."""
    impressions = int(rng.uniform(400, 700) * (budget_usd / 75.0))
    ctr = rng.uniform(0.005, 0.009)
    spend_pct = rng.uniform(0.30, 0.50)  # Underspending — algo learning
    roas = 0.0  # No conversions yet
    return _build_analytics(rng, budget_usd, creatives, impressions, ctr, spend_pct, roas,
                            save_rate=rng.uniform(0.002, 0.005),
                            ad_scenario="even")


def _cycle_2_clear_winner_loser(rng, budget_usd, creatives):
    """One ad dominates, one is terrible. Agent should pause the underperformer."""
    impressions = int(rng.uniform(900, 1400) * (budget_usd / 75.0))
    ctr = rng.uniform(0.010, 0.015)
    spend_pct = rng.uniform(0.60, 0.75)
    roas = rng.uniform(1.2, 2.0)
    return _build_analytics(rng, budget_usd, creatives, impressions, ctr, spend_pct, roas,
                            save_rate=rng.uniform(0.006, 0.012),
                            ad_scenario="winner_loser")


def _cycle_3_strong_roas_underspend(rng, budget_usd, creatives):
    """Strong performance but budget is being underspent. Agent should increase budget."""
    impressions = int(rng.uniform(1200, 1800) * (budget_usd / 75.0))
    ctr = rng.uniform(0.014, 0.020)
    spend_pct = rng.uniform(0.45, 0.60)  # Significantly underspending
    roas = rng.uniform(3.5, 6.0)  # Very strong ROAS
    return _build_analytics(rng, budget_usd, creatives, impressions, ctr, spend_pct, roas,
                            save_rate=rng.uniform(0.012, 0.020),
                            ad_scenario="all_good")


def _cycle_4_creative_fatigue(rng, budget_usd, creatives):
    """All ads declining — creative fatigue. Agent should generate new creatives."""
    impressions = int(rng.uniform(600, 900) * (budget_usd / 75.0))
    ctr = rng.uniform(0.003, 0.006)  # CTR tanked
    spend_pct = rng.uniform(0.70, 0.85)
    roas = rng.uniform(0.5, 1.0)  # Barely breaking even
    return _build_analytics(rng, budget_usd, creatives, impressions, ctr, spend_pct, roas,
                            save_rate=rng.uniform(0.001, 0.003),  # Save rate crashed
                            ad_scenario="all_declining")


def _cycle_5_overspend_low_roas(rng, budget_usd, creatives):
    """Overspending with terrible ROAS. Agent should cut budget or pause."""
    impressions = int(rng.uniform(1800, 2500) * (budget_usd / 75.0))
    ctr = rng.uniform(0.008, 0.012)
    spend_pct = rng.uniform(0.95, 1.05)  # Spending full budget or more
    roas = rng.uniform(0.2, 0.6)  # Very poor return
    return _build_analytics(rng, budget_usd, creatives, impressions, ctr, spend_pct, roas,
                            save_rate=rng.uniform(0.002, 0.005),
                            ad_scenario="all_bad")


# Map cycle number to scenario (repeats after cycle 5)
_SCENARIO_MAP = {
    1: _cycle_1_learning,
    2: _cycle_2_clear_winner_loser,
    3: _cycle_3_strong_roas_underspend,
    4: _cycle_4_creative_fatigue,
    5: _cycle_5_overspend_low_roas,
}


def generate_simulated_analytics(
    campaign_id: str,
    cycle: int,
    budget_usd: float,
    creatives: list[dict],
) -> dict:
    """
    Generate scenario-based Pinterest analytics that force the LLM to act.

    Each cycle has a distinct scenario that demands a specific decision.
    After cycle 5, scenarios repeat with slight variation.
    """
    rng = _seed_from(f"{campaign_id}-{cycle}")

    # Pick scenario based on cycle (1-indexed, repeating)
    scenario_idx = ((cycle - 1) % 5) + 1
    scenario_fn = _SCENARIO_MAP[scenario_idx]

    return scenario_fn(rng, budget_usd, creatives)


# ─────────────────────────────────────────────
# Analytics Builder
# ─────────────────────────────────────────────

def _build_analytics(
    rng: random.Random,
    budget_usd: float,
    creatives: list[dict],
    impressions: int,
    ctr: float,
    spend_pct: float,
    roas: float,
    save_rate: float,
    ad_scenario: str,
) -> dict:
    """Build a full analytics dict from high-level parameters."""
    impressions = max(impressions, 50)
    clicks = max(int(impressions * ctr), 1)
    outbound_clicks = int(clicks * rng.uniform(0.50, 0.75))
    saves = max(int(impressions * save_rate), 0)
    closeups = int(impressions * rng.uniform(0.02, 0.06))
    conversions = int(outbound_clicks * rng.uniform(0.03, 0.10)) if roas > 0 else 0

    spend_usd = budget_usd * spend_pct
    spend_micro = usd_to_micro(spend_usd)
    cpc_micro = usd_to_micro(spend_usd / max(clicks, 1))
    cpm_micro = usd_to_micro(spend_usd / max(impressions, 1) * 1000)

    ad_performances = _generate_ad_breakdown(
        rng, creatives, impressions, ctr, spend_micro, save_rate, ad_scenario,
    )

    return {
        "IMPRESSION": impressions,
        "PIN_CLICK": clicks,
        "OUTBOUND_CLICK": outbound_clicks,
        "SAVE": saves,
        "CLOSEUP": closeups,
        "TOTAL_CONVERSIONS": conversions,
        "SPEND_IN_MICRO_DOLLAR": spend_micro,
        "CPC_IN_MICRO_DOLLAR": cpc_micro,
        "CPM_IN_MICRO_DOLLAR": cpm_micro,
        "ROAS": round(roas, 2),
        "ctr": round(ctr, 4),
        "save_rate": round(save_rate, 4),
        "outbound_ctr": round(outbound_clicks / max(impressions, 1), 4),
        "spend_usd": round(spend_usd, 2),
        "budget_usd": budget_usd,
        "budget_utilization_pct": round(spend_pct * 100, 1),
        "ad_performances": ad_performances,
    }


def _generate_ad_breakdown(
    rng: random.Random,
    creatives: list[dict],
    impressions: int,
    ctr: float,
    spend_micro: int,
    save_rate: float,
    ad_scenario: str,
) -> list[dict]:
    """Generate per-ad breakdown based on the scenario type."""
    fallback = [{"ad_id": f"ad_sim_{j}", "title": f"Creative {j}"} for j in range(4)]
    active = creatives or fallback
    num_ads = len(active)
    results = []

    for i, creative in enumerate(active):
        ad_id = creative.get("ad_id", f"ad_sim_{i}") if isinstance(creative, dict) else getattr(creative, "ad_id", f"ad_sim_{i}")
        title = creative.get("title", f"Creative {i}") if isinstance(creative, dict) else getattr(creative, "title", f"Creative {i}")

        # Per-ad multiplier based on scenario
        if ad_scenario == "winner_loser":
            if i == 0:
                mult = rng.uniform(2.0, 2.8)   # Clear star
            elif i == num_ads - 1:
                mult = rng.uniform(0.10, 0.20)  # Terrible — CTR near zero, wasting money
            else:
                mult = rng.uniform(0.7, 1.1)
        elif ad_scenario == "all_declining":
            mult = rng.uniform(0.3, 0.6)  # Everything is bad
        elif ad_scenario == "all_bad":
            mult = rng.uniform(0.2, 0.5)
        elif ad_scenario == "all_good":
            mult = rng.uniform(0.9, 1.3)
        else:  # "even"
            mult = rng.uniform(0.8, 1.2)

        ad_imp = max(int(impressions / num_ads * mult), 10)
        ad_ctr = max(ctr * mult, 0.001)
        ad_clicks = max(int(ad_imp * ad_ctr), 0)
        ad_saves = max(int(ad_imp * save_rate * mult), 0)
        ad_outbound = int(ad_clicks * rng.uniform(0.4, 0.75))
        ad_spend = int(spend_micro / num_ads * mult)

        results.append({
            "ad_id": ad_id,
            "title": title,
            "impressions": ad_imp,
            "clicks": ad_clicks,
            "outbound_clicks": ad_outbound,
            "saves": ad_saves,
            "ctr": round(ad_ctr, 4),
            "save_rate": round(ad_saves / max(ad_imp, 1), 4),
            "spend_micro": ad_spend,
            "spend_usd": round(micro_to_usd(ad_spend), 2),
        })

    return results
