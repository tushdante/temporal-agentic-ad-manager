"""
Pinterest Creative Generation tool.

Uses Claude to generate Pinterest-optimized pin creatives with titles,
descriptions, CTAs, and image concepts.
"""

import json
import uuid

from agent.models import ToolArgument, ToolDefinition

# ─────────────────────────────────────────────
# generate_creatives
# ─────────────────────────────────────────────

generate_creatives_definition = ToolDefinition(
    name="generate_creatives",
    description=(
        "Use AI to generate Pinterest-optimized pin creatives. Returns a list of "
        "creative variants with titles, descriptions, CTAs, and image concepts. "
        "Pinterest recommends at least 4 active creatives per ad group."
    ),
    arguments=[
        ToolArgument(name="product_description", type="string", description="Description of the product being advertised"),
        ToolArgument(name="target_audience", type="string", description="Description of the target audience"),
        ToolArgument(name="destination_url", type="string", description="Landing page URL for the pins"),
        ToolArgument(name="objective", type="string", description="Campaign objective (AWARENESS, WEB_CONVERSIONS, etc.)"),
        ToolArgument(name="num_variants", type="number", description="Number of creative variants to generate (default: 4)", required=False),
    ],
    timeout_seconds=180,  # LLM generation can take time
)


async def generate_creatives_handler(
    product_description: str,
    target_audience: str,
    destination_url: str,
    objective: str,
    num_variants: int = 4,
) -> list[dict]:
    """Generate Pinterest-optimized pin creatives using Claude."""
    from temporalio import activity
    import anthropic

    num_variants = int(num_variants)

    prompt = f"""You are an expert Pinterest advertising creative strategist.

## Product & Audience
Product: {product_description}
Target Audience: {target_audience}
Destination URL: {destination_url}
Campaign Objective: {objective}

## Pinterest Creative Requirements
- Pin title: max 100 characters, front-load keywords
- Pin description: max 500 characters, include relevant keywords for search
- Pinterest is a VISUAL DISCOVERY platform — users are in planning/shopping mode
- Pins with lifestyle imagery outperform plain product shots
- Include seasonal or aspirational context when relevant
- CTAs: SHOP_NOW, LEARN_MORE, SIGN_UP, BOOK_NOW, GET_OFFER, DOWNLOAD

## Pinterest-Specific Optimization Notes
- Users SAVE pins they want to return to — descriptions should encourage saves
- Outbound clicks (not just pin clicks) are the key conversion metric
- Pinterest search is keyword-driven — think SEO for descriptions
- Closeup rate indicates visual appeal — imagery must be compelling at thumbnail size

## Your Task
Generate {num_variants} distinct pin creative variants. For each, provide:
1. "title": (max 100 chars, keyword-rich)
2. "description": (max 500 chars, SEO-optimized, includes CTA language)
3. "cta_type": one of [SHOP_NOW, LEARN_MORE, SIGN_UP, BOOK_NOW, GET_OFFER]
4. "image_concept": detailed description of the pin image (for designer/image gen)
5. "angle": which creative strategy this uses

Creative angles to cover:
- Lifestyle/aspirational (show the product in an ideal use scenario)
- Problem → solution (pain point the product solves)
- Social proof / trending (leverage FOMO, "most-saved", seasonal trends)

Respond ONLY with a valid JSON array."""

    activity.logger.info(f"Calling Claude to generate {num_variants} Pinterest creatives")

    client = anthropic.AsyncAnthropic(max_retries=0)
    message = await client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=2048,
        messages=[{"role": "user", "content": prompt}],
    )
    response = message.content[0].text

    try:
        text = response.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1]
            text = text.rsplit("```", 1)[0]

        variants = json.loads(text)
        creatives = []
        for v in variants[:num_variants]:
            creatives.append({
                "title": v.get("title", "")[:100],
                "description": v.get("description", "")[:500],
                "link": destination_url,
                "cta_type": v.get("cta_type", "LEARN_MORE"),
                "image_url": f"https://images.example.com/pins/{uuid.uuid4().hex[:8]}.jpg",
                "image_concept": v.get("image_concept", ""),
                "angle": v.get("angle", ""),
            })

        activity.logger.info(f"Generated {len(creatives)} creatives successfully")
        return creatives

    except (json.JSONDecodeError, KeyError, TypeError) as e:
        activity.logger.error(f"Failed to parse LLM creative response: {e}")
        return [
            {
                "title": f"Creative Variant {i+1}",
                "description": f"Discover {product_description[:100]}. Shop now!",
                "link": destination_url,
                "cta_type": "SHOP_NOW",
                "image_url": f"https://images.example.com/pins/fallback_{i}.jpg",
                "image_concept": "Fallback creative",
                "angle": "general",
            }
            for i in range(num_variants)
        ]
