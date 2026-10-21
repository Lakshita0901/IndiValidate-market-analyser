from app.llm import get_llm
from app.state import MarketState

# Module-level LLM instance for backward compatibility and direct calls
llm = get_llm(temperature=0)


def extract_keywords(state: MarketState):
    if state.get("keywords") and len(state["keywords"]) > 0:
        return {"keywords": state["keywords"]}

    idea = state.get("idea", "")
    founder_ctx = state.get("founder_context") or {}
    active_llm = state.get("keywords_llm") or state.get("llm") or llm

    # Build founder context hints if present
    founder_hints = []
    if founder_ctx.get("customer_category"):
        founder_hints.append(f"- Target Customer Category: {founder_ctx['customer_category']}")
    if founder_ctx.get("customer_description"):
        founder_hints.append(f"- Customer Description: {founder_ctx['customer_description']}")
    if founder_ctx.get("problem_description"):
        founder_hints.append(f"- Customer Problem: {founder_ctx['problem_description']}")
    if founder_ctx.get("known_alternatives"):
        alts = ", ".join(founder_ctx["known_alternatives"])
        founder_hints.append(f"- Existing Alternatives / Competitors: {alts}")
    if founder_ctx.get("launch_geography"):
        founder_hints.append(f"- Launch Geography: {founder_ctx['launch_geography']}")
    if founder_ctx.get("pricing_model") and founder_ctx.get("pricing_model") != "not_decided":
        p_str = founder_ctx["pricing_model"]
        if founder_ctx.get("expected_price"):
            p_str += f" ({founder_ctx['expected_price']})"
        founder_hints.append(f"- Pricing Model: {p_str}")

    hint_section = ""
    if founder_hints:
        hint_section = (
            "\n\nFOUNDER CONTEXT (Founder-reported claims — use to sharpen keyword candidates):\n"
            + "\n".join(founder_hints)
        )

    prompt = f"""
You are the keyword extraction node of IndiValidate.

Business idea:
{idea}{hint_section}

Extract 5 to 8 important keywords or phrases suitable for search trends and discussion forum analysis.

Focus on:
- product/service
- target customer
- problem / pain points
- important characteristics
- competitor / alternative solutions (if known)
- business model / pricing

Return ONLY the keywords separated by commas.

Example:
healthy meals, college students, meal subscription, affordable food
"""

    response = active_llm.invoke(prompt)

    content = response.content
    if isinstance(content, str):
        text = content
    elif isinstance(content, list):
        text = "".join(item if isinstance(item, str) else str(item) for item in content)
    else:
        text = str(content)

    # 1. Parse and normalize whitespace
    raw_keywords = [
        " ".join(kw.strip().split())
        for kw in text.split(",")
        if kw.strip()
    ]

    # 2. Case-insensitive deduplication preserving order
    seen = set()
    keywords = []
    for kw in raw_keywords:
        key = kw.lower()
        if key and key not in seen:
            seen.add(key)
            keywords.append(kw)

    # 3. Integrate known alternatives if not already present (capped at 10)
    known_alts = founder_ctx.get("known_alternatives") or []
    for alt in known_alts:
        if alt and str(alt).strip():
            clean_alt = " ".join(str(alt).strip().split())
            key = clean_alt.lower()
            if key not in seen and len(keywords) < 10:
                seen.add(key)
                keywords.append(clean_alt)

    return {
        "keywords": keywords
    }