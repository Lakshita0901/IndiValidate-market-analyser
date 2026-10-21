"""
app.nodes.market_report
-----------------------
Deterministic report-building node for Step 12: Final Structured Market-Validation Report.

Consolidates Step 11 market analysis, synthetic persona evaluations, empirical
evidence traceability, and market context into a validated, serializable
MarketValidationReport.

STRICT BOUNDARIES:
1. No startup success probabilities, market size estimations, or investment/go-no-go recommendations.
2. Synthetic persona frequencies are NOT population percentages, adoption rates, or conversion probabilities.
3. Pricing without explicit proposal input remains conditional and unverified.
4. Deterministic composition without mandatory or unconstrained LLM calls.
"""

import hashlib
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set, Tuple, Union

from app.schemas.market_analysis import (
    EvidenceStatus,
    MarketAnalysis,
)
from app.nodes.market_analysis import _extract_chunk_source, _extract_chunk_metadata_field
from app.schemas.market_report import (
    DisagreementItem,
    EvidenceCoverageReport,
    EvidenceTraceabilityItem,
    ExecutiveSummary,
    IdeaAndMarketContext,
    MarketValidationReport,
    PricingAndAffordabilityReport,
    PrioritizedFeatureHypothesis,
    PromisingFinding,
    RecommendedExperiment,
    ResearchQuestionAnswer,
    RiskOrBarrierFinding,
    SegmentComparisonItem,
)
from app.nodes.persona_evaluation import is_price_specified
from app.services.fallback_answer import answer_research_questions
from app.state import MarketState


# ------------------------------------------------------------------
# 1. Deterministic Extraction Helpers
# ------------------------------------------------------------------

def _extract_supplied_pricing(idea_text: str) -> Dict[str, Any]:
    """
    Extract supplied price and currency if explicitly present in the idea text.
    """
    if not is_price_specified(idea_text):
        return {
            "is_specified": False,
            "supplied_price": None,
            "currency": None,
            "price_is_conditional": True,
            "pricing_status": "Unresolved / Conditional: No price was specified in the business idea.",
        }

    # Match currency and amount
    match = re.search(r"(?:rs\.?|inr|₹|\$|€|£)\s*(\d+(?:,\d+)*(?:\.\d+)?)", idea_text, re.IGNORECASE)
    if not match:
        match = re.search(r"(\d+(?:,\d+)*(?:\.\d+)?)\s*(?:rupees|rs|inr|usd|dollars)", idea_text, re.IGNORECASE)

    amount = match.group(1) if match else "Specified (variable)"
    currency = "INR"
    if "$" in idea_text or "usd" in idea_text.lower():
        currency = "USD"
    elif "€" in idea_text:
        currency = "EUR"

    return {
        "is_specified": True,
        "supplied_price": amount,
        "currency": currency,
        "price_is_conditional": False,
        "pricing_status": f"Specified in proposal: {currency} {amount}",
    }


def _build_feature_priority_tier(pos_count: int, neg_count: int) -> str:
    """
    Transparent, documented priority tier classification:
    - High Priority Candidate: >= 2 positive mentions, 0 negative/unnecessary mentions.
    - Controversial / Needs Revision: > 0 positive and > 0 negative mentions.
    - Secondary Candidate: All other feature hypotheses.
    """
    if pos_count >= 2 and neg_count == 0:
        return "High Priority Candidate"
    elif pos_count > 0 and neg_count > 0:
        return "Controversial / Needs Revision"
    else:
        return "Secondary Candidate"


# ------------------------------------------------------------------
# 2. Master Report Construction Function
# ------------------------------------------------------------------

def build_market_validation_report(
    idea: str,
    market_analysis: Optional[Union[MarketAnalysis, Dict[str, Any]]] = None,
    personas: Optional[List[Any]] = None,
    evaluations: Optional[List[Any]] = None,
    target_segment: str = "",
    location: str = "",
    district: str = "",
    category: str = "",
    research_evidence: Optional[Dict[str, Any]] = None,
    retrieved_chunks: Optional[List[Any]] = None,
    research_question_answers: Optional[List[ResearchQuestionAnswer]] = None,
    llm: Optional[Any] = None,
    report_id: Optional[str] = None,
    generated_at: Optional[str] = None,
) -> Tuple[MarketValidationReport, Dict[str, Any]]:
    """
    Deterministically build the final structured market-validation report.
    """
    stable_report_id = report_id or f"MVR-{hashlib.sha256(idea.strip().encode('utf-8')).hexdigest()[:8].upper()}"
    stable_generated_at = generated_at or datetime.now(timezone.utc).isoformat()

    diagnostics: Dict[str, Any] = {
        "report_id": stable_report_id,
        "has_market_analysis": False,
        "total_personas": len(personas) if personas else 0,
        "total_evaluations": len(evaluations) if evaluations else 0,
        "status": "success",
        "warnings": [],
        "issues": [],
    }

    if not idea or not idea.strip():
        raise ValueError("Business idea string cannot be empty.")

    # 1. Coerce or parse MarketAnalysis
    analysis_obj: Optional[MarketAnalysis] = None
    if market_analysis:
        try:
            if isinstance(market_analysis, MarketAnalysis):
                analysis_obj = market_analysis
            elif isinstance(market_analysis, dict):
                analysis_obj = MarketAnalysis.model_validate(market_analysis)
            diagnostics["has_market_analysis"] = True
        except Exception as e:
            diagnostics["issues"].append(f"MarketAnalysis parsing error: {e}")
            diagnostics["status"] = "partial_success"
    else:
        diagnostics["warnings"].append("Upstream Step 11 market_analysis was missing or empty.")

    # Index personas and evaluations
    persona_map: Dict[str, Any] = {}
    if personas:
        for p in personas:
            pid = getattr(p, "persona_id", None) or (p.get("persona_id") if isinstance(p, dict) else None)
            if pid:
                persona_map[pid] = p

    evaluations_objs: List[Any] = evaluations or []

    # Build an index of available evidence records.
    # DocumentChunk dicts from chunker.py store provenance inside a nested 'metadata' dict.
    # Use the same extraction helpers as market_analysis to keep behaviour consistent.
    all_evidence_records: Dict[str, Dict[str, Any]] = {}
    if retrieved_chunks:
        for chk in retrieved_chunks:
            cid = getattr(chk, "chunk_id", None) or (chk.get("chunk_id") if isinstance(chk, dict) else None)
            if cid:
                all_evidence_records[str(cid)] = {
                    "chunk_id": str(cid),
                    "text": getattr(chk, "text", "") or (chk.get("text", "") if isinstance(chk, dict) else ""),
                    "source": _extract_chunk_source(chk, str(cid)),
                    "geography": _extract_chunk_metadata_field(chk, "geography"),
                    "time_period": _extract_chunk_metadata_field(chk, "time_period"),
                    "limitations": _extract_chunk_metadata_field(chk, "limitations"),
                }

    if research_evidence:
        for k, v in research_evidence.items():
            if isinstance(v, dict) and ("text" in v or "source" in v):
                all_evidence_records[k] = {
                    "chunk_id": k,
                    "text": v.get("text") or v.get("observation_summary", ""),
                    "source": _extract_chunk_source(v, k),
                    "geography": v.get("geography"),
                    "time_period": v.get("time_period"),
                    "limitations": v.get("limitations"),
                }
        for key in ["cleaned_evidence", "normalized_evidence", "census_evidence", "plfs_evidence", "reddit_evidence", "trends_evidence"]:
            for item in research_evidence.get(key, []):
                eid = item.get("evidence_id") if isinstance(item, dict) else getattr(item, "evidence_id", None)
                if not eid and isinstance(item, dict):
                    eid = item.get("chunk_id")
                if eid:
                    txt = (item.get("text") or item.get("observation_summary") or "") if isinstance(item, dict) else (getattr(item, "text", None) or getattr(item, "observation_summary", ""))
                    all_evidence_records[str(eid)] = {
                        "chunk_id": str(eid),
                        "text": txt,
                        "source": _extract_chunk_source(item, str(eid)),
                        "geography": _extract_chunk_metadata_field(item, "geography"),
                        "time_period": _extract_chunk_metadata_field(item, "time_period"),
                        "limitations": _extract_chunk_metadata_field(item, "limitations"),
                    }

    # 2. Section B: Idea and Market Context
    pricing_info = _extract_supplied_pricing(idea)
    geo_dict = {}
    if state_loc := location:
        geo_dict["state"] = state_loc
    if dist_loc := district:
        geo_dict["district"] = dist_loc

    target_segs = []
    if analysis_obj and analysis_obj.segment_analyses:
        target_segs = [s.segment_name for s in analysis_obj.segment_analyses]
    elif target_segment:
        target_segs = [target_segment]
    else:
        target_segs = ["General Target Customers"]

    # Gather intended use cases from personas if available
    intended_use_cases = []
    if personas:
        for p in personas:
            uc = p.get("usage_context") if isinstance(p, dict) else getattr(p, "usage_context", None)
            if uc and uc not in intended_use_cases:
                intended_use_cases.append(uc)
    intended_use_cases = intended_use_cases[:4]

    idea_context = IdeaAndMarketContext(
        business_idea=idea.strip(),
        business_category=category or "Unspecified Category",
        target_segments=target_segs,
        target_geography=geo_dict if geo_dict else None,
        intended_use_cases=intended_use_cases,
        pricing_information=pricing_info,
    )

    # 3. Section C: What Appears Promising
    promising_findings: List[PromisingFinding] = []
    if analysis_obj:
        # From top valued features
        for idx, feat in enumerate(analysis_obj.features_analysis[:4], 1):
            if feat.positive_mentions_count > 0:
                cat = "feature"
                if any(w in feat.feature_name.lower() for w in ["speed", "fast", "workflow", "automate", "schedule"]):
                    cat = "workflow_efficiency"
                elif any(w in feat.feature_name.lower() for w in ["cost", "affordable", "budget", "price"]):
                    cat = "economic_alignment"

                promising_findings.append(
                    PromisingFinding(
                        finding_id=f"PROMISING-{idx}",
                        claim_or_hypothesis=f"Simulated personas value: '{feat.feature_name}' ({feat.positive_mentions_count} positive mentions)",
                        category=cat,
                        relevant_segments=feat.segments_represented or target_segs,
                        supporting_persona_ids=feat.persona_ids,
                        supporting_evidence_ids=feat.validation.supporting_evidence_ids,
                        evidence_sources=feat.validation.evidence_sources,
                        evidence_validation_status=feat.validation.evidence_status,
                        rationale=feat.validation.explanation or "Observed favorable reaction across simulated personas.",
                        caveats_and_assumptions=feat.validation.caveats or ["Simulated sentiment; does not constitute measured market demand."],
                        suggested_real_world_validation=f"Conduct feature preference test with 10 real users from {', '.join(feat.segments_represented[:2])}.",
                    )
                )

        # From high-interest segments
        for idx, seg in enumerate(analysis_obj.segment_analyses[:2], len(promising_findings) + 1):
            if seg.median_interest and seg.median_interest >= 7.0:
                seg_evals = []
                for e in evaluations_objs:
                    e_pid = getattr(e, "persona_id", None) or (e.get("persona_id") if isinstance(e, dict) else None)
                    p_entry = persona_map.get(e_pid)
                    p_seg = getattr(p_entry, "segment", None) or (p_entry.get("segment") if isinstance(p_entry, dict) else None)
                    if p_seg == seg.segment_name:
                        seg_evals.append(e)

                seg_ev_ids = []
                for ev in seg_evals:
                    ev_ids = getattr(ev, "supporting_evidence_ids", None) or (ev.get("supporting_evidence_ids") if isinstance(ev, dict) else None) or []
                    seg_ev_ids.extend(ev_ids)
                seg_ev_ids = sorted(list(set(seg_ev_ids)))

                supp_pids = [
                    (getattr(p, "persona_id", None) or (p.get("persona_id") if isinstance(p, dict) else None))
                    for p in personas or []
                    if (getattr(p, "segment", None) or (p.get("segment") if isinstance(p, dict) else None)) == seg.segment_name
                ]
                supp_pids = [pid for pid in supp_pids if pid]

                # Simulated segment receptivity cannot be SUPPORTED if empirical coverage is 0%
                seg_status = EvidenceStatus.INSUFFICIENT_EVIDENCE
                if seg_ev_ids and analysis_obj and getattr(analysis_obj.evidence_coverage, "supported_count", 0) > 0:
                    seg_status = EvidenceStatus.SUPPORTED

                promising_findings.append(
                    PromisingFinding(
                        finding_id=f"PROMISING-{idx}",
                        claim_or_hypothesis=f"High simulated receptivity in segment: '{seg.segment_name}' (Median Interest: {seg.median_interest}/10)",
                        category="segment_alignment",
                        relevant_segments=[seg.segment_name],
                        supporting_persona_ids=supp_pids,
                        supporting_evidence_ids=seg_ev_ids,
                        evidence_sources=[],
                        evidence_validation_status=seg_status,
                        rationale=seg.affordability_and_adoption_summary,
                        caveats_and_assumptions=["Persona sample allocation does not represent real-world segment size or market share."],
                        suggested_real_world_validation=f"Interview 8 target decision makers in {seg.segment_name}.",
                    )
                )

    # 4. Section D: What May Not Work / Key Risks
    risk_findings: List[RiskOrBarrierFinding] = []
    if analysis_obj:
        for idx, conc in enumerate(analysis_obj.concerns_analysis[:6], 1):
            risk_findings.append(
                RiskOrBarrierFinding(
                    finding_id=f"RISK-{idx}",
                    concern_or_barrier=conc.concern_name,
                    barrier_category=conc.category,
                    relevant_segments=conc.segments_represented or target_segs,
                    reporting_persona_ids=conc.persona_ids,
                    contradicting_or_supporting_evidence_ids=conc.validation.supporting_evidence_ids or conc.validation.contradicting_evidence_ids,
                    evidence_sources=conc.validation.evidence_sources,
                    evidence_validation_status=conc.validation.evidence_status,
                    rationale=conc.validation.explanation or "Frequently raised objection across simulated evaluations.",
                    caveats=conc.validation.caveats or ["Potential barrier requiring qualitative interview confirmation."],
                    suggested_mitigation_or_test=f"Design an onboarding prototype addressing {conc.category.replace('_', ' ')}.",
                )
            )

    # 5. Section E: Segment Comparison
    segment_comparison: List[SegmentComparisonItem] = []
    if analysis_obj:
        for s in analysis_obj.segment_analyses:
            med_dict = {
                # Short keys (canonical, read by downstream consumers)
                "interest": s.median_interest,
                "purchase_intent": s.median_purchase_intent,
                "perceived_value": s.median_perceived_value,
                "affordability": s.median_affordability,
                "adoption_barrier": s.median_adoption_barrier,
                # Backward-compatible prefixed keys (for CLI code that reads median_interest etc.)
                "median_interest": s.median_interest,
                "median_purchase_intent": s.median_purchase_intent,
                "median_perceived_value": s.median_perceived_value,
                "median_affordability": s.median_affordability,
                "median_adoption_barrier": s.median_adoption_barrier,
            }

            seg_evals = []
            for e in evaluations_objs:
                e_pid = getattr(e, "persona_id", None) or (e.get("persona_id") if isinstance(e, dict) else None)
                p_entry = persona_map.get(e_pid)
                p_seg = getattr(p_entry, "segment", None) or (p_entry.get("segment") if isinstance(p_entry, dict) else None)
                if p_seg == s.segment_name:
                    seg_evals.append(e)

            seg_ev_ids = []
            for ev in seg_evals:
                ev_ids = getattr(ev, "supporting_evidence_ids", None) or (ev.get("supporting_evidence_ids") if isinstance(ev, dict) else None) or []
                seg_ev_ids.extend(ev_ids)
            seg_ev_ids = sorted(list(set(seg_ev_ids)))

            segment_comparison.append(
                SegmentComparisonItem(
                    segment_name=s.segment_name,
                    persona_count=s.persona_count,
                    evaluated_personas_count=s.evaluated_count,
                    median_scores=med_dict,
                    valued_features=s.top_valued_features,
                    main_concerns=s.major_concerns,
                    affordability_and_adoption_summary=s.affordability_and_adoption_summary,
                    relevant_evidence_ids=seg_ev_ids,
                    important_evidence_gaps=s.important_gaps,
                    suggested_validation_experiment=f"Qualitative interview study (N=10) focusing on {s.segment_name} adoption barriers.",
                )
            )

    # 6. Section F: Feature Prioritization Hypotheses
    feature_prioritization: List[PrioritizedFeatureHypothesis] = []
    if analysis_obj:
        for feat in analysis_obj.features_analysis:
            tier = _build_feature_priority_tier(feat.positive_mentions_count, feat.negative_mentions_count)
            uncertainty = "Need to test whether real users will pay for this feature or consider it baseline table stakes."
            if feat.validation.evidence_status == EvidenceStatus.INSUFFICIENT_EVIDENCE:
                uncertainty += " External empirical evidence is currently missing."

            feature_prioritization.append(
                PrioritizedFeatureHypothesis(
                    feature_name=feat.feature_name,
                    positive_mentions_count=feat.positive_mentions_count,
                    negative_mentions_count=feat.negative_mentions_count,
                    persona_ids=feat.persona_ids,
                    segment_distribution=feat.segments_represented,
                    evidence_validation_status=feat.validation.evidence_status,
                    supporting_evidence_ids=feat.validation.supporting_evidence_ids,
                    contradicting_evidence_ids=feat.validation.contradicting_evidence_ids,
                    priority_tier=tier,
                    main_uncertainty=uncertainty,
                    suggested_next_validation_step=f"Include '{feat.feature_name}' in a feature-card sorting exercise with prospective users.",
                )
            )

    # 7. Section G: Pricing and Affordability Report
    afford_summary = "Simulated affordability scores reflect budget fit relative to hypothesized persona income. They do NOT establish real willingness to pay or price elasticity."
    unresolved_pricing = []
    if pricing_info["price_is_conditional"]:
        unresolved_pricing.append("Product pricing is unverified; idea did not propose a concrete price point.")
        unresolved_pricing.append("Willingness to pay cannot be inferred directly from aggregate census or labour statistics.")
    else:
        unresolved_pricing.append(f"Proposed price of {pricing_info['supplied_price']} {pricing_info['currency']} requires validation against competitor price alternatives.")

    # Contextual earnings evidence from research state (PLFS 2025)
    contextual_earnings = None
    if research_evidence and research_evidence.get("plfs_evidence"):
        plfs_rec = research_evidence["plfs_evidence"][0]
        earn = plfs_rec.get("earnings", {})
        if earn:
            reg_sal = earn.get("regular_salaried", {}).get("avg_monthly_salary_inr")
            self_emp = earn.get("self_employed", {}).get("avg_monthly_earnings_inr")
            contextual_earnings = {
                "source": "PLFS 2025 (Weighted labour survey benchmarks)",
                "regular_salaried_avg_inr": reg_sal,
                "self_employed_gross_avg_inr": self_emp,
                "limitations": "Benchmark monthly earnings context only; cannot be used to determine pricing elasticity without direct customer tests.",
            }

    pricing_report = PricingAndAffordabilityReport(
        supplied_price=pricing_info["supplied_price"],
        currency=pricing_info["currency"],
        pricing_status=pricing_info["pricing_status"],
        price_is_conditional=pricing_info["price_is_conditional"],
        simulated_affordability_summary=afford_summary,
        contextual_earnings_evidence=contextual_earnings,
        unresolved_pricing_questions=unresolved_pricing,
        recommended_wtp_experiment="Conduct a 4-question Van Westendorp Price Sensitivity Survey and a landing page pre-order test.",
    )

    # 8. Section H: Evidence Traceability
    traceability_items: List[EvidenceTraceabilityItem] = []
    # Identify all cited evidence IDs
    all_cited_eids: Set[str] = set()
    for pf in promising_findings:
        all_cited_eids.update(pf.supporting_evidence_ids)
    for rf in risk_findings:
        all_cited_eids.update(rf.contradicting_or_supporting_evidence_ids)

    # If few cited, also include retrieved chunks
    for cid in list(all_evidence_records.keys())[:8]:
        all_cited_eids.add(cid)

    for eid in sorted(list(all_cited_eids)):
        rec = all_evidence_records.get(eid, {})
        src = rec.get("source") or "unknown"
        # Build a human-readable title from the resolved source name (not "UNKNOWN ...")
        if src and src.lower() != "unknown":
            src_label = src.upper()
        else:
            # Last-resort: infer from evidence_id prefix
            eid_lower = eid.lower()
            if "_census_" in eid_lower or eid_lower.startswith("census"):
                src_label = "CENSUS_2011"
                src = "census_2011"
            elif "_plfs_" in eid_lower or eid_lower.startswith("plfs"):
                src_label = "PLFS_2025"
                src = "plfs_2025"
            elif "_reddit_" in eid_lower or eid_lower.startswith("reddit"):
                src_label = "REDDIT"
                src = "reddit"
            elif "_trends_" in eid_lower or eid_lower.startswith("trends"):
                src_label = "GOOGLE_TRENDS"
                src = "google_trends"
            else:
                src_label = "UNKNOWN"
        txt = rec.get("text", "No observation text available.")
        raw_lims = rec.get("limitations") or []
        if isinstance(raw_lims, str):
            lims = [raw_lims]
        else:
            lims = list(raw_lims)

        # Source-specific caveats
        if "census" in src.lower():
            lims.append("Census 2011 provides reference demographic distributions; cannot establish product purchase intent.")
        elif "plfs" in src.lower():
            lims.append("PLFS 2025 provides labour estimates subject to survey sampling limits.")
        elif "trends" in src.lower():
            lims.append("Google Trends reports relative search query interest, not absolute demand or purchase volume.")
        elif "reddit" in src.lower():
            lims.append("Historical social discussion dataset subject to self-selection and forum participation bias.")

        supp_finds = [pf.finding_id for pf in promising_findings if eid in pf.supporting_evidence_ids]
        contra_finds = [rf.finding_id for rf in risk_findings if eid in rf.contradicting_or_supporting_evidence_ids]

        traceability_items.append(
            EvidenceTraceabilityItem(
                evidence_id=eid,
                source_type=src,
                source_title=f"{src_label} Evidence Record [{eid}]",
                geography=rec.get("geography"),
                observation_period=rec.get("time_period"),
                factual_summary=txt[:250],
                caveats_and_limitations=list(dict.fromkeys(lims))[:3],
                findings_supported=supp_finds,
                findings_contradicted=contra_finds,
            )
        )

    # 9. Section I: Disagreement and Uncertainty
    disagreement_items: List[DisagreementItem] = []
    if analysis_obj:
        for d in analysis_obj.disagreement_areas:
            disagreement_items.append(
                DisagreementItem(
                    topic=d.topic,
                    relevant_segments_or_personas=d.opposing_views_or_segments,
                    observed_spread_or_difference=f"Spread / Variance: {d.divergence_spread}",
                    plausible_explanation=d.explanation,
                    is_observed_or_hypothesized="Hypothesized Explanation",
                    evidence_needed_to_resolve="Direct customer interviews contrasting high-friction vs low-friction customer personas.",
                )
            )

    # 10. Section J: Evidence Coverage Audit
    if analysis_obj:
        cov_obj = analysis_obj.evidence_coverage
        coverage_report = EvidenceCoverageReport(
            total_findings_evaluated=cov_obj.total_findings_evaluated,
            supported_count=cov_obj.supported_count,
            contradicted_count=cov_obj.contradicted_count,
            mixed_count=cov_obj.mixed_count,
            insufficient_evidence_count=cov_obj.insufficient_evidence_count,
            not_applicable_count=cov_obj.not_applicable_count,
            evidence_coverage_ratio=cov_obj.evidence_coverage_ratio,
            coverage_formula_explanation="(supported + contradicted + mixed) / max(1, total_findings). Measures data availability, NOT market viability.",
            sources_represented=cov_obj.sources_represented,
            unsupported_assumptions=cov_obj.unsupported_assumptions,
            unresolved_pricing_assumptions=cov_obj.unresolved_pricing_assumptions,
            important_evidence_gaps=cov_obj.important_evidence_gaps,
        )
    else:
        coverage_report = EvidenceCoverageReport(
            total_findings_evaluated=0,
            supported_count=0,
            contradicted_count=0,
            mixed_count=0,
            insufficient_evidence_count=0,
            not_applicable_count=0,
            evidence_coverage_ratio=0.0,
            coverage_formula_explanation="No analysis findings evaluated.",
            sources_represented=[],
            unsupported_assumptions=[],
            unresolved_pricing_assumptions=[],
            important_evidence_gaps=["Step 11 analysis unavailable."],
        )

    # 11. Section K: Recommended Next Experiments
    recommended_experiments: List[RecommendedExperiment] = []
    lead_seg = target_segs[0] if target_segs else "Primary Target Customer"

    # EXP-1: Core Problem & Workflow Interviews
    recommended_experiments.append(
        RecommendedExperiment(
            recommendation_id="EXP-1",
            question_to_validate=f"Do {lead_seg} actively seek to replace their current workflow/solution, or does habit inertia prevail?",
            target_segment=lead_seg,
            strategic_rationale="Simulated personas identified switching costs and habit inertia as major adoption barriers.",
            supporting_finding_ids=[rf.finding_id for rf in risk_findings[:2]],
            suggested_experiment_type="Customer Discovery Interviews",
            measurement_metric="Proportion of interviewees who report active frustration and recent spending on alternative solutions.",
            decision_rule_hypothesis="If >= 6 of 10 interviewees report recent attempts to change solutions, proceed with workflow prototype. (Proposed threshold).",
            experiment_limitations="Qualitative self-reporting bias; respondents may overstate willingness to change.",
        )
    )

    # EXP-2: Willingness-to-Pay / Price Range Test
    recommended_experiments.append(
        RecommendedExperiment(
            recommendation_id="EXP-2",
            question_to_validate=f"What is the acceptable price threshold and perceived ROI for {lead_seg}?",
            target_segment=lead_seg,
            strategic_rationale="Pricing is currently conditional and unverified; WTP cannot be deduced from labour benchmarks.",
            supporting_finding_ids=[],
            suggested_experiment_type="Van Westendorp Price Sensitivity Survey & Landing Page Smoke Test",
            measurement_metric="Optimum Price Point (OPP) and Point of Marginal Cheapness/Expensiveness.",
            decision_rule_hypothesis="Acceptable price band aligns with target unit economics. (Proposed design choice).",
            experiment_limitations="Stated willingness to pay does not guarantee actual credit-card checkout.",
        )
    )

    # EXP-3: Key Feature Usability & Value Proof
    top_feature_name = promising_findings[0].claim_or_hypothesis if promising_findings else "Core Automation"
    recommended_experiments.append(
        RecommendedExperiment(
            recommendation_id="EXP-3",
            question_to_validate=f"Does the proposed capability ('{top_feature_name}') deliver sufficient perceived value to overcome switching friction?",
            target_segment=lead_seg,
            strategic_rationale="Validates whether the most favored simulated feature is genuinely compelling to real prospective users.",
            supporting_finding_ids=[promising_findings[0].finding_id] if promising_findings else [],
            suggested_experiment_type="Clickable Prototype Usability Test",
            measurement_metric="Task completion rate and net usability perception.",
            decision_rule_hypothesis="Users successfully complete core task and verbally express willingness to adopt. (Proposed design choice).",
            experiment_limitations="Clickable prototype lacks actual live integration and operational edge cases.",
        )
    )

    # Epistemic boundary: When overall evidence coverage has 0 supported findings,
    # no claim can be labeled SUPPORTED / 'Corroborated by Evidence'.
    if coverage_report.supported_count == 0:
        for pf in promising_findings:
            if pf.evidence_validation_status == EvidenceStatus.SUPPORTED:
                pf.evidence_validation_status = EvidenceStatus.INSUFFICIENT_EVIDENCE
        for rf in risk_findings:
            if rf.evidence_validation_status == EvidenceStatus.SUPPORTED:
                rf.evidence_validation_status = EvidenceStatus.INSUFFICIENT_EVIDENCE
        for fp in feature_prioritization:
            if fp.evidence_validation_status == EvidenceStatus.SUPPORTED:
                fp.evidence_validation_status = EvidenceStatus.INSUFFICIENT_EVIDENCE

    # 12. Section A: Executive Summary Synthesis
    promising_snippets = [f"[{pf.finding_id}] {pf.claim_or_hypothesis}" for pf in promising_findings[:3]]
    risk_snippets = [f"[{rf.finding_id}] {rf.concern_or_barrier} ({rf.barrier_category.replace('_', ' ')})" for rf in risk_findings[:3]]
    unresolved_snippets = list(dict.fromkeys(pricing_report.unresolved_pricing_questions + coverage_report.important_evidence_gaps))[:3]

    # Explicit default fallback to ensure variable is always assigned
    next_priority = (
        f"Conduct 10 in-depth customer discovery interviews with {lead_seg} to empirically validate "
        f"problem urgency, workflow friction, and willingness to pay before committing build resources."
    )

    if not personas:
        diagnostics["status"] = "failed"
        diagnostics["issues"].append("Market validation incomplete: persona generation produced zero personas.")
        diagnostics["warnings"].append("Market validation incomplete: persona generation produced zero personas.")
        default_promising = ["Analysis incomplete: persona generation produced zero personas."]
        default_risks = ["Upstream persona generation failed; simulated evaluations and barrier analysis could not be conducted."]
        default_unresolved = ["Customer demand, segment receptivity, and pricing validation remain completely unevaluated."]
        next_priority = "Diagnose persona generation / LLM connectivity and re-run analysis to generate customer evaluations."
    elif not evaluations:
        diagnostics["status"] = "failed"
        diagnostics["issues"].append("Market validation incomplete: persona evaluation produced zero evaluations.")
        default_promising = ["Analysis incomplete: persona evaluation produced zero evaluations."]
        default_risks = ["Upstream persona evaluation failed; simulated reactions and barrier analysis could not be conducted."]
        default_unresolved = ["Customer demand, segment receptivity, and pricing validation remain completely unevaluated."]
        next_priority = "Diagnose persona evaluation connectivity and re-run analysis to evaluate generated personas."
    else:
        # Both personas and evaluations are present
        if coverage_report.supported_count == 0 and coverage_report.insufficient_evidence_count > 0:
            default_promising = ["No empirically supported signals identified (all simulated signals require real-world validation)."]
            default_risks = ["Adoption barriers, switching costs, and pricing acceptability are unverified by empirical data."]
            default_unresolved = ["Empirical demand, willingness to pay, and conversion behavior remain completely unvalidated."]
            if recommended_experiments:
                top_exp = recommended_experiments[0]
                next_priority = (
                    f"Empirical evidence is currently insufficient (0 supported claims). Priority is to conduct "
                    f"{top_exp.suggested_experiment_type} with {lead_seg} ({top_exp.recommendation_id}) to validate: "
                    f"'{top_exp.question_to_validate}'."
                )
            else:
                next_priority = (
                    f"Empirical evidence is currently insufficient (0 supported claims). Priority is to conduct "
                    f"customer discovery interviews with {lead_seg} to test fundamental problem-solution fit and willingness to pay."
                )
        else:
            default_promising = ["Simulated persona interest observed in core features (requires real-world validation)."]
            default_risks = ["Switching costs, workflow habits, and pricing unverified in real market."]
            default_unresolved = ["Willingness to pay and real-world conversion behavior."]
            if recommended_experiments:
                top_exp = recommended_experiments[0]
                next_priority = (
                    f"Conduct {top_exp.suggested_experiment_type} with {lead_seg} ({top_exp.recommendation_id}) to validate: "
                    f"'{top_exp.question_to_validate}'."
                )
            elif risk_findings:
                top_risk = risk_findings[0]
                next_priority = (
                    f"Conduct 10 in-depth customer discovery interviews with {lead_seg} to validate whether "
                    f"the key barrier '{top_risk.concern_or_barrier}' represents an insurmountable adoption hurdle."
                )
            else:
                next_priority = (
                    f"Conduct 10 in-depth customer discovery interviews with {lead_seg} (EXP-1) to validate whether current switching "
                    f"inertia and operational objections represent insurmountable barriers before building production software."
                )

    exec_summary = ExecutiveSummary(
        idea_description=idea.strip()[:200],
        target_customer_segments=target_segs,
        strongest_promising_signals=promising_snippets or default_promising,
        key_risks_and_barriers=risk_snippets or default_risks,
        critical_unresolved_questions=unresolved_snippets or default_unresolved,
        next_validation_priority=next_priority,
    )

    # 13. Section 9: Core Research Questions Analysis (Evidence-grounded or LLM Fallback)
    rq_answers = research_question_answers
    if rq_answers is None:
        try:
            rq_answers, rq_diag = answer_research_questions(
                idea=idea,
                evidence_data=research_evidence,
                retrieved_chunks=retrieved_chunks,
                llm=llm,
            )
            diagnostics["research_questions_diagnostics"] = rq_diag
        except Exception as rq_exc:
            diagnostics["issues"].append(f"Research questions evaluation error: {rq_exc}")
            rq_answers = []

    # Attach evaluated personas and evaluations to diagnostics for frontend visualization
    diagnostics["personas"] = [p.model_dump() if hasattr(p, "model_dump") else p for p in personas] if personas else []
    diagnostics["persona_evaluations"] = [e.model_dump() if hasattr(e, "model_dump") else e for e in evaluations] if evaluations else []

    # Assemble master report
    final_report = MarketValidationReport(
        report_id=stable_report_id,
        generated_at=stable_generated_at,
        executive_summary=exec_summary,
        idea_and_context=idea_context,
        what_appears_promising=promising_findings,
        what_may_not_work=risk_findings,
        segment_comparison=segment_comparison,
        feature_prioritization=feature_prioritization,
        pricing_and_affordability=pricing_report,
        evidence_traceability=traceability_items,
        disagreement_and_uncertainty=disagreement_items,
        evidence_coverage_audit=coverage_report,
        recommended_experiments=recommended_experiments,
        research_questions_analysis=rq_answers or [],
        diagnostics=diagnostics,
    )

    return final_report, diagnostics


# ------------------------------------------------------------------
# 3. LangGraph Node Integration
# ------------------------------------------------------------------

def build_market_report_node(state: MarketState) -> Dict[str, Any]:
    """
    LangGraph node generating the final structured market-validation report.
    Consumes Step 11 analysis, personas, evaluations, and research evidence.
    """
    idea = state.get("idea", "")
    analysis_data = state.get("market_analysis")
    personas = state.get("personas", [])
    evaluations = state.get("persona_evaluations", [])
    target = state.get("target_segment", "")
    location = state.get("location", "")
    district = state.get("district", "")
    category = state.get("category", "")

    research_evidence = {
        "census_evidence": state.get("census_evidence", []),
        "plfs_evidence": state.get("plfs_evidence", []),
        "reddit_evidence": state.get("reddit_evidence", []),
        "trends_evidence": state.get("trends_evidence", []),
        "cleaned_evidence": state.get("cleaned_evidence", []),
        "normalized_evidence": state.get("normalized_evidence", []),
    }
    retrieved_chunks = state.get("retrieved_chunks", []) or state.get("document_chunks", [])

    print("\n>>> FINAL MARKET VALIDATION REPORT GENERATION (Step 12)")

    try:
        existing_rq_answers = state.get("research_question_answers")
        report, diag = build_market_validation_report(
            idea=idea,
            market_analysis=analysis_data,
            personas=personas,
            evaluations=evaluations,
            target_segment=target,
            location=location,
            district=district,
            category=category,
            research_evidence=research_evidence,
            retrieved_chunks=retrieved_chunks,
            research_question_answers=existing_rq_answers,
        )

        if not personas or state.get("stage_failures"):
            diag["status"] = "failed"
            if "Market validation incomplete: persona generation produced zero personas." not in diag.get("issues", []):
                diag.setdefault("issues", []).append("Market validation incomplete: persona generation produced zero personas.")

        report_dict = report.model_dump()
        print(f"    Report Created: {report.report_id}")
        print(f"    Promising Hypotheses: {len(report.what_appears_promising)} | Risks & Barriers: {len(report.what_may_not_work)}")
        print(f"    Segments Compared: {len(report.segment_comparison)} | Prioritized Features: {len(report.feature_prioritization)}")
        print(f"    Recommended Experiments: {len(report.recommended_experiments)}")
        print(f"    Core Research Questions Evaluated: {len(report.research_questions_analysis)}")

        return {
            "market_report": report_dict,
            "market_report_diagnostics": diag,
            "research_question_answers": [r.model_dump() if hasattr(r, "model_dump") else r for r in report.research_questions_analysis],
        }
    except Exception as e:
        print(f"    Report Generation Error: {e}")
        return {
            "market_report": {},
            "market_report_diagnostics": {
                "status": "error",
                "issues": [f"Market report generation exception: {e}"],
            },
        }
