from app.llm import get_llm
from app.state import MarketState

# Module-level LLM instance for backward compatibility and direct calls
llm = get_llm(temperature=0)


def identify_location(state: MarketState):
    if state.get("location") and state.get("geography_diagnostics"):
        return {
            "location": state["location"],
            "geography_diagnostics": state["geography_diagnostics"],
        }

    idea = state.get("idea", "")
    founder_ctx = state.get("founder_context") or {}
    active_llm = state.get("location_llm") or state.get("llm") or llm

    prompt = f"""
You are the geographic-market identification node of IndiValidate.

Business idea:
{idea}

Identify the location or geographic market explicitly mentioned.

If a specific location is mentioned, return it.

If no location is mentioned, return:
Not specified

Return ONLY the location.
"""

    response = active_llm.invoke(prompt)

    content = response.content
    if isinstance(content, str):
        text = content
    elif isinstance(content, list):
        text = "".join(item if isinstance(item, str) else str(item) for item in content)
    else:
        text = str(content)

    inferred_location = text.strip()

    # Precedence rule: explicit launch geography takes precedence over inferred location
    launch_geo = founder_ctx.get("launch_geography")
    active_location = inferred_location
    has_discrepancy = False
    discrepancy_msg = None

    if launch_geo and str(launch_geo).strip():
        clean_launch_geo = str(launch_geo).strip()
        if inferred_location and inferred_location.lower() not in ("not specified", ""):
            if inferred_location.lower() != clean_launch_geo.lower():
                has_discrepancy = True
                discrepancy_msg = (
                    f"Discrepancy: Inferred location '{inferred_location}' conflicts with "
                    f"explicit founder launch geography '{clean_launch_geo}'. "
                    f"Founder launch geography takes precedence."
                )
        active_location = clean_launch_geo

    geo_diag = {
        "inferred_location": inferred_location,
        "launch_geography": launch_geo,
        "active_location": active_location,
        "has_discrepancy": has_discrepancy,
    }
    if discrepancy_msg:
        geo_diag["discrepancy_message"] = discrepancy_msg

    return {
        "location": active_location,
        "geography_diagnostics": geo_diag,
    }