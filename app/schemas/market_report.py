"""
app.schemas.market_report
--------------------------
Pydantic schema for the final structured market-validation report (Step 12).

Consolidates Step 11 market analysis, synthetic persona evaluations, empirical
evidence traceability, disagreements, pricing hypotheses, and recommended
validation experiments into a validated, serializable output.

STRICT BOUNDARIES:
1. No startup success probabilities, market size estimations, or investment/go-no-go recommendations.
2. Synthetic persona frequencies are NOT population percentages, adoption rates, or conversion probabilities.
3. Pricing without explicit proposal input remains conditional and unverified.
4. Evidence coverage ratio measures empirical data availability, NOT market viability.
"""

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.market_analysis import EvidenceStatus


class AnswerBasis(str, Enum):
    """
    Epistemic grounding basis of a research question answer.
    """
    RETRIEVED_EVIDENCE = "retrieved_evidence"
    MIXED = "mixed"
    MODEL_KNOWLEDGE = "model_knowledge"


class ResearchQuestionAnswer(BaseModel):
    """
    Evaluation of a core research question, supported by retrieved evidence,
    a mixture of evidence and reasoning, or independent LLM knowledge fallback.
    """
    model_config = ConfigDict(extra="forbid")

    question: str = Field(description="The research question evaluated")
    answer: str = Field(description="The evidence-grounded or model-reasoned answer")
    basis: AnswerBasis = Field(description="retrieved_evidence, mixed, or model_knowledge")
    supporting_sources: List[str] = Field(default_factory=list, description="Actual sources used, if any")
    assumptions: List[str] = Field(default_factory=list, description="Assumptions made by the model")
    confidence: str = Field(description="Qualitative confidence with explanation")
    limitations: List[str] = Field(default_factory=list, description="Known limitations or caveats")
    requires_external_validation: bool = Field(description="True if claim requires real-world external validation")



class ExecutiveSummary(BaseModel):
    """
    High-level executive briefing consolidating key market signals, risks, and next steps.
    """
    model_config = ConfigDict(extra="forbid")

    idea_description: str = Field(description="Concise description of the evaluated business idea")
    target_customer_segments: List[str] = Field(description="Primary segments identified by the pipeline")
    strongest_promising_signals: List[str] = Field(description="Key strengths, valued capabilities, or demographic alignments")
    key_risks_and_barriers: List[str] = Field(description="Critical adoption barriers, affordability issues, or operational frictions")
    critical_unresolved_questions: List[str] = Field(description="Crucial market assumptions currently lacking empirical validation")
    next_validation_priority: str = Field(description="Clear recommendation of the immediate next question to validate with real humans")


class IdeaAndMarketContext(BaseModel):
    """
    Structured context of the business proposal and geographic scope.
    """
    model_config = ConfigDict(extra="forbid")

    business_idea: str = Field(description="Raw proposal text")
    business_category: Optional[str] = Field(default=None, description="Classified category (e.g. SaaS, Transit)")
    target_segments: List[str] = Field(description="Target segments evaluated")
    target_geography: Optional[Dict[str, Any]] = Field(default=None, description="State, district, and regional level")
    intended_use_cases: List[str] = Field(default_factory=list, description="Contexts of usage identified")
    pricing_information: Dict[str, Any] = Field(
        description="Supplied price status (is_specified, supplied_price, currency, price_is_conditional)"
    )


class PromisingFinding(BaseModel):
    """
    A specific value proposition or market hypothesis showing favorable signals.
    """
    model_config = ConfigDict(extra="forbid")

    finding_id: str = Field(description="Stable identifier (e.g. PROMISING-1)")
    claim_or_hypothesis: str = Field(description="Positive finding or capability hypothesis")
    category: str = Field(description="Category: feature, segment_alignment, workflow_efficiency, economic_alignment")
    relevant_segments: List[str] = Field(description="Segments that responded favorably")
    supporting_persona_ids: List[str] = Field(default_factory=list, description="Personas finding this valuable")
    supporting_evidence_ids: List[str] = Field(default_factory=list, description="Traceable empirical evidence chunk IDs")
    evidence_sources: List[str] = Field(default_factory=list, description="Sources: census_2011, plfs_2025, reddit, trends")
    evidence_validation_status: EvidenceStatus = Field(description="Empirical validation classification")
    rationale: str = Field(description="Why this hypothesis holds promise based on persona/evidence context")
    caveats_and_assumptions: List[str] = Field(default_factory=list, description="Unresolved assumptions or boundary limits")
    suggested_real_world_validation: str = Field(description="Practical way to test this hypothesis with real humans")


class RiskOrBarrierFinding(BaseModel):
    """
    A specific risk, friction point, or adoption barrier.
    """
    model_config = ConfigDict(extra="forbid")

    finding_id: str = Field(description="Stable identifier (e.g. RISK-1)")
    concern_or_barrier: str = Field(description="Concise description of the barrier or objection")
    barrier_category: str = Field(
        description="Category: pricing_and_affordability, switching_costs, trust_and_reliability, usability_and_adoption, operational_constraints, missing_functionality, general"
    )
    relevant_segments: List[str] = Field(description="Segments raising this concern")
    reporting_persona_ids: List[str] = Field(default_factory=list, description="Personas expressing this objection")
    contradicting_or_supporting_evidence_ids: List[str] = Field(default_factory=list, description="Cited evidence IDs")
    evidence_sources: List[str] = Field(default_factory=list, description="Sources citing this risk")
    evidence_validation_status: EvidenceStatus = Field(description="Empirical validation classification")
    rationale: str = Field(description="Context and drivers behind this concern")
    caveats: List[str] = Field(default_factory=list, description="Known limits or conditions for this concern")
    suggested_mitigation_or_test: str = Field(description="Specific test or design mitigation to explore")


class SegmentComparisonItem(BaseModel):
    """
    Segment-by-segment comparison derived from Step 11 analysis.
    """
    model_config = ConfigDict(extra="forbid")

    segment_name: str = Field(description="Segment label")
    persona_count: int = Field(ge=0, description="Synthetic personas generated in this segment (NOT market share!)")
    evaluated_personas_count: int = Field(ge=0, description="Successfully evaluated personas in this segment")
    median_scores: Dict[str, Optional[float]] = Field(
        description="Median scores: interest, purchase_intent, perceived_value, affordability, adoption_barrier"
    )
    valued_features: List[str] = Field(default_factory=list, description="Top features praised by this segment")
    main_concerns: List[str] = Field(default_factory=list, description="Major objections raised in this segment")
    affordability_and_adoption_summary: str = Field(description="Narrative summary of financial and workflow friction")
    relevant_evidence_ids: List[str] = Field(default_factory=list, description="Evidence records cited for this segment")
    important_evidence_gaps: List[str] = Field(default_factory=list, description="Missing demographic or behavioural facts")
    suggested_validation_experiment: str = Field(description="Recommended real-world test for this segment")


class PrioritizedFeatureHypothesis(BaseModel):
    """
    Structured feature feedback with transparent priority rules.
    """
    model_config = ConfigDict(extra="forbid")

    feature_name: str = Field(description="Feature descriptor")
    positive_mentions_count: int = Field(ge=0, description="Distinct personas valuing this feature")
    negative_mentions_count: int = Field(ge=0, description="Distinct personas finding it unnecessary or problematic")
    persona_ids: List[str] = Field(description="Personas commenting on this feature")
    segment_distribution: List[str] = Field(description="Segments representing these personas")
    evidence_validation_status: EvidenceStatus = Field(description="Empirical backing status")
    supporting_evidence_ids: List[str] = Field(default_factory=list, description="Corroborating evidence IDs")
    contradicting_evidence_ids: List[str] = Field(default_factory=list, description="Conflicting evidence IDs")
    priority_tier: str = Field(
        description="Transparent rule: High Priority Candidate, Controversial / Needs Revision, or Secondary Candidate"
    )
    main_uncertainty: str = Field(description="Key unknown question regarding this feature")
    suggested_next_validation_step: str = Field(description="Customer test for this feature")


class PricingAndAffordabilityReport(BaseModel):
    """
    Conservative pricing assessment and willingness-to-pay hypotheses.
    """
    model_config = ConfigDict(extra="forbid")

    supplied_price: Optional[str] = Field(default=None, description="Exact price supplied by user, or None if omitted")
    currency: Optional[str] = Field(default=None, description="Currency specified")
    pricing_status: str = Field(description="Status: Specified or Unresolved / Conditional")
    price_is_conditional: bool = Field(description="True if price was unspecified in proposal")
    simulated_affordability_summary: str = Field(
        description="Explanation of what simulated affordability scores establish and caveats"
    )
    contextual_earnings_evidence: Optional[Dict[str, Any]] = Field(
        default=None,
        description="PLFS wage benchmarks cited for context (does NOT derive willingness to pay directly from income)"
    )
    unresolved_pricing_questions: List[str] = Field(description="Crucial pricing uncertainties")
    recommended_wtp_experiment: str = Field(description="Empirical pricing validation test (e.g. Van Westendorp, landing page test)")


class EvidenceTraceabilityItem(BaseModel):
    """
    Audit record tracing a factual source that contributed to the evaluation.
    """
    model_config = ConfigDict(extra="forbid")

    evidence_id: str = Field(description="Stable chunk or evidence identifier")
    source_type: str = Field(description="census_2011, plfs_2025, reddit, or google_trends")
    source_title: str = Field(description="Descriptive title or indicator name")
    geography: Optional[Dict[str, Any]] = Field(default=None, description="Geographic scope")
    observation_period: Optional[str] = Field(default=None, description="Survey year or observation period")
    factual_summary: str = Field(description="Textual observation or metric excerpt")
    caveats_and_limitations: List[str] = Field(default_factory=list, description="Source-specific limitations")
    findings_supported: List[str] = Field(default_factory=list, description="IDs of findings supported")
    findings_contradicted: List[str] = Field(default_factory=list, description="IDs of findings contradicted")


class DisagreementItem(BaseModel):
    """
    Specific dimension or metric where personas reached opposing conclusions.
    """
    model_config = ConfigDict(extra="forbid")

    topic: str = Field(description="Dimension of disagreement")
    relevant_segments_or_personas: Dict[str, Any] = Field(description="Contrasting segments or score distributions")
    observed_spread_or_difference: str = Field(description="Quantitative spread or score variance")
    plausible_explanation: str = Field(description="Plausible contextual reason for difference")
    is_observed_or_hypothesized: str = Field(
        description="Explicit classification: 'Observed Empirical Fact' or 'Hypothesized Explanation'"
    )
    evidence_needed_to_resolve: str = Field(description="Factual data needed to resolve divergence")


class EvidenceCoverageReport(BaseModel):
    """
    Audit metrics of empirical evidence cross-validation.
    """
    model_config = ConfigDict(extra="forbid")

    total_findings_evaluated: int = Field(ge=0, description="Total findings submitted to validation")
    supported_count: int = Field(ge=0, description="Findings corroborated by evidence")
    contradicted_count: int = Field(ge=0, description="Findings contradicted by evidence")
    mixed_count: int = Field(ge=0, description="Findings with mixed evidence")
    insufficient_evidence_count: int = Field(ge=0, description="Findings lacking empirical data")
    not_applicable_count: int = Field(ge=0, description="Purely subjective findings not applicable to data")
    evidence_coverage_ratio: float = Field(
        ge=0.0,
        le=1.0,
        description="Formula: (supported + contradicted + mixed) / max(1, total_findings). Coverage measure, NOT success probability."
    )
    coverage_formula_explanation: str = Field(
        description="Documents exact formula and confirms this is an audit metric, not startup viability"
    )
    sources_represented: List[str] = Field(default_factory=list, description="Active sources cited")
    unsupported_assumptions: List[str] = Field(default_factory=list, description="Assumptions lacking data")
    unresolved_pricing_assumptions: List[str] = Field(default_factory=list, description="Conditional pricing assumptions")
    important_evidence_gaps: List[str] = Field(default_factory=list, description="Critical data gaps")


class RecommendedExperiment(BaseModel):
    """
    Actionable validation experiment to test critical uncertainties with real customers.
    """
    model_config = ConfigDict(extra="forbid")

    recommendation_id: str = Field(description="Stable identifier (e.g. EXP-1)")
    question_to_validate: str = Field(description="Core empirical hypothesis to test")
    target_segment: str = Field(description="Specific customer segment to interview/survey")
    strategic_rationale: str = Field(description="Why resolving this question is critical for the idea")
    supporting_finding_ids: List[str] = Field(default_factory=list, description="Related finding IDs")
    suggested_experiment_type: str = Field(
        description="Experiment type: Customer Discovery Interviews, Usability Test, Landing Page Smoke Test, Van Westendorp Survey, Operational Pilot"
    )
    measurement_metric: str = Field(description="Quantitative or qualitative signal to observe")
    decision_rule_hypothesis: str = Field(
        description="Proposed threshold: what outcome would support vs weaken the hypothesis (explicitly labeled proposed design choice)"
    )
    experiment_limitations: str = Field(description="Known caveats or confounding factors of this test")


class MarketValidationReport(BaseModel):
    """
    Master contract for Step 12: Final Structured Market-Validation Report.
    Consolidates executive briefing, context, findings, segments, features, pricing,
    traceability, disagreements, coverage audit, and recommended experiments.
    """
    model_config = ConfigDict(extra="forbid")

    report_id: str = Field(description="Stable deterministic report identifier")
    generated_at: str = Field(description="Deterministic generation timestamp or reference label")
    executive_summary: ExecutiveSummary = Field(description="Section A: Executive summary")
    idea_and_context: IdeaAndMarketContext = Field(description="Section B: Idea and market context")
    what_appears_promising: List[PromisingFinding] = Field(description="Section C: Promising findings")
    what_may_not_work: List[RiskOrBarrierFinding] = Field(description="Section D: Risks and barriers")
    segment_comparison: List[SegmentComparisonItem] = Field(description="Section E: Segment comparison")
    feature_prioritization: List[PrioritizedFeatureHypothesis] = Field(description="Section F: Feature prioritization")
    pricing_and_affordability: PricingAndAffordabilityReport = Field(description="Section G: Pricing and affordability")
    evidence_traceability: List[EvidenceTraceabilityItem] = Field(description="Section H: Evidence traceability")
    disagreement_and_uncertainty: List[DisagreementItem] = Field(description="Section I: Disagreements")
    evidence_coverage_audit: EvidenceCoverageReport = Field(description="Section J: Evidence coverage audit")
    recommended_experiments: List[RecommendedExperiment] = Field(description="Section K: Recommended experiments")
    research_questions_analysis: List[ResearchQuestionAnswer] = Field(
        default_factory=list,
        description="Section 9: Core research questions analysis supported by retrieved evidence, mixed evidence, or model knowledge"
    )
    diagnostics: Dict[str, Any] = Field(default_factory=dict, description="Metadata and execution diagnostics")

    @model_validator(mode="after")
    def validate_report_integrity(self) -> "MarketValidationReport":
        """
        Verify that the report does not produce startup success probabilities or unvalidated scores.
        """
        if not self.report_id or not self.report_id.strip():
            raise ValueError("report_id cannot be empty.")
        if self.evidence_coverage_audit.evidence_coverage_ratio < 0.0 or self.evidence_coverage_audit.evidence_coverage_ratio > 1.0:
            raise ValueError("evidence_coverage_ratio must be between 0.0 and 1.0.")
        return self

    def to_markdown(self) -> str:
        """
        Serialize the report into a clean, human-readable Markdown format suitable for CLI/documentation.
        """
        lines = []
        lines.append(f"# MARKET VALIDATION REPORT: {self.idea_and_context.business_idea[:60]}...")
        lines.append(f"**Report ID**: `{self.report_id}` | **Status**: Verified Synthetic Simulation & Empirical Audit\n")

        # Executive Summary
        es = self.executive_summary
        lines.append("## 1. Executive Summary")
        lines.append(f"- **Evaluated Concept**: {es.idea_description}")
        lines.append(f"- **Target Segments**: {', '.join(es.target_customer_segments) if es.target_customer_segments else 'General Market'}")
        lines.append("\n### Strongest Promising Signals")
        for s in es.strongest_promising_signals[:4]:
            lines.append(f"- {s}")
        lines.append("\n### Key Risks & Adoption Barriers")
        for r in es.key_risks_and_barriers[:4]:
            lines.append(f"- {r}")
        lines.append("\n### Immediate Next Validation Priority")
        lines.append(f"> {es.next_validation_priority}\n")

        # Promising Findings
        lines.append("## 2. What Appears Promising")
        for pf in self.what_appears_promising[:4]:
            lines.append(f"### [{pf.finding_id}] {pf.claim_or_hypothesis}")
            lines.append(f"- **Category**: {pf.category} | **Evidence Status**: `{pf.evidence_validation_status.value.upper()}`")
            lines.append(f"- **Relevant Segments**: {', '.join(pf.relevant_segments)}")
            lines.append(f"- **Rationale**: {pf.rationale}")
            lines.append(f"- **Next Test**: {pf.suggested_real_world_validation}\n")

        # Risks and Barriers
        lines.append("## 3. What May Not Work / Key Barriers")
        for rf in self.what_may_not_work[:4]:
            lines.append(f"### [{rf.finding_id}] {rf.concern_or_barrier}")
            lines.append(f"- **Category**: {rf.barrier_category} | **Evidence Status**: `{rf.evidence_validation_status.value.upper()}`")
            lines.append(f"- **Relevant Segments**: {', '.join(rf.relevant_segments)}")
            lines.append(f"- **Context**: {rf.rationale}")
            lines.append(f"- **Mitigation/Test**: {rf.suggested_mitigation_or_test}\n")

        # Segment Comparison Table
        lines.append("## 4. Segment Comparison")
        lines.append("| Segment | Personas (Synth) | Med. Interest | Med. Intent | Med. Affordability | Med. Barrier |")
        lines.append("| :--- | :---: | :---: | :---: | :---: | :---: |")
        for sc in self.segment_comparison:
            ms = sc.median_scores
            lines.append(
                f"| {sc.segment_name} | {sc.evaluated_personas_count}/{sc.persona_count} | "
                f"{ms.get('interest', '-')} | {ms.get('purchase_intent', '-')} | "
                f"{ms.get('affordability', '-')} | {ms.get('adoption_barrier', '-')} |"
            )
        lines.append("\n*Note: Persona counts represent synthetic simulation allocations, NOT market share or conversion rates.*\n")

        # Feature Prioritization
        lines.append("## 5. Feature Prioritization Hypotheses")
        for fp in self.feature_prioritization[:4]:
            lines.append(
                f"- **{fp.feature_name}** (`{fp.priority_tier}`): "
                f"+{fp.positive_mentions_count} / -{fp.negative_mentions_count} personas | Status: `{fp.evidence_validation_status.value}`"
            )
            lines.append(f"  *Uncertainty*: {fp.main_uncertainty} (Next step: {fp.suggested_next_validation_step})")
        lines.append("")

        # Pricing & Affordability
        pa = self.pricing_and_affordability
        lines.append("## 6. Pricing & Affordability Assessment")
        lines.append(f"- **Pricing Status**: {pa.pricing_status}")
        if pa.supplied_price:
            lines.append(f"- **Supplied Price**: {pa.supplied_price} ({pa.currency or 'INR'})")
        lines.append(f"- **Summary**: {pa.simulated_affordability_summary}")
        lines.append(f"- **Recommended Test**: {pa.recommended_wtp_experiment}\n")

        # Evidence Coverage Audit
        ec = self.evidence_coverage_audit
        lines.append("## 7. Evidence Coverage & Audit Metrics")
        lines.append(f"- **Total Findings Evaluated**: {ec.total_findings_evaluated}")
        lines.append(f"- **Evidence Coverage Ratio**: `{ec.evidence_coverage_ratio:.2f}` ({ec.coverage_formula_explanation})")
        lines.append(
            f"- **Validation Status Counts**: Supported={ec.supported_count}, Contradicted={ec.contradicted_count}, "
            f"Mixed={ec.mixed_count}, Insufficient={ec.insufficient_evidence_count}, N/A={ec.not_applicable_count}"
        )
        if ec.sources_represented:
            lines.append(f"- **Active Evidence Sources**: {', '.join(ec.sources_represented)}")
        lines.append("\n*Disclaimer: Coverage ratio is an empirical data audit measure, NOT a probability of startup success.*\n")

        # Recommended Next Experiments
        lines.append("## 8. Recommended Real-World Validation Experiments")
        for rx in self.recommended_experiments[:4]:
            lines.append(f"### [{rx.recommendation_id}] {rx.question_to_validate}")
            lines.append(f"- **Experiment Type**: {rx.suggested_experiment_type} (Target: {rx.target_segment})")
            lines.append(f"- **Strategic Value**: {rx.strategic_rationale}")
            lines.append(f"- **Metric / Observation**: {rx.measurement_metric}")
            lines.append(f"- **Decision Rule Hypothesis**: {rx.decision_rule_hypothesis}\n")

        # Core Research Questions Analysis (Fallback / LLM Grounding)
        if self.research_questions_analysis:
            lines.append("## 9. Core Research Questions Analysis")
            for idx, rqa in enumerate(self.research_questions_analysis, 1):
                basis_label = rqa.basis.value if hasattr(rqa.basis, "value") else str(rqa.basis)
                sources_str = ", ".join(rqa.supporting_sources) if rqa.supporting_sources else "None (Model Knowledge Fallback)"
                lines.append(f"### Q{idx}: {rqa.question}")
                lines.append(f"- **Basis**: `{basis_label}` | **External Validation Required**: `{rqa.requires_external_validation}`")
                lines.append(f"- **Answer**: {rqa.answer}")
                lines.append(f"- **Confidence**: {rqa.confidence}")
                lines.append(f"- **Supporting Sources**: {sources_str}")
                if rqa.assumptions:
                    lines.append("- **Assumptions**:")
                    for asm in rqa.assumptions:
                        lines.append(f"  - {asm}")
                if rqa.limitations:
                    lines.append("- **Limitations**:")
                    for lim in rqa.limitations:
                        lines.append(f"  - {lim}")
                lines.append("")

        return "\n".join(lines)
