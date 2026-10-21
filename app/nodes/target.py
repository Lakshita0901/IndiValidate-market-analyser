from app.llm import get_llm
from app.state import MarketState

# Module-level LLM instance for backward compatibility and direct calls
llm = get_llm(temperature=0)


def identify_target(state: MarketState):
    if state.get("target_segment") and str(state["target_segment"]).strip():
        return {"target_segment": str(state["target_segment"]).strip()}

    idea = state["idea"]
    active_llm = state.get("target_llm") or state.get("llm") or llm

    prompt = f"""
You are the target-market identification node of IndiValidate.

Business idea:
{idea}

Identify the primary target customer.

Return ONLY the target customer segment.

Examples:
College students
Working professionals
Small business owners
Parents with young children
Senior citizens
"""
    
    response = active_llm.invoke(prompt)

    content = response.content
    if isinstance(content, str):
        text = content
    elif isinstance(content, list):
        text = "".join(item if isinstance(item, str) else str(item) for item in content)
    else:
        text = str(content)

    return {
        "target_segment": text.strip()
    }