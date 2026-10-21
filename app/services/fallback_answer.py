"""
app.services.fallback_answer
----------------------------
Reusable service layer providing LLM-native answers and fallbacks for market validation questions.

When research tools (Reddit, Google Trends, Census, PLFS, web search) cannot provide useful data,
this service allows the LLM to reason independently using its learned knowledge without forcing
the system to return "no data available".

Epistemic Grounding Rules:
1. Basis Classification:
   - 'retrieved_evidence': Evidence is sufficient and relevant; answer is strictly grounded in retrieved facts.
   - 'mixed': Partial evidence exists; retrieved evidence is explicitly distinguished from model-generated inferences.
   - 'model_knowledge': Evidence is missing, irrelevant, or unavailable; LLM answers using learned reasoning.
2. Independent LLM Rules:
   - LLM explains customer needs, likely use cases, competitive considerations, positioning, risks, and hypotheses.
   - Never invent statistics, survey numbers, sample sizes, URLs, citations, or claims of live access.
   - Explicitly state when information (current market conditions, trends, prices, competitors) could not be verified.
   - If an answer depends on unavailable data, provide a reasoned hypothesis and state what needs external validation.
   - Treat simulated personas as simulations, not live interviews.
   - If external sources conflict, explain the divergence rather than concealing it.
"""

import json
import logging
import os
import re
from typing import Any, Dict, List, Optional, Set, Tuple, Union

from app.schemas.market_report import AnswerBasis, ResearchQuestionAnswer
from app.utils.json_utils import parse_json_robust, capture_failed_response_diagnostics

logger = logging.getLogger(__name__)

DEFAULT_RESEARCH_QUESTIONS: List[str] = [
    "What is the core customer problem, and what indicates real market demand or urgency?",
    "What existing alternatives, incumbents, or workarounds do customers currently rely on?",
    "What are the willingness-to-pay dynamics and realistic pricing considerations for this offering?",
    "What are the most critical customer adoption barriers, switching costs, or operational risks?",
    "What demographic, geographic, or industry trends support or constrain adoption?",
]

VALID_SOURCES = {"census_2011", "plfs_2025", "reddit", "google_trends", "web_search"}


def get_configured_llm(temperature: float = 0.3, timeout: float = 45.0, max_retries: int = 1) -> Optional[Any]:
    """
    Retrieve an instance of the configured Mistral LLM matching project defaults.
    Returns None if API credentials are not set.
    """
    from app.llm import get_llm, has_mistral_api_key

    if not has_mistral_api_key():
        return None

    try:
        return get_llm(
            temperature=temperature,
            timeout=timeout,
            max_retries=max_retries,
        )
    except Exception as exc:
        logger.warning("Failed to instantiate Mistral LLM: %s", exc)
        return None


def extract_evidence_items(
    evidence_data: Optional[Dict[str, Any]] = None,
    retrieved_chunks: Optional[List[Any]] = None,
) -> List[Dict[str, Any]]:
    """
    Normalize disparate evidence representations (raw records, cleaned records, chunks)
    into a flat list of evidence items with text and source.
    """
    items: List[Dict[str, Any]] = []

    # 1. Chunks
    if retrieved_chunks:
        for chunk in retrieved_chunks:
            text = getattr(chunk, "text", "") or (chunk.get("text") if isinstance(chunk, dict) else "")
            source = getattr(chunk, "source", "") or (chunk.get("source") if isinstance(chunk, dict) else "")
            chunk_id = getattr(chunk, "chunk_id", "") or (chunk.get("chunk_id") if isinstance(chunk, dict) else "")
            if text:
                items.append({
                    "text": str(text),
                    "source": str(source).lower() if source else "unknown",
                    "id": str(chunk_id),
                })

    # 2. Structured evidence data
    if evidence_data and isinstance(evidence_data, dict):
        for key, records in evidence_data.items():
            if not isinstance(records, list):
                continue
            src_hint = key.replace("_evidence", "")
            for r in records:
                if isinstance(r, dict):
                    # Check for text or indicator
                    text_parts = []
                    if "text" in r and r["text"]:
                        text_parts.append(str(r["text"]))
                    if "title" in r and r["title"]:
                        text_parts.append(str(r["title"]))
                    if "indicator" in r and r["indicator"]:
                        val = r.get("value", "")
                        unit = r.get("unit", "")
                        text_parts.append(f"{r['indicator']}: {val} {unit}".strip())
                    if "factual_summary" in r and r["factual_summary"]:
                        text_parts.append(str(r["factual_summary"]))

                    src = r.get("source") or src_hint
                    item_text = " | ".join(text_parts).strip()
                    if item_text:
                        items.append({
                            "text": item_text,
                            "source": str(src).lower(),
                            "id": str(r.get("evidence_id") or r.get("id") or ""),
                        })

    return items


def assess_evidence_sufficiency(
    question: str,
    evidence_items: List[Dict[str, Any]],
) -> Tuple[AnswerBasis, List[str], List[Dict[str, Any]]]:
    """
    Assess whether the collected evidence is relevant and sufficient for a given research question.
    Returns:
        (basis, supporting_sources, relevant_evidence_items)
    """
    if not evidence_items:
        return AnswerBasis.MODEL_KNOWLEDGE, [], []

    q_lower = question.lower()

    # Topic keyword associations for matching relevant evidence
    topic_keywords = {
        "problem": ["problem", "issue", "friction", "pain", "struggle", "downtime", "queue", "delay", "challenge", "bottleneck"],
        "demand": ["demand", "interest", "search", "trend", "growth", "volume", "popular", "adoption", "need"],
        "alternatives": ["alternative", "competitor", "substitute", "existing", "current", "incumbent", "workaround", "generator", "station", "legacy", "other"],
        "pricing": ["pric", "cost", "fee", "rate", "wage", "earning", "salary", "inr", "rupee", "afford", "expensive", "cheap", "wtp", "pay", "spend", "budget"],
        "barrier": ["barrier", "switching", "risk", "obstacle", "reliability", "trust", "unpredictable", "adoption", "hesitat", "inertia", "friction"],
        "demographic": ["population", "census", "labour", "employment", "worker", "graduate", "education", "district", "state", "urban", "rural", "demographic", "industry"],
    }

    relevant_items: List[Dict[str, Any]] = []
    represented_sources: Set[str] = set()

    for item in evidence_items:
        item_text = item["text"].lower()
        item_source = item["source"].lower()

        # Check keyword overlap between question concepts and item text
        matched_concept = False
        for category, kws in topic_keywords.items():
            if any(k in q_lower for k in kws) and any(k in item_text for k in kws):
                matched_concept = True
                break

        # Also direct word overlap (ignoring common stop words)
        q_words = set(re.findall(r"\b[a-z]{4,}\b", q_lower)) - {
            "what", "that", "this", "from", "with", "have", "been", "were", "indicate", "indicates",
            "realistic", "critical", "support", "constrain", "offering", "current", "currently"
        }
        item_words = set(re.findall(r"\b[a-z]{4,}\b", item_text))
        overlap = q_words & item_words

        if matched_concept or len(overlap) >= 2:
            relevant_items.append(item)
            if item_source in VALID_SOURCES:
                represented_sources.add(item_source)
            elif item_source:
                represented_sources.add(item_source)

    if not relevant_items:
        return AnswerBasis.MODEL_KNOWLEDGE, [], []

    # Guardrails:
    # 1. Operational claim cannot be solely supported by Google Trends
    operational_keywords = [
        "operational", "latency", "uptime", "downtime", "maintenance", "dispatch",
        "turnaround", "throughput", "infrastructure", "hardware", "breakdown",
        "fleet", "charging speed", "battery degradation", "grid", "power cutoff"
    ]
    # 2. Market-wide statistical claim cannot be solely supported by qualitative Reddit
    statistical_keywords = [
        "market share", "market size", "tam", "total addressable market",
        "statistically", "nationwide", "statewide", "cagr", "penetration rate",
        "population-wide", "majority of"
    ]

    is_operational = any(op in q_lower for op in operational_keywords)
    is_statistical = any(stat in q_lower for stat in statistical_keywords)

    only_trends = bool(represented_sources) and all("trends" in s.lower() for s in represented_sources)
    only_reddit = bool(represented_sources) and all("reddit" in s.lower() for s in represented_sources)

    # If we have strong empirical coverage with multiple relevant items
    # and direct factual sources:
    if len(relevant_items) >= 3 and len(represented_sources) >= 1:
        # If question is operational and only source is trends, downgrade to MIXED
        if is_operational and only_trends:
            return AnswerBasis.MIXED, sorted(list(represented_sources)), relevant_items
        # If question is statistical and only source is reddit, downgrade to MIXED
        if is_statistical and only_reddit:
            return AnswerBasis.MIXED, sorted(list(represented_sources)), relevant_items
        # High evidence coverage
        return AnswerBasis.RETRIEVED_EVIDENCE, sorted(list(represented_sources)), relevant_items

    # Partial evidence: some empirical matches exist, but they don't cover the full scope
    return AnswerBasis.MIXED, sorted(list(represented_sources)), relevant_items


def clean_and_sanitize_rqa(
    rqa: ResearchQuestionAnswer,
    allowed_sources: List[str],
) -> ResearchQuestionAnswer:
    """
    Sanitize and enforce epistemic integrity on a generated ResearchQuestionAnswer:
    - Never invent URLs, citations, or statistics.
    - If model_knowledge, force supporting_sources to empty and requires_external_validation to True.
    - If retrieved_evidence or mixed, filter supporting_sources to those actually verified.
    - If no verified supporting sources remain, downgrade to model_knowledge.
    - Remove hallucinated URLs or claims of live web search if unsupported.
    """
    basis = rqa.basis
    clean_sources = []
    if basis == AnswerBasis.MODEL_KNOWLEDGE:
        clean_sources = []
        requires_ext_val = True
    else:
        # Keep only verified available sources
        clean_sources = [s for s in rqa.supporting_sources if s in allowed_sources]
        if not clean_sources:
            # If evidence was supposed to be empirical or mixed, but no sources verified/available:
            basis = AnswerBasis.MODEL_KNOWLEDGE
            requires_ext_val = True
        else:
            requires_ext_val = rqa.requires_external_validation

    # Check for fabricated URLs (http://, https://, www.) in answer
    cleaned_answer = re.sub(r"https?://\S+|www\.\S+", "[Live URL omitted - unverified]", rqa.answer)

    # Clean limitations and assumptions
    assumptions = list(rqa.assumptions)
    limitations = list(rqa.limitations)

    if basis == AnswerBasis.MODEL_KNOWLEDGE:
        if not any("model knowledge" in a.lower() or "unverified" in a.lower() for a in assumptions):
            assumptions.insert(0, "Answer derived from pre-trained model knowledge without live external empirical data.")
        if not any("validation" in l.lower() or "unverified" in l.lower() for l in limitations):
            limitations.insert(0, "Empirical data was unavailable; claims must be externally validated before commercial reliance.")

    confidence = rqa.confidence
    if not confidence or confidence.strip() == "":
        confidence = "Moderate - Reasoned hypothesis based on general domain knowledge." if basis == AnswerBasis.MODEL_KNOWLEDGE else "High - Corroborated by empirical evidence."
    elif basis == AnswerBasis.MODEL_KNOWLEDGE and ("high" in confidence.lower() or "corroborat" in confidence.lower() or "empirical" in confidence.lower()):
        confidence = "Moderate - Reasoned hypothesis based on domain priors (empirical sources unavailable)."

    return ResearchQuestionAnswer(
        question=rqa.question.strip(),
        answer=cleaned_answer.strip(),
        basis=basis,
        supporting_sources=clean_sources,
        assumptions=assumptions,
        confidence=confidence.strip(),
        limitations=limitations,
        requires_external_validation=requires_ext_val,
    )


def build_deterministic_fallback_answer(
    question: str,
    idea: str,
    basis: AnswerBasis = AnswerBasis.MODEL_KNOWLEDGE,
    supporting_sources: Optional[List[str]] = None,
    relevant_evidence: Optional[List[Dict[str, Any]]] = None,
    note: str = "",
) -> ResearchQuestionAnswer:
    """
    Deterministic answer generator used when LLM call is unavailable, failed,
    or during fully offline testing.
    """
    sources = supporting_sources or []
    q_lower = question.lower()

    if basis == AnswerBasis.RETRIEVED_EVIDENCE and relevant_evidence:
        summary_snippets = [item["text"][:140] for item in relevant_evidence[:3]]
        ans = (
            f"Based on retrieved empirical data ({', '.join(sources)}), the proposal aligns with observed market records: "
            + "; ".join(summary_snippets) + "."
        )
        conf = "Moderate - Directly grounded in retrieved empirical records."
        assumptions = ["Retrieved empirical evidence accurately reflects the target demographic segment."]
        limitations = ["Empirical evidence is historical and may not reflect recent market dynamics."]
        req_val = False
    elif basis == AnswerBasis.MIXED and relevant_evidence:
        summary_snippets = [item["text"][:120] for item in relevant_evidence[:2]]
        ans = (
            f"Empirical evidence indicates {'; '.join(summary_snippets)}, while domain reasoning suggests "
            f"operational adoption for '{idea[:60]}' will depend on user willingness to adapt to new workflows. "
            f"Externally verified facts from {', '.join(sources)} are combined with structural market hypotheses."
        )
        conf = "Moderate - Combines available empirical observations with model domain hypotheses."
        assumptions = [
            "Empirical observations from available sources provide directional guidance.",
            "Market adoption hypotheses require customer interview confirmation.",
        ]
        limitations = ["Empirical records partially cover the market context but do not provide full validation."]
        req_val = True
    else:
        # Pure model knowledge fallback
        basis = AnswerBasis.MODEL_KNOWLEDGE
        sources = []
        ans = (
            f"No empirical research data was retrieved for this specific question. Reasoning from learned market domain knowledge: "
            f"For an initiative such as '{idea[:80]}', customer adoption depends on addressing immediate operational friction, "
            f"clear pricing transparency, and low switching barriers compared to incumbent workarounds. "
            f"Current market figures and competitor status could not be verified."
        )
        if note:
            ans += f" ({note})"
        conf = "Low-to-Moderate - Model reasoning without empirical research data."
        assumptions = [
            "Customer behavior follows standard industry economics and switching cost patterns.",
            "Live market conditions and pricing could not be empirically verified.",
        ]
        limitations = [
            "Independent model reasoning only; no external evidence was retrieved.",
            "Requires field validation with real prospective users before making capital commitments.",
        ]
        req_val = True

    return ResearchQuestionAnswer(
        question=question,
        answer=ans,
        basis=basis,
        supporting_sources=sources,
        assumptions=assumptions,
        confidence=conf,
        limitations=limitations,
        requires_external_validation=req_val,
    )


def generate_fallback_answer(
    question: str,
    idea: str,
    basis: AnswerBasis,
    supporting_sources: List[str],
    evidence_items: List[Dict[str, Any]],
    llm: Optional[Any] = None,
) -> ResearchQuestionAnswer:
    """
    Generate an answer to a single research question using LLM or deterministic fallback.
    Maintains strict epistemic rules and schema compliance.
    """
    if llm is None:
        llm = get_configured_llm()

    if llm is None:
        return build_deterministic_fallback_answer(
            question=question,
            idea=idea,
            basis=basis,
            supporting_sources=supporting_sources,
            relevant_evidence=evidence_items,
            note="Configured LLM was not available.",
        )

    # Format evidence context
    evidence_context_str = ""
    if evidence_items:
        formatted = []
        for idx, item in enumerate(evidence_items[:5], 1):
            formatted.append(f"[{idx}] Source: {item['source'].upper()} (ID: {item.get('id', 'N/A')}): {item['text']}")
        evidence_context_str = "\n".join(formatted)
    else:
        evidence_context_str = "None available (all research sources returned empty or irrelevant results)."

    basis_instruction = ""
    if basis == AnswerBasis.RETRIEVED_EVIDENCE:
        basis_instruction = (
            "BASIS: retrieved_evidence.\n"
            "Sufficient empirical evidence was found. Ground your answer strictly in the provided evidence. "
            "List only the actual supporting sources from the provided evidence. Do NOT add sources not provided."
        )
    elif basis == AnswerBasis.MIXED:
        basis_instruction = (
            "BASIS: mixed.\n"
            "Partial empirical evidence is available. Combine the retrieved evidence with your domain reasoning. "
            "You MUST clearly distinguish externally supported findings from your own model-generated inferences. "
            "Only include actual sources from the provided evidence in supporting_sources."
        )
    else:
        basis_instruction = (
            "BASIS: model_knowledge.\n"
            "Research sources returned no useful data for this question. "
            "Answer independently using your learned knowledge and reasoning (like ChatGPT). "
            "DO NOT say 'no data available'. Explain customer needs, likely use cases, competitive considerations, "
            "product positioning, possible risks, and hypotheses. "
            "CRITICAL: Never invent statistics, survey numbers, sample sizes, URLs, or citations. "
            "Explicitly state that live market conditions, current trends, and prices could not be verified. "
            "Set supporting_sources to an empty list []. Set requires_external_validation to true."
        )

    prompt = f"""You are an objective market-validation analyst.

BUSINESS IDEA UNDER EVALUATION:
"{idea}"

RESEARCH QUESTION:
"{question}"

RETRIEVED EVIDENCE:
{evidence_context_str}

{basis_instruction}

OUTPUT REQUIREMENTS:
Return ONLY a valid JSON object matching this exact schema:
{{
  "question": "{question}",
  "answer": "Detailed, thorough answer strictly adhering to the basis rules above.",
  "basis": "{basis.value}",
  "supporting_sources": {json.dumps(supporting_sources if basis != AnswerBasis.MODEL_KNOWLEDGE else [])},
  "assumptions": ["List of explicit assumptions made in this answer"],
  "confidence": "Qualitative confidence level with explanation (e.g. 'High - Supported by census metrics' or 'Moderate - Based on industry economics')",
  "limitations": ["Known limitations, data gaps, or boundary conditions"],
  "requires_external_validation": {str(basis != AnswerBasis.RETRIEVED_EVIDENCE).lower()}
}}

Do not include any Markdown code fences or extra text outside the JSON object.
"""

    # 1. Prefer native schema-constrained structured output if supported by model/LLM
    if hasattr(llm, "with_structured_output"):
        try:
            structured_llm = llm.with_structured_output(ResearchQuestionAnswer)
            struct_res = structured_llm.invoke(prompt)
            if isinstance(struct_res, ResearchQuestionAnswer):
                # Ensure question integrity
                if not struct_res.question or not struct_res.question.strip():
                    struct_res.question = question
                return clean_and_sanitize_rqa(struct_res, allowed_sources=supporting_sources)
        except Exception as struct_err:
            logger.info("Native structured output for question '%s' bypassed to robust JSON: %s", question, struct_err)

    # 2. Raw LLM invocation with robust multi-stage JSON parsing and bounded repair
    response = None
    try:
        response = llm.invoke(prompt)
        content = getattr(response, "content", "") or str(response)

        data = parse_json_robust(content)

        if not isinstance(data, dict):
            raise ValueError(f"Expected JSON dictionary from LLM, got {type(data).__name__}")

        # Parse basis safely
        parsed_basis_str = data.get("basis", basis.value)
        try:
            parsed_basis = AnswerBasis(parsed_basis_str)
        except ValueError:
            parsed_basis = basis

        raw_rqa = ResearchQuestionAnswer(
            question=data.get("question", question) or question,
            answer=data.get("answer", ""),
            basis=parsed_basis,
            supporting_sources=data.get("supporting_sources", []),
            assumptions=data.get("assumptions", []),
            confidence=data.get("confidence", "Moderate"),
            limitations=data.get("limitations", []),
            requires_external_validation=bool(data.get("requires_external_validation", True)),
        )

        # Enforce sanitization
        return clean_and_sanitize_rqa(raw_rqa, allowed_sources=supporting_sources)

    except Exception as exc:
        diag = capture_failed_response_diagnostics(
            provider="mistral",
            model=getattr(llm, "model", "unknown") if hasattr(llm, "model") else getattr(llm, "model_name", "unknown"),
            raw_response=response,
            exc=exc,
        )
        logger.warning(
            "LLM generation error for question '%s': %s (finish_reason=%s, len=%s, preview=%s)",
            question,
            diag["error"],
            diag["finish_reason"],
            diag["raw_response_length"],
            diag["raw_preview"][:80],
        )
        return build_deterministic_fallback_answer(
            question=question,
            idea=idea,
            basis=basis,
            supporting_sources=supporting_sources,
            relevant_evidence=evidence_items,
            note=f"LLM call encountered an issue: {diag['error']}. Delivered deterministic fallback.",
        )


def answer_research_questions(
    idea: str,
    questions: Optional[List[str]] = None,
    evidence_data: Optional[Dict[str, Any]] = None,
    retrieved_chunks: Optional[List[Any]] = None,
    llm: Optional[Any] = None,
) -> Tuple[List[ResearchQuestionAnswer], Dict[str, Any]]:
    """
    Coordinate answering all research questions for the market report.
    Assesses evidence sufficiency for each question, invokes LLM / fallback answering,
    and isolates failures so the overall report never crashes.
    """
    active_questions = questions if questions and len(questions) > 0 else DEFAULT_RESEARCH_QUESTIONS
    all_evidence = extract_evidence_items(evidence_data=evidence_data, retrieved_chunks=retrieved_chunks)

    diagnostics: Dict[str, Any] = {
        "total_questions": len(active_questions),
        "total_evidence_items": len(all_evidence),
        "basis_counts": {
            AnswerBasis.RETRIEVED_EVIDENCE.value: 0,
            AnswerBasis.MIXED.value: 0,
            AnswerBasis.MODEL_KNOWLEDGE.value: 0,
        },
        "issues": [],
    }

    answers: List[ResearchQuestionAnswer] = []

    for q in active_questions:
        try:
            basis, sources, relevant_evidence = assess_evidence_sufficiency(
                question=q,
                evidence_items=all_evidence,
            )

            rqa = generate_fallback_answer(
                question=q,
                idea=idea,
                basis=basis,
                supporting_sources=sources,
                evidence_items=relevant_evidence,
                llm=llm,
            )

            answers.append(rqa)
            basis_val = rqa.basis.value if hasattr(rqa.basis, "value") else str(rqa.basis)
            if basis_val in diagnostics["basis_counts"]:
                diagnostics["basis_counts"][basis_val] += 1

        except Exception as q_exc:
            logger.error("Unexpected error answering question '%s': %s", q, q_exc)
            diagnostics["issues"].append(f"Question '{q[:40]}' failed: {q_exc}")
            # Isolate failure: provide deterministic fallback rather than crashing
            safe_fallback = build_deterministic_fallback_answer(
                question=q,
                idea=idea,
                basis=AnswerBasis.MODEL_KNOWLEDGE,
                note=f"Error occurred during generation: {q_exc}",
            )
            answers.append(safe_fallback)
            diagnostics["basis_counts"][AnswerBasis.MODEL_KNOWLEDGE.value] += 1

    return answers, diagnostics
