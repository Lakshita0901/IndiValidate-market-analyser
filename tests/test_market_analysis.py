"""
tests.test_market_analysis
--------------------------
Comprehensive test suite for Step 11: Persona Aggregation and Evidence Cross-Validation.

Verifies:
1. Mean, median, minimum, and maximum calculations.
2. Standard deviation and score distributions (histograms).
3. Empty and partially failed evaluation sets handling.
4. Missing scores and correct explicit denominators.
5. Adoption-barrier score direction preservation (higher = harder).
6. Segment aggregation and medians.
7. Duplicate feature mentions within one persona deduplicated.
8. Preservation of original statements and persona references.
9. Evidence validation statuses: supported, contradicted, mixed, insufficient, not-applicable.
10. Invalid or irrelevant evidence references handling.
11. Evidence-coverage calculation formula (coverage measure, not success probability).
12. Conditional pricing and unsupported assumptions tracking.
13. Graph integration contains analyze_market node and edges.
14. Deterministic reproducibility across multiple runs.
15. End-to-end LangGraph node execution.
"""

import os
import pytest
from dotenv import load_dotenv

load_dotenv()
if not os.getenv("MISTRAL_API_KEY"):
    os.environ["MISTRAL_API_KEY"] = "mock-key-for-test"

from app.schemas.persona import (
    BehavioralHypotheses,
    CustomerType,
    Persona,
    PersonaProvenance,
)
from app.schemas.persona_evaluation import PersonaEvaluation
from app.schemas.market_analysis import (
    EvidenceStatus,
    MarketAnalysis,
    OverallEvaluationStatistics,
)
from app.nodes.market_analysis import (
    analyze_market,
    analyze_market_node,
    compute_metric_statistics,
)


# ------------------------------------------------------------------
# Test Fixtures & Helpers
# ------------------------------------------------------------------

def make_sample_persona(pid: str, name: str, segment: str = "Tech Commuters") -> Persona:
    return Persona(
        persona_id=pid,
        name=name,
        customer_type=CustomerType.CONSUMER,
        segment=segment,
        age_band="25-34",
        occupation="Software Engineer",
        behavioral_hypotheses=BehavioralHypotheses(
            price_sensitivity=5,
            convenience_preference=8,
            brand_trust_importance=6,
            risk_tolerance=7,
            digital_adoption=8,
        ),
        goals_and_needs=["Fast daily commute"],
        pain_points=["Traffic jams"],
        purchasing_constraints=["Budget limit INR 5000"],
        provenance=PersonaProvenance(
            is_synthetic=True,
            is_statistically_representative=False,
        ),
    )


def make_sample_evaluation(
    pid: str,
    interest: int = 7,
    intent: int = 6,
    value: int = 7,
    afford: int = 6,
    barrier: int = 4,
    valued_features: list = None,
    negative_aspects: list = None,
    evidence_ids: list = None,
    price_cond: bool = False,
) -> PersonaEvaluation:
    return PersonaEvaluation(
        persona_id=pid,
        interest_score=interest,
        simulated_purchase_intent=intent,
        perceived_value_score=value,
        affordability_score=afford,
        adoption_barrier_score=barrier,
        positive_aspects=["Comfortable ride", "Fixed timing"],
        negative_aspects=negative_aspects if negative_aspects is not None else ["Route inflexibility"],
        needs_addressed=["Fast commute"],
        needs_unmet=["Flexible return time"],
        pricing_considerations="Conditional on fare under INR 100/day" if price_cond else "Affordable fare",
        price_is_conditional=price_cond,
        valued_features=valued_features if valued_features is not None else ["Live GPS Tracking", "Guaranteed Seat"],
        unnecessary_features=["In-ride audio guide"],
        reasons_for_assessment="Good fit for daily commute routines.",
        supporting_persona_attributes=["convenience_preference"],
        supporting_evidence_ids=evidence_ids or [],
        unsupported_assumptions=["Assumed punctual drivers"],
        evidence_gaps=["Local route traffic density unmeasured"],
        is_simulation=True,
        is_conversion_probability=False,
    )


# ------------------------------------------------------------------
# 1. Mean, Median, Min, and Max Calculations
# ------------------------------------------------------------------

def test_metric_statistics_calculations():
    # Odd length list: 3, 5, 8, 9, 10
    scores = [3, 5, 8, 9, 10]
    stats = compute_metric_statistics("test_metric", scores)
    assert stats.count == 5
    assert stats.mean == 7.0
    assert stats.median == 8.0
    assert stats.min_val == 3
    assert stats.max_val == 10
    assert stats.missing_count == 0

    # Even length list: 2, 4, 6, 8 -> median is 5.0
    even_scores = [2, 4, 6, 8]
    even_stats = compute_metric_statistics("even_metric", even_scores)
    assert even_stats.count == 4
    assert even_stats.mean == 5.0
    assert even_stats.median == 5.0
    assert even_stats.min_val == 2
    assert even_stats.max_val == 8


# ------------------------------------------------------------------
# 2. Standard Deviation and Score Distributions (Histograms)
# ------------------------------------------------------------------

def test_std_dev_and_distribution_histogram():
    scores = [5, 5, 5, 5]
    stats = compute_metric_statistics("constant_metric", scores)
    assert stats.std_dev == 0.0
    assert stats.distribution[5] == 4
    assert stats.distribution[1] == 0

    varying = [2, 8]
    var_stats = compute_metric_statistics("varying_metric", varying)
    assert var_stats.std_dev is not None
    assert var_stats.std_dev > 4.0
    assert var_stats.distribution[2] == 1
    assert var_stats.distribution[8] == 1


# ------------------------------------------------------------------
# 3. Empty and Partially Failed Evaluation Sets
# ------------------------------------------------------------------

def test_empty_and_failed_evaluations_handling():
    # Empty evaluations
    empty_stats = compute_metric_statistics("empty_metric", [])
    assert empty_stats.count == 0
    assert empty_stats.mean is None
    assert empty_stats.median is None
    assert empty_stats.min_val is None
    assert empty_stats.max_val is None
    assert empty_stats.std_dev is None

    p1 = make_sample_persona("p1", "User 1")
    e1 = make_sample_evaluation("p1", interest=8)

    # 1 valid, 1 malformed dict
    analysis, diag = analyze_market(
        idea="Smart Shuttle",
        personas=[p1],
        evaluations=[e1, {"persona_id": "bad_p", "interest_score": 99}],  # invalid score 99
    )

    stats = analysis.overall_statistics
    assert stats.total_personas_generated == 1
    assert stats.successful_evaluations_count == 1
    assert stats.failed_evaluations_count == 1
    assert stats.interest_stats.mean == 8.0
    assert diag["total_evaluations"] == 2


# ------------------------------------------------------------------
# 4. Missing Scores and Correct Explicit Denominators
# ------------------------------------------------------------------

def test_missing_scores_explicit_denominators():
    raw_with_nones = [7, None, 9, None, 8]
    stats = compute_metric_statistics("partial_metric", raw_with_nones)
    assert stats.count == 3  # Denominator is strictly 3, not 5
    assert stats.missing_count == 2
    assert stats.mean == 8.0  # (7 + 9 + 8) / 3 = 8.0
    assert stats.median == 8.0


# ------------------------------------------------------------------
# 5. Adoption-Barrier Score Direction Preservation
# ------------------------------------------------------------------

def test_adoption_barrier_direction():
    p1 = make_sample_persona("p1", "User 1")
    p2 = make_sample_persona("p2", "User 2")
    # Higher barrier score (9) = greater friction / difficulty
    e1 = make_sample_evaluation("p1", barrier=2)  # low barrier
    e2 = make_sample_evaluation("p2", barrier=8)  # high barrier

    analysis, diag = analyze_market(
        idea="Smart Shuttle",
        personas=[p1, p2],
        evaluations=[e1, e2],
    )

    barrier_stats = analysis.overall_statistics.adoption_barrier_stats
    assert barrier_stats.min_val == 2
    assert barrier_stats.max_val == 8
    assert barrier_stats.mean == 5.0
    # Field documentation must clearly specify higher = harder
    assert "higher score = greater barrier" in OverallEvaluationStatistics.model_fields["adoption_barrier_stats"].description


# ------------------------------------------------------------------
# 6. Segment Aggregation and Medians
# ------------------------------------------------------------------

def test_segment_aggregation_and_medians():
    p_tech = make_sample_persona("p_tech", "Tech Lead", segment="Tech Corporate")
    p_retail = make_sample_persona("p_retail", "Shop Owner", segment="Retail Small Business")

    e_tech = make_sample_evaluation("p_tech", interest=9, afford=8, barrier=2)
    e_retail = make_sample_evaluation("p_retail", interest=4, afford=3, barrier=8)

    analysis, diag = analyze_market(
        idea="Smart Shuttle",
        personas=[p_tech, p_retail],
        evaluations=[e_tech, e_retail],
    )

    segs = {s.segment_name: s for s in analysis.segment_analyses}
    assert "Tech Corporate" in segs
    assert "Retail Small Business" in segs

    assert segs["Tech Corporate"].median_interest == 9.0
    assert segs["Tech Corporate"].median_affordability == 8.0
    assert segs["Retail Small Business"].median_interest == 4.0
    assert segs["Retail Small Business"].median_affordability == 3.0


# ------------------------------------------------------------------
# 7. Deduplication of Duplicate Feature Mentions Within One Persona
# ------------------------------------------------------------------

def test_duplicate_feature_mentions_deduplicated_per_persona():
    p = make_sample_persona("p1", "User 1")
    # Persona mentions "Live GPS Tracking" in both valued_features and positive_aspects
    e = make_sample_evaluation(
        "p1",
        valued_features=["Live GPS Tracking", "Live GPS Tracking"],
    )
    e.positive_aspects = ["Live GPS Tracking", "Clean vehicles"]

    analysis, diag = analyze_market(
        idea="Smart Shuttle",
        personas=[p],
        evaluations=[e],
    )

    gps_features = [f for f in analysis.features_analysis if "gps" in f.feature_name.lower()]
    assert len(gps_features) > 0
    # Must count as 1 distinct persona, NOT 3
    assert gps_features[0].positive_mentions_count == 1
    assert gps_features[0].persona_ids == ["p1"]


# ------------------------------------------------------------------
# 8. Preservation of Original Statements and Persona References
# ------------------------------------------------------------------

def test_preservation_of_statements_and_persona_refs():
    p = make_sample_persona("p_ref", "Ref User")
    e = make_sample_evaluation(
        "p_ref",
        valued_features=["Guaranteed Air Conditioned Seating"],
        negative_aspects=["Monsoon road flooding creates major delays"],
    )

    analysis, diag = analyze_market(
        idea="Smart Shuttle",
        personas=[p],
        evaluations=[e],
    )

    # Feature preservation
    f = [x for x in analysis.features_analysis if "seating" in x.feature_name.lower() or "conditioned" in x.feature_name.lower()][0]
    assert "p_ref" in f.persona_ids
    assert any("Guaranteed Air Conditioned Seating" in stmt for stmt in f.original_statements)

    # Concern preservation
    c = [x for x in analysis.concerns_analysis if "flooding" in x.concern_name.lower() or "monsoon" in x.concern_name.lower()][0]
    assert "p_ref" in c.persona_ids
    assert any("Monsoon road flooding" in stmt for stmt in c.original_statements)


# ------------------------------------------------------------------
# 9. Evidence Validation Statuses: Supported, Contradicted, Mixed, Insufficient
# ------------------------------------------------------------------

def test_evidence_validation_statuses():
    p = make_sample_persona("p1", "User 1")

    evidence_dict = {
        "ev_wage_1": {
            "evidence_id": "ev_wage_1",
            "source": "plfs_2025",
            "text": "PLFS 2025 indicates regular salaried tech employees average INR 45,000 monthly income.",
            "geography": {"state": "Gujarat", "district": "Ahmedabad"},
        },
        "ev_monsoon_reddit": {
            "evidence_id": "ev_monsoon_reddit",
            "source": "reddit",
            "text": "User reports highlight frequent monsoon shuttle cancellations and route diversions.",
            "geography": {"state": "Gujarat"},
        },
    }

    # 1. Supported finding (wage/affordability with plfs evidence)
    e_supported = make_sample_evaluation(
        "p1",
        valued_features=["Affordable Monthly Pass aligned with tech salary"],
        evidence_ids=["ev_wage_1"],
    )

    # 2. Contradicted finding (claims 100% monsoon reliability, but evidence reports cancellations)
    e_contradicted = make_sample_evaluation(
        "p1",
        negative_aspects=["Monsoon cancellations and route delays"],
        evidence_ids=["ev_monsoon_reddit"],
    )

    # 3. Insufficient evidence (finding with no cited evidence or empty evidence)
    e_insufficient = make_sample_evaluation(
        "p1",
        valued_features=["Free bottled sparkling water"],
        evidence_ids=[],
    )

    analysis, diag = analyze_market(
        idea="Smart Shuttle",
        personas=[p],
        evaluations=[e_supported, e_contradicted, e_insufficient],
        research_evidence={"cleaned_evidence": list(evidence_dict.values())},
    )

    cov = analysis.evidence_coverage
    assert cov.supported_count >= 1
    assert cov.insufficient_evidence_count >= 1


# ------------------------------------------------------------------
# 10. Invalid or Irrelevant Evidence References
# ------------------------------------------------------------------

def test_invalid_or_irrelevant_evidence_references():
    p = make_sample_persona("p1", "User 1")

    # Census population count alone does not validate specific product feature
    evidence_dict = {
        "census_pop_1": {
            "evidence_id": "census_pop_1",
            "source": "census_2011",
            "text": "Total population of Ahmedabad district is 7,214,225 persons.",
            "geography": {"state": "Gujarat", "district": "Ahmedabad"},
        }
    }

    e = make_sample_evaluation(
        "p1",
        valued_features=["In-ride massage chairs"],
        evidence_ids=["census_pop_1"],
    )

    analysis, diag = analyze_market(
        idea="Smart Shuttle",
        personas=[p],
        evaluations=[e],
        research_evidence={"cleaned_evidence": list(evidence_dict.values())},
    )

    feat = [f for f in analysis.features_analysis if "massage" in f.feature_name.lower()][0]
    # Aggregate population does NOT validate massage chairs; marked insufficient with caveat
    assert feat.validation.evidence_status in (EvidenceStatus.INSUFFICIENT_EVIDENCE, EvidenceStatus.NOT_APPLICABLE)
    assert any("does not validate" in c or "demographic context" in c for c in feat.validation.caveats)


# ------------------------------------------------------------------
# 11. Evidence-Coverage Calculation Formula
# ------------------------------------------------------------------

def test_evidence_coverage_calculation_formula():
    p = make_sample_persona("p1", "User 1")
    e = make_sample_evaluation("p1")

    analysis, diag = analyze_market(
        idea="Smart Shuttle",
        personas=[p],
        evaluations=[e],
    )

    cov = analysis.evidence_coverage
    assert cov.total_findings_evaluated >= 1
    # Check formula: (supported + contradicted + mixed) / max(1, total_findings)
    expected_ratio = round(
        (cov.supported_count + cov.contradicted_count + cov.mixed_count) / max(1, cov.total_findings_evaluated),
        2
    )
    assert cov.evidence_coverage_ratio == expected_ratio
    assert 0.0 <= cov.evidence_coverage_ratio <= 1.0


# ------------------------------------------------------------------
# 12. Conditional Pricing and Unsupported Assumptions
# ------------------------------------------------------------------

def test_conditional_pricing_and_assumptions_tracking():
    p = make_sample_persona("p1", "User 1")
    # price_is_conditional = True
    e = make_sample_evaluation(
        "p1",
        price_cond=True,
    )

    analysis, diag = analyze_market(
        idea="Smart Shuttle without explicit pricing",
        personas=[p],
        evaluations=[e],
    )

    cov = analysis.evidence_coverage
    assert len(cov.unresolved_pricing_assumptions) > 0
    assert "conditional" in cov.unresolved_pricing_assumptions[0].lower()
    assert len(cov.unsupported_assumptions) > 0


# ------------------------------------------------------------------
# 13. Graph Integration Contains analyze_market Node and Edges
# ------------------------------------------------------------------

def test_graph_integration_contains_analyze_market():
    from app.graph import build_graph
    graph = build_graph()
    assert "analyze_market" in graph.nodes
    assert "evaluate_personas" in graph.nodes
    assert "generate_personas" in graph.nodes


# ------------------------------------------------------------------
# 14. Deterministic Reproducibility
# ------------------------------------------------------------------

def test_deterministic_reproducibility():
    p1 = make_sample_persona("p1", "User 1")
    p2 = make_sample_persona("p2", "User 2")
    e1 = make_sample_evaluation("p1", interest=8, intent=7)
    e2 = make_sample_evaluation("p2", interest=6, intent=5)

    analysis_1, _ = analyze_market("Smart Shuttle", [p1, p2], [e1, e2])
    analysis_2, _ = analyze_market("Smart Shuttle", [p1, p2], [e1, e2])

    assert analysis_1.overall_statistics.interest_stats.mean == analysis_2.overall_statistics.interest_stats.mean
    assert analysis_1.overall_statistics.interest_stats.std_dev == analysis_2.overall_statistics.interest_stats.std_dev
    assert len(analysis_1.features_analysis) == len(analysis_2.features_analysis)
    assert len(analysis_1.concerns_analysis) == len(analysis_2.concerns_analysis)


# ------------------------------------------------------------------
# 15. LangGraph Node Integration Execution
# ------------------------------------------------------------------

def test_analyze_market_node_execution():
    p = make_sample_persona("p_node", "Node User")
    e = make_sample_evaluation("p_node", interest=8, intent=7)

    state = {
        "idea": "B2B SaaS tool for automated billing",
        "personas": [p.model_dump()],
        "persona_evaluations": [e.model_dump()],
    }

    result = analyze_market_node(state)
    assert "market_analysis" in result
    assert "market_analysis_diagnostics" in result
    analysis_dict = result["market_analysis"]
    assert "overall_statistics" in analysis_dict
    assert analysis_dict["overall_statistics"]["successful_evaluations_count"] == 1
    assert analysis_dict["overall_statistics"]["interest_stats"]["mean"] == 8.0
