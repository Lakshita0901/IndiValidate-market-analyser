from app.llm import get_llm
from app.state import MarketState

# Module-level LLM instance for backward compatibility and direct calls
llm = get_llm(temperature=0)


def analyze_idea(state: MarketState):
    if state.get("category") and str(state["category"]).strip():
        return {"category": str(state["category"]).strip()}

    idea = state["idea"]
    active_llm = state.get("idea_llm") or state.get("llm") or llm

    prompt = f"""
You are the first analysis node of IndiValidate.

Analyze the following business idea:

{idea}

Identify the primary business category.

Return ONLY the category.
Keep it short, for example:
Food & Delivery
Health & Fitness
Education
Finance
E-commerce
Productivity
Transportation
Employment
"""

    response = active_llm.invoke(prompt)
    # print(/n[Node] analyze_idea)
    # print(response.content.strip())

    content = response.content
    if isinstance(content, str):
        text = content
    elif isinstance(content, list):
        text = "".join(item if isinstance(item, str) else str(item) for item in content)
    else:
        text = str(content)

    return {
        "category": text.strip()
    }