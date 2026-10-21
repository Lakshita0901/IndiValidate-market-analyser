"""
app.nodes.gemini_context
------------------------
Node and helper functions for evidence sufficiency determination and
Gemini fallback context generation (Step 8.5).

ARCHITECTURAL RULES:
1. Called ONLY when empirical evidence is absent or insufficient.
2. Generates general startup/customer context, pain-point hypotheses,
   assumptions, and persona-generation guidance.
3. Output is passed into Mistral's persona generation prompt.
4. Output is STRICTLY ISOLATED from the empirical evidence pool:
   never appended to normalized_evidence, cleaned_evidence, retrieval_documents,
   document_chunks, or ChromaDB.
5. Never used as a fallback for Mistral persona generation or evaluation failures.
"""

import logging
import os
from typing import Any, Dict, Optional, Tuple

from app.llm import get_gemini_llm, has_gemini_api_key
from app.schemas.gemini_context import GeminiFallbackContext
from app.state import MarketState
from app.utils.json_utils import capture_failed_response_diagnostics, parse_json_robust

logger = logging.getLogger(__name__)


def is_evidence_sufficient(state: MarketState) -> bool:
    """
    Determine whether retrieved empirical evidence is sufficient to ground personas.

    Evidence is deemed absent or insufficient if:
    - Explicitly forced via state['force_gemini_fallback'] = True (for testing/override)
    - cleaned_evidence is empty or fewer than 2 items
    - document_chunks is empty or fewer than 2 items
    - All 4 sources (reddit, trends, census, plfs) returned empty records
    """
    if state.get("force_gemini_fallback") is True:
        return False

    cleaned = state.get("cleaned_evidence") or []
    chunks = state.get("document_chunks") or []
    reddit = state.get("reddit_evidence") or []
    trends = state.get("trends_evidence") or []
    census = state.get("census_evidence") or []
    plfs = state.get("plfs_evidence") or []

    # If both chunks and cleaned evidence are absent, evidence is absent
    if len(cleaned) == 0 or len(chunks) == 0:
        return False

    # Check that at least one external empirical source returned substantive data
    total_source_records = len(reddit) + len(trends) + len(census) + len(plfs)
    if total_source_records == 0:
        return False

    # Minimal sufficiency threshold: at least 2 cleaned records and 2 chunks
    if len(cleaned) < 2 or len(chunks) < 2:
        return False

    return True


def generate_gemini_context(
    idea: str,
    target_segment: str = "",
    location: str = "",
    category: str = "",
    founder_context: Optional[Dict[str, Any]] = None,
    llm: Optional[Any] = None,
) -> Tuple[GeminiFallbackContext, Dict[str, Any]]:
    """
    Invoke Gemini to generate domain context, pain-point hypotheses,
    assumptions, and persona-generation guidance.
    """
    diagnostics: Dict[str, Any] = {
        "status": "success",
        "provider": "google_gemini",
        "model": os.getenv("GEMINI_MODEL", "gemini-1.5-flash"),
        "issues": [],
    }

    gemini_client = llm or get_gemini_llm()

    fc_block = ""
    if founder_context:
        fc_cat = founder_context.get("customer_category") or "Not specified"
        fc_desc = founder_context.get("customer_description") or "Not specified"
        fc_prob = founder_context.get("problem_description") or "Not specified"
        fc_alts = ", ".join(founder_context.get("known_alternatives", [])) or "None identified"
        fc_block = f"""
FOUNDER CLAIM CONTEXT:
- Customer Category: {fc_cat}
- Customer Description: {fc_desc}
- Problem Stated: {fc_prob}
- Known Alternatives Today: {fc_alts}
"""

    prompt = f"""You are the startup customer research advisor for IndiValidate.
Empirical market research data for the following concept is currently absent or insufficient.
Your task is to generate general market context, customer pain-point hypotheses,
adoption barrier hypotheses, explicit model assumptions, and persona-generation guidance
to steer downstream synthetic customer persona generation.

BUSINESS IDEA:
{idea.strip()}

TARGET SEGMENT: {target_segment or 'General prospective customers'}
LOCATION: {location or 'India'}
CATEGORY: {category or 'General Business'}
{fc_block}
STRICT REQUIREMENTS:
1. Provide a realistic market overview describing the industry dynamics and user environment.
2. Outline 3-5 typical target customer profiles or roles.
3. Formulate 3-5 plausible pain-point hypotheses (daily frictions, workflow inefficiencies, unmet needs).
4. Formulate 3-5 adoption barrier hypotheses (switching costs, habit inertia, budget constraints, technical hurdles).
5. State 3-5 explicit assumptions that the downstream pipeline and founders must validate in the field.
6. Provide actionable persona-generation guidance for Mistral to ensure diverse, representative, and realistic archetypes.

Return ONLY a valid JSON object conforming to this structure:
{{
  "market_overview": "Comprehensive 2-4 sentence market landscape overview...",
  "target_customer_profiles": ["Profile 1 description", "Profile 2 description"],
  "pain_point_hypotheses": ["Friction 1", "Friction 2", "Friction 3"],
  "adoption_barrier_hypotheses": ["Barrier 1", "Barrier 2", "Barrier 3"],
  "explicit_assumptions": ["Assumption 1 requiring human validation", "Assumption 2"],
  "persona_generation_guidance": ["Guidance point 1 for Mistral", "Guidance point 2"]
}}
"""

    # 1. Try native schema-constrained output
    if hasattr(gemini_client, "with_structured_output"):
        try:
            structured_chain = gemini_client.with_structured_output(GeminiFallbackContext)
            result = structured_chain.invoke(prompt)
            if isinstance(result, GeminiFallbackContext):
                return result, diagnostics
            if isinstance(result, dict):
                return GeminiFallbackContext.model_validate(result), diagnostics
        except Exception as e:
            diagnostics["issues"].append(f"Structured output attempt failed: {e}")

    # 2. Raw invocation + robust JSON parsing
    raw_response = gemini_client.invoke(prompt)
    raw_content = raw_response.content if hasattr(raw_response, "content") else str(raw_response)

    parsed_dict = parse_json_robust(raw_content)
    if isinstance(parsed_dict, dict):
        gemini_ctx = GeminiFallbackContext.model_validate(parsed_dict)
        return gemini_ctx, diagnostics

    raise ValueError(f"Failed to parse Gemini fallback context JSON: {raw_content[:200]}")


def gemini_context_node(state: MarketState) -> Dict[str, Any]:
    """
    LangGraph node executed when empirical evidence is absent or insufficient.
    Invokes Gemini to generate startup context and hypotheses for Mistral.
    """
    idea = state.get("idea", "")
    target = state.get("target_segment", "")
    location = state.get("location", "")
    category = state.get("category", "")
    founder_context = state.get("founder_context")
    custom_llm = state.get("gemini_llm")

    print("\n>>> GEMINI FALLBACK CONTEXT GENERATION (Evidence Absent / Insufficient)")

    try:
        if not has_gemini_api_key() and custom_llm is None:
            print("    Gemini Context: Skipped (no GEMINI_API_KEY configured in environment)")
            return {
                "evidence_sufficient": False,
                "gemini_context": None,
                "gemini_context_diagnostics": {
                    "status": "skipped",
                    "issues": ["GEMINI_API_KEY not configured in environment."],
                },
            }

        ctx_obj, diag = generate_gemini_context(
            idea=idea,
            target_segment=target,
            location=location,
            category=category,
            founder_context=founder_context,
            llm=custom_llm,
        )

        print(f"    Gemini Context: Generated {len(ctx_obj.pain_point_hypotheses)} pain-point hypotheses & {len(ctx_obj.adoption_barrier_hypotheses)} barrier hypotheses")
        print(f"    Guidance: {len(ctx_obj.persona_generation_guidance)} persona directives ready for Mistral")

        return {
            "evidence_sufficient": False,
            "gemini_context": ctx_obj.model_dump(),
            "gemini_context_diagnostics": diag,
        }
    except Exception as e:
        print(f"    Gemini Context Error: {e}")
        return {
            "evidence_sufficient": False,
            "gemini_context": None,
            "gemini_context_diagnostics": {
                "status": "failed",
                "issues": [f"Gemini fallback generation error: {e}"],
            },
        }
