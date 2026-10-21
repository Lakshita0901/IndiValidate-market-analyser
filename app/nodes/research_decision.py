from app.state import MarketState


def research_decision(state: MarketState):
    keywords = state.get("keywords", [])
    target = state.get("target_segment", "")
    location = state.get("location", "")
    founder_ctx = state.get("founder_context") or {}

    effective_location = founder_ctx.get("launch_geography") or location

    if effective_location and effective_location != "Not specified":
        research_type = "location_based"
    elif target:
        research_type = "consumer"
    else:
        research_type = "general"

    print(f">>> RESEARCH DECISION: {research_type}")

    return {
        "research_type": research_type
    }