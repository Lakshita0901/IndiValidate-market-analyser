"""
app.schemas.market_analysis
----------------------------
Pydantic schema for persona aggregation and evidence cross-validation (Step 11).

Provides structured representations for:
1. Overall statistical distributions across numerical evaluation metrics.
2. Clustered feature popularity and critique analysis.
3. Common concerns, switching barriers, and operational constraints.
4. Segment-by-segment comparative receptivity, affordability, and barriers.
5. Key areas of disagreement among simulated customer personas.
6. Evidence cross-validation status (supported, contradicted, mixed, insufficient).
7. Traceable evidence coverage and uncertainty metrics.

STRICT BOUNDARIES:
1. Aggregation reflects simulated reactions among synthetic personas, NOT actual customer survey percentages or real-world market shares.
2. Evidence coverage ratio measures the proportion of findings with relevant external evidence; it is NOT a probability of startup success.
3. No go/no-go recommendations or business success predictions.
"""

from enum import Enum
from typing import Any, Dict, List, Optional, Tuple
from pydantic import BaseModel, ConfigDict, Field, model_validator


class EvidenceStatus(str, Enum):
    """
    Standardized classification of external factual grounding for a market finding.
    """
    SUPPORTED = "supported"              # Direct external evidence corroborates finding
    CONTRADICTED = "contradicted"        # Direct external evidence conflicts with finding
    MIXED = "mixed"                      # External evidence contains conflicting or nuanced signals
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"  # Available evidence lacks depth, specificity, or relevance
    NOT_APPLICABLE = "not_applicable"    # Purely subjective persona preference not subject to empirical statistics


class MetricStatistics(BaseModel):
    """
    Summary descriptive statistics for an individual 1–10 ordinal evaluation metric.
    """
    model_config = ConfigDict(extra="forbid")

    metric_name: str = Field(description="Name of the metric evaluated (e.g. interest_score)")
    count: int = Field(ge=0, description="Denominator: number of valid evaluations containing this metric")
    mean: Optional[float] = Field(default=None, description="Arithmetic mean of valid scores")
    median: Optional[float] = Field(default=None, description="Median score across valid evaluations")
    min_val: Optional[int] = Field(default=None, ge=1, le=10, description="Minimum score observed")
    max_val: Optional[int] = Field(default=None, ge=1, le=10, description="Maximum score observed")
    std_dev: Optional[float] = Field(default=None, description="Sample standard deviation (or 0.0 if count < 2)")
    distribution: Dict[int, int] = Field(
        default_factory=dict,
        description="Histogram frequency count for each score from 1 to 10"
    )
    missing_count: int = Field(
        default=0,
        ge=0,
        description="Number of evaluations where this metric was missing or unpopulated"
    )


class OverallEvaluationStatistics(BaseModel):
    """
    Consolidated descriptive statistics across all evaluated numerical metrics.
    """
    model_config = ConfigDict(extra="forbid")

    total_personas_generated: int = Field(ge=0, description="Total number of synthetic personas produced")
    successful_evaluations_count: int = Field(ge=0, description="Successfully parsed and validated persona evaluations")
    failed_evaluations_count: int = Field(ge=0, description="Failed, malformed, or unparseable evaluations")

    interest_stats: MetricStatistics = Field(description="Interest score statistics (1=Uninterested, 10=High interest)")
    purchase_intent_stats: MetricStatistics = Field(description="Simulated adoption inclination (1=Definitely not, 10=High inclination)")
    perceived_value_stats: MetricStatistics = Field(description="Perceived value statistics (1=Negligible, 10=Transformative)")
    affordability_stats: MetricStatistics = Field(description="Affordability statistics (1=Unaffordable, 10=Easily affordable)")
    adoption_barrier_stats: MetricStatistics = Field(
        description="Adoption friction statistics (1=Frictionless, 10=Prohibitive barriers). NOTE: higher score = greater barrier"
    )


class EvidenceValidationItem(BaseModel):
    """
    Factual cross-validation details for an aggregated feature, concern, or segment finding.
    """
    model_config = ConfigDict(extra="forbid")

    evidence_status: EvidenceStatus = Field(description="Classification of empirical support")
    supporting_evidence_ids: List[str] = Field(default_factory=list, description="IDs of supporting chunks")
    contradicting_evidence_ids: List[str] = Field(default_factory=list, description="IDs of conflicting chunks")
    evidence_sources: List[str] = Field(default_factory=list, description="Sources cited (e.g. census_2011, plfs_2025)")
    geography: Optional[Dict[str, Any]] = Field(default=None, description="Geographic scope of cited evidence")
    time_period: Optional[str] = Field(default=None, description="Time period or survey year of cited evidence")
    caveats: List[str] = Field(default_factory=list, description="Known survey caveats, sample limits, or temporal gaps")
    explanation: str = Field(description="Explicit reasoning on how evidence relates to this finding")


class AggregatedFeature(BaseModel):
    """
    Aggregated synthesis of a proposed feature or value proposition.
    """
    model_config = ConfigDict(extra="forbid")

    feature_name: str = Field(description="Normalized feature or capability descriptor")
    positive_mentions_count: int = Field(ge=0, description="Distinct personas valuing or praising this feature")
    negative_mentions_count: int = Field(ge=0, description="Distinct personas finding this feature unnecessary or problematic")
    persona_ids: List[str] = Field(default_factory=list, description="Deduplicated list of persona IDs mentioning this feature")
    segments_represented: List[str] = Field(default_factory=list, description="Segments of personas who highlighted this feature")
    original_statements: List[str] = Field(default_factory=list, description="Verbatim excerpts from individual evaluations")
    validation: EvidenceValidationItem = Field(description="Cross-validation against retrieved empirical evidence")


class AggregatedConcern(BaseModel):
    """
    Recurring objection, friction point, or adoption barrier across personas.
    """
    model_config = ConfigDict(extra="forbid")

    concern_name: str = Field(description="Normalized concern or barrier descriptor")
    category: str = Field(
        description="Category: pricing_and_affordability, switching_costs, trust_and_reliability, usability_and_adoption, missing_functionality, operational_constraints, general"
    )
    persona_mentions_count: int = Field(ge=0, description="Distinct personas raising this concern")
    persona_ids: List[str] = Field(default_factory=list, description="Deduplicated persona IDs raising this concern")
    segments_represented: List[str] = Field(default_factory=list, description="Segments raising this concern")
    original_statements: List[str] = Field(default_factory=list, description="Verbatim concern excerpts from evaluations")
    validation: EvidenceValidationItem = Field(description="Cross-validation against retrieved empirical evidence")


class SegmentAnalysis(BaseModel):
    """
    Segment-level comparative analysis of receptivity, affordability, and barriers.
    """
    model_config = ConfigDict(extra="forbid")

    segment_name: str = Field(description="Customer segment identifier")
    persona_count: int = Field(ge=0, description="Total synthetic personas generated in this segment")
    evaluated_count: int = Field(ge=0, description="Successfully evaluated personas in this segment")
    median_interest: Optional[float] = Field(default=None, description="Median interest score (1-10)")
    median_purchase_intent: Optional[float] = Field(default=None, description="Median simulated adoption intent (1-10)")
    median_perceived_value: Optional[float] = Field(default=None, description="Median perceived value score (1-10)")
    median_affordability: Optional[float] = Field(default=None, description="Median affordability score (1-10)")
    median_adoption_barrier: Optional[float] = Field(default=None, description="Median adoption barrier score (1-10)")
    top_valued_features: List[str] = Field(default_factory=list, description="Key features valued by this segment")
    major_concerns: List[str] = Field(default_factory=list, description="Major objections or barriers in this segment")
    affordability_and_adoption_summary: str = Field(description="Synthesis of budget fit and adoption friction for segment")
    evidence_coverage_summary: str = Field(description="Summary of external factual backing for this segment")
    important_gaps: List[str] = Field(default_factory=list, description="Unverified assumptions or data gaps for this segment")


class DisagreementArea(BaseModel):
    """
    Captures topics or metrics where simulated customer personas diverged significantly.
    """
    model_config = ConfigDict(extra="forbid")

    topic: str = Field(description="Topic or dimension of disagreement")
    description: str = Field(description="Summary of the differing perspectives")
    metric_or_facet: str = Field(description="Metric or qualitative attribute with high variance")
    divergence_spread: Optional[float] = Field(default=None, description="Spread, standard deviation, or score range")
    opposing_views_or_segments: Dict[str, Any] = Field(
        default_factory=dict,
        description="Contrasting viewpoints or segment differences"
    )
    explanation: str = Field(description="Why this divergence occurs based on persona contexts")


class EvidenceCoverageMetrics(BaseModel):
    """
    Audit metrics of empirical evidence cross-validation and unresolved gaps.
    """
    model_config = ConfigDict(extra="forbid")

    total_findings_evaluated: int = Field(ge=0, description="Total aggregated findings submitted to cross-validation")
    supported_count: int = Field(ge=0, description="Findings corroborated by external evidence")
    contradicted_count: int = Field(ge=0, description="Findings contradicted by external evidence")
    mixed_count: int = Field(ge=0, description="Findings with mixed external evidence")
    insufficient_evidence_count: int = Field(ge=0, description="Findings lacking external evidence")
    not_applicable_count: int = Field(ge=0, description="Purely subjective findings not applicable to empirical data")
    evidence_coverage_ratio: float = Field(
        ge=0.0,
        le=1.0,
        description="Formula: (supported + contradicted + mixed) / max(1, total_findings). Measures data coverage, NOT startup success probability."
    )
    sources_represented: List[str] = Field(default_factory=list, description="Data sources cited across findings")
    unresolved_pricing_assumptions: List[str] = Field(default_factory=list, description="Conditional pricing or unverified rate assumptions")
    unsupported_assumptions: List[str] = Field(default_factory=list, description="Explicit assumptions without empirical grounding")
    important_evidence_gaps: List[str] = Field(default_factory=list, description="Key unaddressed empirical questions")


class MarketAnalysis(BaseModel):
    """
    Root model for Step 11: aggregated persona findings cross-validated against real evidence.
    """
    model_config = ConfigDict(extra="forbid")

    overall_statistics: OverallEvaluationStatistics = Field(description="Descriptive statistics of scores")
    features_analysis: List[AggregatedFeature] = Field(default_factory=list, description="Synthesized feature feedback")
    concerns_analysis: List[AggregatedConcern] = Field(default_factory=list, description="Synthesized objections and barriers")
    segment_analyses: List[SegmentAnalysis] = Field(default_factory=list, description="Comparative segment breakdown")
    disagreement_areas: List[DisagreementArea] = Field(default_factory=list, description="Dimensions of high persona divergence")
    evidence_coverage: EvidenceCoverageMetrics = Field(description="Factual evidence audit and gap tracking")
    diagnostics: Dict[str, Any] = Field(default_factory=dict, description="Execution diagnostics and metadata")

    @model_validator(mode="after")
    def validate_analysis_boundaries(self) -> "MarketAnalysis":
        """
        Verify that analysis does not leak startup success probabilities.
        """
        # Ensure evidence coverage ratio is documented as coverage, not probability of success
        if self.evidence_coverage.evidence_coverage_ratio < 0.0 or self.evidence_coverage.evidence_coverage_ratio > 1.0:
            raise ValueError("evidence_coverage_ratio must be between 0.0 and 1.0.")
        return self
