"""
app.nodes.persona_evaluation
----------------------------
Evidence-grounded multi-persona evaluation and intent simulation node (Step 10).

Simulates individual customer evaluations for a business idea across a diverse
population of synthetic personas.

STRICT BOUNDARIES:
1. Evaluations represent simulated customer reactions, NOT real-world customer surveys.
2. Simulated purchase intent is an ordinal 1-10 scale, NOT a real-world conversion probability.
3. Every cited evidence ID must exist in retrieved evidence records; no invented citations.
4. If price is unspecified, pricing assessments are explicitly marked conditional and unverified.
"""

import concurrent.futures
import json
import os
import random
import re
import threading
import time
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Union

from app.llm import (
    MistralRateLimitException,
    calculate_backoff,
    classify_mistral_error,
    get_llm,
    has_mistral_api_key,
    is_terminal_error,
)

from app.schemas.persona import Persona
from app.schemas.persona_evaluation import PersonaEvaluation
from app.rag.retriever import EvidenceRetriever, build_evidence_context
from app.rag.vector_store import ChromaVectorStore
from app.state import MarketState


# ------------------------------------------------------------------
# 1. Price Specification Detection
# ------------------------------------------------------------------

def is_price_specified(idea_text: str) -> bool:
    """
    Detect whether the business idea includes an explicit proposed price or fee.
    """
    if not idea_text:
        return False
    # Look for currency symbols, numeric pricing terms, or subscription tiers
    patterns = [
        r"(?:rs\.?|inr|₹|\$|€|£)\s*\d+",
        r"\d+\s*(?:rupees|rs|inr|usd|dollars)",
        r"(?:priced\s+at|subscription\s+of|cost\s+of|fee\s+of)\s*(?:rs\.?|inr|₹|\$)?\s*\d+",
        r"per\s+(?:month|year|user|unit)\s*(?:at|for)?\s*(?:rs\.?|inr|₹|\$)?\s*\d+",
    ]
    combined = "|".join(patterns)
    return bool(re.search(combined, idea_text, flags=re.IGNORECASE))


# ------------------------------------------------------------------
# 2. JSON Cleaning and Response Parsing
# ------------------------------------------------------------------

def _clean_json_response(raw_text: str) -> str:
    """Extract clean JSON string from LLM output, stripping code blocks and fences."""
    from app.utils.json_utils import extract_json_candidate
    return extract_json_candidate(raw_text)


def _parse_and_validate_evaluation(
    raw_response: str,
    persona_id: str,
    valid_evidence_ids: Set[str],
    price_unspecified: bool,
) -> Tuple[Optional[PersonaEvaluation], List[str]]:
    """
    Parse and validate a single PersonaEvaluation JSON response.
    Enforces evidence citation integrity and price conditionality.
    """
    issues: List[str] = []
    from app.utils.json_utils import parse_json_robust

    try:
        data = parse_json_robust(raw_response)
    except Exception as e:
        return None, [f"JSON decoding error for persona '{persona_id}': {e}"]

    if not isinstance(data, dict):
        return None, [f"Expected JSON dictionary for persona '{persona_id}', got {type(data)}."]

    # Enforce persona_id link
    data["persona_id"] = persona_id

    # Enforce price conditionality if price was unspecified
    if price_unspecified:
        data["price_is_conditional"] = True
        if not data.get("pricing_considerations"):
            data["pricing_considerations"] = "Conditional: product price unspecified in proposal; needs further validation."

    # Validate evidence citations against actual available evidence IDs
    raw_citations = data.get("supporting_evidence_ids", [])
    verified_citations = []
    unsupported_assumptions = data.get("unsupported_assumptions", []) or []

    for cid in raw_citations:
        cid_clean = str(cid).strip()
        if cid_clean in valid_evidence_ids:
            verified_citations.append(cid_clean)
        else:
            unsupported_assumptions.append(f"Unverified evidence citation removed: {cid_clean}")

    data["supporting_evidence_ids"] = verified_citations
    data["unsupported_assumptions"] = unsupported_assumptions

    # Enforce simulation flags
    data["is_simulation"] = True
    data["is_conversion_probability"] = False

    try:
        eval_obj = PersonaEvaluation.model_validate(data)
        return eval_obj, issues
    except Exception as val_err:
        return None, [f"Validation failure for persona '{persona_id}': {val_err}"]


# ------------------------------------------------------------------
# 3. Prompt Construction
# ------------------------------------------------------------------

def _build_evaluation_prompt(
    idea: str,
    persona: Persona,
    evidence_context_str: str,
    price_unspecified: bool,
    founder_context: Optional[Dict[str, Any]] = None,
) -> str:
    """
    Construct an objective evaluation prompt tailored to a single persona.
    """
    p_dict = persona.model_dump()
    bh = p_dict.get("behavioral_hypotheses", {})

    b2b_info = ""
    if persona.b2b_attributes:
        b2b = persona.b2b_attributes
        b2b_info = f"""
ORGANIZATIONAL / B2B PROFILE:
- Job Role: {b2b.job_role or 'N/A'}
- Organization Size: {b2b.organization_size or 'N/A'}
- Purchasing Authority: {b2b.purchasing_authority or 'N/A'}
- Procurement Constraints: {', '.join(b2b.procurement_constraints) if b2b.procurement_constraints else 'None listed'}
"""

    pricing_directive = ""
    if price_unspecified:
        pricing_directive = """
PRICING INSTRUCTION:
The business idea does NOT specify a concrete product price.
- Set price_is_conditional = true.
- Treat pricing assessment as conditional upon future testing.
- DO NOT invent a specific price or assume affordability without evidence.
- Note pricing uncertainty in evidence_gaps.
"""
    else:
        pricing_directive = """
PRICING INSTRUCTION:
A price is specified in the idea. Evaluate willingness-to-pay and affordability based on this persona's income/budget constraints.
"""

    founder_block = ""
    if founder_context:
        fc_prob = founder_context.get("problem_description") or ""
        fc_alts = ", ".join(founder_context.get("known_alternatives", [])) or "None listed"
        fc_price = founder_context.get("expected_price")
        price_line = f"\n- Founder Proposed Target Price: {fc_price} [UNVERIFIED FOUNDER HYPOTHESIS]" if fc_price else ""
        founder_block = f"""
FOUNDER CONTEXT (SELF-REPORTED CLAIMS — FOR HYPOTHESIS TESTING ONLY):
- Problem Stated by Founder: {fc_prob}
- Existing Workarounds / Alternatives Mentioned: {fc_alts}{price_line}
(NOTE: Founder claims are unverified context. validation_notes are strictly excluded. Do not cite founder claims as empirical evidence.)
"""

    prompt = f"""You are an objective evaluation simulator for IndiValidate.
Your task is to simulate how a specific customer persona would realistically evaluate a proposed business idea.

PROPOSED BUSINESS IDEA:
{idea}
{founder_block}
PERSONA CONTEXT (Persona ID: {persona.persona_id}):
- Name: {persona.name}
- Segment: {persona.segment}
- Customer Type: {persona.customer_type.value}
- Demographics: Age Band: {persona.age_band or 'N/A'}, Occupation: {persona.occupation or 'N/A'}, Education: {persona.education_level or 'N/A'}, Income Band: {persona.income_band or 'N/A'}
- Household Context: {persona.household_context or 'N/A'} (Size: {persona.household_size or 'N/A'})
{b2b_info}
BEHAVIORAL HYPOTHESES (1-10 Scales):
- Price Sensitivity: {bh.get('price_sensitivity', 'N/A')}/10
- Convenience Preference: {bh.get('convenience_preference', 'N/A')}/10
- Brand Trust Importance: {bh.get('brand_trust_importance', 'N/A')}/10
- Risk Tolerance: {bh.get('risk_tolerance', 'N/A')}/10
- Digital Adoption: {bh.get('digital_adoption', 'N/A')}/10

CORE NEEDS & PAIN POINTS:
- Needs: {', '.join(persona.goals_and_needs) if persona.goals_and_needs else 'None specified'}
- Pain Points: {', '.join(persona.pain_points) if persona.pain_points else 'None specified'}
- Constraints: {', '.join(persona.purchasing_constraints) if persona.purchasing_constraints else 'None specified'}
- Typical Usage Context: {persona.usage_context or 'N/A'}

RELEVANT MARKET EVIDENCE CONTEXT:
{evidence_context_str}

{pricing_directive}

EVALUATION PRINCIPLES:
1. Objectivity: Do not assume the business idea is good or bad. Ground the evaluation strictly in this persona's specific life/work context, constraints, and habits. Different personas must reach different conclusions.
2. Anti-Stereotyping: Do not deduce interest solely from age, gender, or location stereotypes. Rely on their stated pain points and behavioral profile.
3. Evidence Citation Integrity: In supporting_evidence_ids, cite ONLY chunk IDs that appear in the RELEVANT MARKET EVIDENCE CONTEXT above. Never invent evidence IDs.
4. Scale Definitions (Strict 1-10 Integers):
   - interest_score: 1 = Completely uninterested/irrelevant, 10 = Urgent relevance/high interest.
   - simulated_purchase_intent: 1 = Definitely would not purchase/adopt, 10 = Highly inclined to adopt if conditions met. (NOT a conversion probability).
   - perceived_value_score: 1 = Negligible value vs alternatives, 10 = Transformative improvement over alternatives.
   - affordability_score: 1 = Completely unaffordable budget barrier, 10 = Easily affordable / trivial expense.
   - adoption_barrier_score: 1 = Frictionless adoption, 10 = Prohibitive adoption barriers / high inertia.
5. If evidence is lacking or inconclusive, explicitly state this in evidence_gaps.

OUTPUT FORMAT:
Return ONLY a valid JSON object matching this schema:
{{
  "persona_id": "{persona.persona_id}",
  "interest_score": 7,
  "simulated_purchase_intent": 6,
  "perceived_value_score": 7,
  "affordability_score": 5,
  "adoption_barrier_score": 4,
  "positive_aspects": ["Compelling aspect 1", "Compelling aspect 2"],
  "negative_aspects": ["Drawback or concern 1"],
  "needs_addressed": ["Persona need satisfied"],
  "needs_unmet": ["Persona need left unaddressed"],
  "pricing_considerations": "Willingness to pay or conditional pricing comment",
  "price_is_conditional": {"true" if price_unspecified else "false"},
  "valued_features": ["Feature A", "Feature B"],
  "unnecessary_features": ["Feature C"],
  "reasons_for_assessment": "Comprehensive reasoning connecting persona constraints to the scores.",
  "supporting_persona_attributes": ["price_sensitivity", "occupation"],
  "supporting_evidence_ids": [],
  "unsupported_assumptions": ["Assumption regarding workflow change"],
  "evidence_gaps": ["Missing data on specific competitor pricing"],
  "is_simulation": true,
  "is_conversion_probability": false
}}
"""
    return prompt


class RateLimitCoordinator:
    """
    Coordinates outbound LLM requests across concurrent evaluation threads:
    1. Enforces inter-request spacing (pacing) to prevent sudden millisecond request bursts.
    2. Synchronizes cooldown across all threads whenever an HTTP 429 / code 1300 is encountered.
    """

    def __init__(self, min_spacing_seconds: Optional[float] = None):
        self._lock = threading.Lock()
        if min_spacing_seconds is not None:
            self._min_spacing = min_spacing_seconds
        else:
            try:
                self._min_spacing = float(os.getenv("MISTRAL_MIN_SPACING", "0.05"))
            except (ValueError, TypeError):
                self._min_spacing = 0.05
        self._last_request_time = 0.0
        self._cooldown_until = 0.0

    def wait_for_slot(self) -> None:
        """Wait until active rate-limit cooldown has elapsed and inter-request spacing is satisfied."""
        while True:
            with self._lock:
                now = time.time()
                cooldown_remaining = max(0.0, self._cooldown_until - now)
                spacing_remaining = max(0.0, (self._last_request_time + self._min_spacing) - now)
                delay = max(cooldown_remaining, spacing_remaining)

                if delay <= 0:
                    self._last_request_time = time.time()
                    return

            time.sleep(min(delay, 0.4))

    def trigger_cooldown(self, retry_after: Optional[float] = None, attempt: int = 1) -> float:
        """
        Record a rate-limit event and set shared cooldown for all worker threads.
        Returns the applied cooldown duration in seconds.
        """
        with self._lock:
            wait = calculate_backoff(attempt=attempt, retry_after=retry_after, max_backoff=25.0)
            now = time.time()
            self._cooldown_until = max(self._cooldown_until, now + wait)
            return wait


# ------------------------------------------------------------------
# 4. Master Persona Evaluation Function
# ------------------------------------------------------------------

def evaluate_personas(
    idea: str,
    personas: List[Union[Persona, Dict[str, Any]]],
    retriever: Optional[EvidenceRetriever] = None,
    vector_store: Optional[ChromaVectorStore] = None,
    research_evidence: Optional[Dict[str, Any]] = None,
    retrieved_chunks: Optional[List[Any]] = None,
    llm: Optional[Any] = None,
    max_retries: int = 2,
    top_k_evidence: int = 4,
    max_concurrency: int = 3,
    founder_context: Optional[Dict[str, Any]] = None,
    cached_evaluations: Optional[List[Union[PersonaEvaluation, Dict[str, Any]]]] = None,
) -> Tuple[List[PersonaEvaluation], Dict[str, Any]]:
    """
    Evaluate business idea separately across each generated persona.

    Parameters:
    - idea: The proposed business idea.
    - personas: List of Persona objects or dictionaries.
    - retriever: Optional EvidenceRetriever instance.
    - vector_store: Optional ChromaVectorStore for dynamic queries.
    - research_evidence: Optional raw evidence dictionary from state.
    - retrieved_chunks: Optional pre-retrieved evidence chunks.
    - llm: Injected LLM or callable (Mistral by default).
    - max_retries: Retry attempts for malformed LLM responses or transient rate limits per persona.
    - top_k_evidence: Number of evidence chunks to retrieve per persona.
    - max_concurrency: Bounded parallel workers (default 3 to respect API rate limits).
    - cached_evaluations: Optional previously completed evaluations to reuse without calling the LLM.

    Returns:
    - (evaluations_list, diagnostics_dict)
    """
    total_personas = len(personas) if personas else 0
    diagnostics: Dict[str, Any] = {
        "total_personas": total_personas,
        "evaluated_count": 0,
        "evaluation_failures_count": 0,
        "price_specified_in_idea": False,
        "score_averages": {},
        "vector_store_grounding_status": "uninitialized",
        "concurrency": max_concurrency,
        "evaluation_time_seconds": 0.0,
        "rate_limit_encountered": False,
        "retry_after": None,
        "reused_count": 0,
        "issues": [],
    }

    if not idea or not idea.strip():
        raise ValueError("Business idea string cannot be empty.")

    if not personas:
        return [], diagnostics

    # 1. Check whether price is specified in idea
    price_unspecified = not is_price_specified(idea)
    diagnostics["price_specified_in_idea"] = not price_unspecified

    # 2. Map existing cached evaluations if provided for safe stage reuse
    cached_map: Dict[str, PersonaEvaluation] = {}
    if cached_evaluations:
        for ce in cached_evaluations:
            try:
                if isinstance(ce, PersonaEvaluation):
                    cached_map[ce.persona_id] = ce
                elif isinstance(ce, dict) and "persona_id" in ce:
                    cached_map[ce["persona_id"]] = PersonaEvaluation.model_validate(ce)
            except Exception:
                pass

    # 3. Resolve LLM provider with bounded timeout
    if llm is None:
        if not has_mistral_api_key():
            diagnostics["issues"].append("Mistral API key not found in environment (MISTRAL_API_KEY).")
            return [], diagnostics

        llm = get_llm(
            temperature=0.3,  # lower temperature for objective evaluation
            timeout=45.0,  # bounded timeout to prevent socket hangs
            max_retries=1,
        )

    # 4. Setup retriever if vector store provided and available
    active_retriever = retriever
    if active_retriever is None and vector_store is not None:
        try:
            col_info = vector_store.get_collection_info()
            if col_info.get("count", 0) > 0:
                active_retriever = EvidenceRetriever(vector_store=vector_store)
                diagnostics["vector_store_grounding_status"] = "active"
            else:
                diagnostics["vector_store_grounding_status"] = "empty_collection_fallback_to_state_chunks"
        except Exception as e:
            diagnostics["issues"].append(f"Vector store unavailable for evaluation: {e}")
            diagnostics["vector_store_grounding_status"] = "unavailable_fallback_to_state_chunks"
            active_retriever = None
    elif active_retriever is not None:
        diagnostics["vector_store_grounding_status"] = "active"
    else:
        diagnostics["vector_store_grounding_status"] = "none_provided_fallback_to_state_chunks"

    # Collect known evidence chunks and IDs for verification
    base_evidence_ids: Set[str] = set()
    if retrieved_chunks:
        for chk in retrieved_chunks:
            if hasattr(chk, "chunk_id"):
                base_evidence_ids.add(chk.chunk_id)
            elif isinstance(chk, dict) and "chunk_id" in chk:
                base_evidence_ids.add(chk["chunk_id"])

    # Also collect IDs from normalized / cleaned evidence if passed
    if research_evidence:
        for key in ["cleaned_evidence", "normalized_evidence"]:
            for item in research_evidence.get(key, []):
                eid = item.get("evidence_id") if isinstance(item, dict) else getattr(item, "evidence_id", None)
                if eid:
                    base_evidence_ids.add(str(eid))

    # Pre-build fallback context if retrieved_chunks is present
    fallback_context_str: Optional[str] = None
    if retrieved_chunks:
        try:
            fallback_context_str = build_evidence_context(retrieved_chunks[:top_k_evidence])
        except Exception:
            fallback_context_str = "No specific retrieved evidence available."

    # Thread-safe synchronization, rate-limit coordinator, and caching structures
    coordinator = RateLimitCoordinator()
    retrieval_cache: Dict[str, Tuple[str, Set[str]]] = {}
    cache_lock = threading.Lock()
    print_lock = threading.Lock()
    diag_lock = threading.Lock()
    completed_counter = [0]
    t_overall_start = time.time()

    def _evaluate_single_persona(
        idx: int,
        p_item: Any,
    ) -> Tuple[int, Optional[PersonaEvaluation], List[str]]:
        """Worker function evaluating a single persona with isolated retries and timing."""
        try:
            if isinstance(p_item, Persona):
                persona_obj = p_item
            elif isinstance(p_item, dict):
                persona_obj = Persona.model_validate(p_item)
            else:
                return idx, None, [f"Skipping invalid persona item type: {type(p_item)}"]
        except Exception as e:
            return idx, None, [f"Persona validation error: {e}"]

        p_id = persona_obj.persona_id
        seg_desc = f"{persona_obj.segment} - {persona_obj.name}"
        display_idx = idx + 1

        # Check if already cached from an earlier stage/attempt
        if p_id in cached_map:
            cached_eval = cached_map[p_id]
            with print_lock:
                completed_counter[0] += 1
                done_cnt = completed_counter[0]
                tot_elapsed = time.time() - t_overall_start
                print(f"    Evaluating persona [{display_idx}/{total_personas}] '{p_id}' ({seg_desc})... [REUSED FROM CACHE] ({cached_eval.interest_score}/10 intent: {cached_eval.simulated_purchase_intent}/10) [Completed: {done_cnt}/{total_personas}]")
            return idx, cached_eval, []

        if effective_concurrency == 1:
            print(f"    Evaluating persona [{display_idx}/{total_personas}] '{p_id}' ({seg_desc})... ", end="", flush=True)

        t_start = time.time()
        local_issues: List[str] = []
        valid_chunk_ids_for_persona = set(base_evidence_ids)

        # Retrieve persona-specific evidence with thread-safe query caching
        context_str = "No specific retrieved evidence available."
        if active_retriever is not None and active_retriever.vector_store.count() > 0:
            query = f"{idea} {persona_obj.segment} {persona_obj.occupation or ''}".strip()
            with cache_lock:
                cached = retrieval_cache.get(query)
            if cached is not None:
                context_str, cached_ids = cached
                valid_chunk_ids_for_persona.update(cached_ids)
            else:
                try:
                    ret_res = active_retriever.retrieve(query=query, top_k=top_k_evidence)
                    if ret_res.chunks:
                        context_str = build_evidence_context(ret_res)
                        ret_ids = {c.chunk_id for c in ret_res.chunks}
                        valid_chunk_ids_for_persona.update(ret_ids)
                        with cache_lock:
                            retrieval_cache[query] = (context_str, ret_ids)
                    else:
                        with cache_lock:
                            retrieval_cache[query] = (context_str, set())
                except Exception as ret_err:
                    local_issues.append(f"Retrieval warning for persona '{p_id}': {ret_err}.")
                    if fallback_context_str:
                        context_str = fallback_context_str
        elif fallback_context_str:
            context_str = fallback_context_str

        # Build prompt
        prompt = _build_evaluation_prompt(
            idea=idea,
            persona=persona_obj,
            evidence_context_str=context_str,
            price_unspecified=price_unspecified,
            founder_context=founder_context,
        )

        # Execute LLM with paced concurrency, bounded exponential backoff, and retry-after respect
        eval_result: Optional[PersonaEvaluation] = None
        attempt = 0
        # Bound retries per persona: 1 to 3 attempts, never indefinite
        max_eval_retries = max(1, min(max_retries, 3))

        while attempt <= max_eval_retries and eval_result is None:
            attempt += 1
            try:
                # Pacing: avoid request bursts and respect active rate-limit cooldown
                coordinator.wait_for_slot()

                if hasattr(llm, "invoke"):
                    res = llm.invoke(prompt)
                    raw_text = res.content if hasattr(res, "content") else str(res)
                elif callable(llm):
                    raw_text = llm(prompt)
                else:
                    raw_text = str(llm)

                parsed_eval, p_issues = _parse_and_validate_evaluation(
                    raw_response=raw_text,
                    persona_id=p_id,
                    valid_evidence_ids=valid_chunk_ids_for_persona,
                    price_unspecified=price_unspecified,
                )
                if p_issues:
                    local_issues.extend(p_issues)

                if parsed_eval is not None:
                    eval_result = parsed_eval
                    break
            except Exception as e:
                err_diag = classify_mistral_error(e)
                if err_diag["classification"] == "rate_limit":
                    with diag_lock:
                        diagnostics["rate_limit_encountered"] = True
                        if err_diag.get("retry_after"):
                            diagnostics["retry_after"] = err_diag["retry_after"]

                    if attempt <= max_eval_retries:
                        # Bounded exponential backoff with jitter respecting server's retry-after
                        cooldown = coordinator.trigger_cooldown(
                            retry_after=err_diag.get("retry_after"),
                            attempt=attempt,
                        )
                        time.sleep(cooldown)

                local_issues.append(f"LLM attempt {attempt} failed for persona '{p_id}': {err_diag['user_message']}")
                if err_diag["is_terminal"]:
                    break

        elapsed = time.time() - t_start
        if effective_concurrency == 1:
            if eval_result is not None:
                print(f"done ({elapsed:.1f}s | interest: {eval_result.interest_score}/10, intent: {eval_result.simulated_purchase_intent}/10)")
            else:
                print(f"FAILED ({elapsed:.1f}s)")
        else:
            with print_lock:
                completed_counter[0] += 1
                done_cnt = completed_counter[0]
                tot_elapsed = time.time() - t_overall_start
                if eval_result is not None:
                    print(f"    Evaluating persona [{display_idx}/{total_personas}] '{p_id}' ({seg_desc})... done ({elapsed:.1f}s | interest: {eval_result.interest_score}/10, intent: {eval_result.simulated_purchase_intent}/10) [Completed: {done_cnt}/{total_personas} | Elapsed: {tot_elapsed:.1f}s]")
                else:
                    print(f"    Evaluating persona [{display_idx}/{total_personas}] '{p_id}' ({seg_desc})... FAILED ({elapsed:.1f}s) [Completed: {done_cnt}/{total_personas} | Elapsed: {tot_elapsed:.1f}s]")

        if eval_result is None:
            local_issues.append(f"Evaluation failed for persona '{p_id}' after {attempt} attempts.")

        return idx, eval_result, local_issues

    results: List[Optional[PersonaEvaluation]] = [None] * total_personas
    effective_concurrency = max(1, min(max_concurrency, total_personas))

    # Pre-populate any existing cached evaluations
    reused_count = 0
    pending_indices = []
    for i, p in enumerate(personas):
        p_id = p.persona_id if isinstance(p, Persona) else (p.get("persona_id") if isinstance(p, dict) else None)
        if p_id and p_id in cached_map:
            results[i] = cached_map[p_id]
            reused_count += 1
        else:
            pending_indices.append(i)

    diagnostics["reused_count"] = reused_count
    if reused_count > 0:
        print(f"    Reusing {reused_count} already-evaluated personas from prior execution; {len(pending_indices)} pending.")

    # 4. Dispatch pending evaluations (preserving deterministic result ordering)
    if pending_indices:
        if effective_concurrency > 1:
            print(f"    Evaluating {len(pending_indices)} personas with bounded concurrency (workers={effective_concurrency})...")

        if effective_concurrency == 1:
            for i in pending_indices:
                idx, res, p_issues = _evaluate_single_persona(i, personas[i])
                results[idx] = res
                if p_issues:
                    diagnostics["issues"].extend(p_issues)
        else:
            with concurrent.futures.ThreadPoolExecutor(max_workers=effective_concurrency) as executor:
                future_to_idx = {
                    executor.submit(_evaluate_single_persona, i, personas[i]): i
                    for i in pending_indices
                }
                for future in concurrent.futures.as_completed(future_to_idx):
                    try:
                        idx, res, p_issues = future.result()
                        results[idx] = res
                        if p_issues:
                            diagnostics["issues"].extend(p_issues)
                    except Exception as exc:
                        orig_idx = future_to_idx[future]
                        diagnostics["issues"].append(f"Worker exception for persona at index {orig_idx}: {exc}")

    evaluations: List[PersonaEvaluation] = [r for r in results if r is not None]
    total_eval_time = time.time() - t_overall_start
    diagnostics["evaluated_count"] = len(evaluations)
    diagnostics["evaluation_failures_count"] = total_personas - len(evaluations)
    diagnostics["evaluation_time_seconds"] = round(total_eval_time, 2)

    # Compute score distributions if evaluations exist
    if evaluations:
        diagnostics["score_averages"] = {
            "avg_interest_score": round(sum(e.interest_score for e in evaluations) / len(evaluations), 2),
            "avg_simulated_purchase_intent": round(sum(e.simulated_purchase_intent for e in evaluations) / len(evaluations), 2),
            "avg_perceived_value_score": round(sum(e.perceived_value_score for e in evaluations) / len(evaluations), 2),
            "avg_affordability_score": round(sum(e.affordability_score for e in evaluations) / len(evaluations), 2),
            "avg_adoption_barrier_score": round(sum(e.adoption_barrier_score for e in evaluations) / len(evaluations), 2),
        }

    return evaluations, diagnostics


# ------------------------------------------------------------------
# 5. LangGraph Node Integration
# ------------------------------------------------------------------

def evaluate_personas_node(state: MarketState) -> Dict[str, Any]:
    """
    LangGraph node executing multi-persona simulated evaluation and intent simulation.
    Supports stage reuse across pipeline retries and bounded backoff.
    """
    idea = state.get("idea", "")
    personas = state.get("personas", [])
    eval_flag = state.get("evaluate_personas", True)

    if not eval_flag:
        return {
            "persona_evaluations": [],
            "persona_evaluation_diagnostics": {"status": "skipped", "issues": ["evaluate_personas is False"]},
        }

    if not personas:
        print("\n>>> MULTI-PERSONA EVALUATION (Step 10): Skipped (No personas generated).")
        return {
            "persona_evaluations": [],
            "persona_evaluation_diagnostics": {
                "total_personas": 0,
                "evaluated_count": 0,
                "issues": ["No personas found in state to evaluate."],
            },
        }

    # Full stage reuse check: if all personas are already evaluated in state, reuse immediately
    existing_evals = state.get("persona_evaluations") or []
    if existing_evals and len(existing_evals) == len(personas):
        print(f"\n>>> MULTI-PERSONA EVALUATION (Step 10): Reusing all {len(existing_evals)} completed evaluations from state.")
        existing_diag = state.get("persona_evaluation_diagnostics") or {
            "total_personas": len(personas),
            "evaluated_count": len(existing_evals),
            "evaluation_failures_count": 0,
            "status": "reused_from_cache",
        }
        return {
            "persona_evaluations": existing_evals,
            "persona_evaluation_diagnostics": existing_diag,
        }

    llm = state.get("evaluation_llm") or state.get("llm")

    # Pass vector store if available and compatible
    vector_store = None
    persist_dir = state.get("chroma_persist_dir", "data/chroma")
    col_name = state.get("chroma_collection_name")
    if not col_name:
        col_name = state.get("vector_store_diagnostics", {}).get("collection_name", "market_evidence_chunks")

    vs_diag = state.get("vector_store_diagnostics", {})
    vs_issues = vs_diag.get("issues", [])
    vs_count = state.get("vector_store_count", 0)

    if vs_count > 0 and not any("error" in str(i).lower() for i in vs_issues):
        try:
            vs = ChromaVectorStore(persist_directory=persist_dir, collection_name=col_name)
            if vs.count() > 0:
                vector_store = vs
        except Exception as e:
            vector_store = None
            print(f"    Vector store unavailable for evaluation: {e}")
    else:
        vector_store = None
        if vs_issues:
            print(f"    Vector storage unavailable ({vs_issues[0]}); using pre-retrieved state chunks for grounding.")
        elif vs_count == 0:
            print("    Vector storage contains 0 chunks; using pre-retrieved state chunks for grounding.")

    retrieved_chunks = state.get("retrieved_chunks", []) or state.get("document_chunks", [])
    research_evidence = {
        "census_evidence": state.get("census_evidence", []),
        "plfs_evidence": state.get("plfs_evidence", []),
        "reddit_evidence": state.get("reddit_evidence", []),
        "trends_evidence": state.get("trends_evidence", []),
        "cleaned_evidence": state.get("cleaned_evidence", []),
        "normalized_evidence": state.get("normalized_evidence", []),
    }

    concurrency = state.get("evaluation_concurrency", 3)
    founder_context = state.get("founder_context")

    print("\n>>> MULTI-PERSONA EVALUATION & INTENT SIMULATION (Step 10)")
    try:
        evals, diag = evaluate_personas(
            idea=idea,
            personas=personas,
            vector_store=vector_store,
            research_evidence=research_evidence,
            retrieved_chunks=retrieved_chunks,
            llm=llm,
            max_concurrency=concurrency,
            founder_context=founder_context,
            cached_evaluations=existing_evals,
        )

        evals_data = [e.model_dump() for e in evals]
        print(f"    Evaluations Completed: {len(evals_data)} / {len(personas)} personas")
        if diag.get("score_averages"):
            avgs = diag["score_averages"]
            print(f"    Average Interest: {avgs.get('avg_interest_score')}/10 | Purchase Intent: {avgs.get('avg_simulated_purchase_intent')}/10")
            print(f"    Average Value: {avgs.get('avg_perceived_value_score')}/10 | Adoption Barrier: {avgs.get('avg_adoption_barrier_score')}/10")

        # If rate limit caused incomplete evaluations, raise MistralRateLimitException with partial progress
        if diag.get("rate_limit_encountered") and len(evals_data) < len(personas):
            raise MistralRateLimitException(
                message="Mistral API rate limit reached. Check your organization’s API limits and usage, then retry after the indicated wait.",
                retry_after=diag.get("retry_after"),
                partial_evaluations=evals_data,
                diagnostics=diag,
            )

        return {
            "persona_evaluations": evals_data,
            "persona_evaluation_diagnostics": diag,
        }
    except MistralRateLimitException:
        raise
    except Exception as e:
        print(f"    Evaluation Execution Error: {e}")
        diag_err = classify_mistral_error(e)
        if diag_err["classification"] == "rate_limit":
            raise MistralRateLimitException(
                message=diag_err["user_message"],
                retry_after=diag_err.get("retry_after"),
                partial_evaluations=[],
                diagnostics={"issues": [diag_err["user_message"]]},
            ) from e
        return {
            "persona_evaluations": [],
            "persona_evaluation_diagnostics": {
                "total_personas": len(personas),
                "evaluated_count": 0,
                "issues": [f"Persona evaluation node error: {e}"],
            },
        }
