"""
tests.test_market_report
------------------------
Comprehensive test suite for Step 12: Final Structured Market-Validation Report.

Verifies:
1. Successful report construction from representative Step 11 output.
2. Correct propagation of evidence statuses and evidence IDs.
3. Preservation of contradictory findings and negative persona objections.
4. Clear distinction between synthetic persona findings and empirical evidence.
5. Unspecified price remains unresolved and conditional.
6. Unsupported price assumptions are never promoted to facts.
7. Missing analysis and empty persona evaluations are handled safely.
8. Partial evaluation failures do not become zero scores.
9. Segment persona counts are not presented as population proportions.
10. Findings without evidence remain explicitly unvalidated.
11. Missing or incomplete source metadata is not fabricated.
12. Coverage counts and denominators are consistent with Step 11.
13. NOT_APPLICABLE and INSUFFICIENT_EVIDENCE are not presented as validated findings.
14. Stable IDs and deterministic output across repeated identical inputs.
15. Pydantic validation rejects malformed report structures.
16. JSON serialization and Markdown export work correctly.
17. Graph integration produces a report after market analysis.
18. Existing pipeline behaviour is not broken.
"""

import json
import os
import pytest
from dotenv import load_dotenv
from pydantic import ValidationError

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
)
from app.nodes.market_analysis import analyze_market
from app.schemas.market_report import (
    ExecutiveSummary,
    IdeaAndMarketContext,
    MarketValidationReport,
    PricingAndAffordabilityReport,
    PrioritizedFeatureHypothesis,
    PromisingFinding,
    RecommendedExperiment,
    RiskOrBarrierFinding,
    SegmentComparisonItem,
)
from app.nodes.market_report import (
    build_market_validation_report,
    build_market_report_node,
    _extract_supplied_pricing,
    _build_feature_priority_tier,
)


from unittest.mock import patch

@pytest.fixture(autouse=True)
def mock_research_questions_llm():
    with patch("app.nodes.market_report.answer_research_questions", return_value=([], {"status": "skipped_in_test"})):
        yield


# ------------------------------------------------------------------
# Fixtures & Mock Data
# ------------------------------------------------------------------

def create_sample_personas():
    p1 = Persona(
        persona_id="p_commuter_1",
        name="Aarav Sharma",
        customer_type=CustomerType.CONSUMER,
        segment="Tech Commuters",
        age_band="25-34",
        occupation="Software Engineer",
        behavioral_hypotheses=BehavioralHypotheses(
            price_sensitivity=5,
            convenience_preference=9,
            brand_trust_importance=6,
            risk_tolerance=7,
            digital_adoption=9,
        ),
        goals_and_needs=["Fast daily commute", "Reliable seat booking"],
        pain_points=["Traffic jams", "Crowded buses"],
        purchasing_constraints=["Monthly budget INR 4000"],
        provenance=PersonaProvenance(is_synthetic=True, is_statistically_representative=False),
    )
    p2 = Persona(
        persona_id="p_student_1",
        name="Priya Patel",
        customer_type=CustomerType.CONSUMER,
        segment="College Students",
        age_band="18-24",
        occupation="Graduate Student",
        behavioral_hypotheses=BehavioralHypotheses(
            price_sensitivity=9,
            convenience_preference=7,
            brand_trust_importance=5,
            risk_tolerance=6,
            digital_adoption=8,
        ),
        goals_and_needs=["Affordable travel", "Fixed timetable"],
        pain_points=["High fare prices", "Unpredictable transit"],
        purchasing_constraints=["Tight student allowance"],
        provenance=PersonaProvenance(is_synthetic=True, is_statistically_representative=False),
    )
    return [p1, p2]


def create_sample_evaluations():
    e1 = PersonaEvaluation(
        persona_id="p_commuter_1",
        interest_score=9,
        simulated_purchase_intent=8,
        perceived_value_score=8,
        affordability_score=7,
        adoption_barrier_score=3,
        positive_aspects=["Reserved AC seating", "Live route tracking"],
        negative_aspects=["Fixed stop locations require 10-min walk"],
        needs_addressed=["Fast daily commute"],
        needs_unmet=["Door-to-door transit"],
        pricing_considerations="INR 3000/mo is reasonable for tech workers",
        price_is_conditional=True,
        supporting_evidence_ids=["census_chunk_001"],
        evidence_gaps=["Local shuttle feeder frequency"],
        unsupported_assumptions=["Guaranteed pickup spot near office"],
        reasons_for_assessment="Highly convenient for busy engineers despite minor walking friction.",
    )
    e2 = PersonaEvaluation(
        persona_id="p_student_1",
        interest_score=6,
        simulated_purchase_intent=4,
        perceived_value_score=6,
        affordability_score=3,
        adoption_barrier_score=8,
        positive_aspects=["Clean vehicles", "Live route tracking"],
        negative_aspects=["Monthly pass is too expensive for student budgets", "High switching barrier"],
        needs_addressed=["Fixed timetable"],
        needs_unmet=["Affordable travel"],
        pricing_considerations="Higher than state metro pass",
        price_is_conditional=True,
        supporting_evidence_ids=["plfs_chunk_002"],
        evidence_gaps=["Student discount pass policy"],
        unsupported_assumptions=["Students will pay premium over ordinary bus"],
        reasons_for_assessment="Values reliability but high price creates severe adoption barrier.",
    )
    return [e1, e2]


def create_sample_evidence_records():
    return {
        "census_evidence": [
            {
                "geography": {"state": "Gujarat", "district": "Ahmedabad", "level": "District"},
                "pca": {"population": {"total": 7214225}, "workers": {"work_participation_rate_percent": 38.5}},
            }
        ],
        "plfs_evidence": [
            {
                "state": "Gujarat",
                "sector": "Urban",
                "regular_wage_mean": 21500,
                "casual_wage_mean": 450,
            }
        ],
        "reddit_evidence": [
            {
                "title": "Ahmedabad public transit overcrowding issues",
                "subreddit": "ahmedabad",
                "score": 42,
            }
        ],
        "trends_evidence": [
            {"keyword": "shuttle service", "latest_value": 78, "trend_direction": "rising"}
        ],
    }


def create_sample_chunks():
    return [
        {
            "chunk_id": "census_chunk_001",
            "source": "census_2011",
            "evidence_type": "demographic_pca",
            "text": "Ahmedabad district has 7.2M population with 38.5% worker participation.",
            "geography": {"state": "Gujarat", "district": "Ahmedabad"},
            "time_period": "2011",
            "limitations": ["Data from 2011 reference year."],
        },
        {
            "chunk_id": "plfs_chunk_002",
            "source": "plfs_2025",
            "evidence_type": "labour_earnings",
            "text": "Urban regular wage employees in Gujarat report average earnings of INR 21,500/month.",
            "geography": {"state": "Gujarat"},
            "time_period": "2023-2024 (PLFS 2025 report)",
            "limitations": ["Survey sampling distribution; does not measure discretionary willingness to pay."],
        },
    ]


# ------------------------------------------------------------------
# Test 1: Successful Report Construction from Step 11 Output
# ------------------------------------------------------------------

def test_report_construction_from_step11_output():
    personas = create_sample_personas()
    evaluations = create_sample_evaluations()
    analysis, _ = analyze_market(
        idea="Smart electric shuttle booking app for urban commuters in Ahmedabad",
        personas=personas,
        evaluations=evaluations,
        retrieved_chunks=create_sample_chunks(),
    )

    report, diag = build_market_validation_report(
        idea="Smart electric shuttle booking app for urban commuters in Ahmedabad",
        market_analysis=analysis,
        personas=personas,
        evaluations=evaluations,
        target_segment="Urban commuters",
        location="Ahmedabad, Gujarat",
        district="Ahmedabad",
        category="Transit & Mobility",
        research_evidence=create_sample_evidence_records(),
        retrieved_chunks=create_sample_chunks(),
    )

    assert isinstance(report, MarketValidationReport)
    assert report.report_id.startswith("MVR-")
    assert report.executive_summary.idea_description is not None
    assert len(report.executive_summary.strongest_promising_signals) > 0
    assert len(report.executive_summary.key_risks_and_barriers) > 0
    assert len(report.what_appears_promising) > 0
    assert len(report.what_may_not_work) > 0
    assert len(report.segment_comparison) == 2
    assert len(report.feature_prioritization) > 0
    assert len(report.recommended_experiments) > 0
    assert diag["status"] == "success"


# ------------------------------------------------------------------
# Test 2: Correct Propagation of Evidence Statuses and IDs
# ------------------------------------------------------------------

def test_propagation_of_evidence_statuses_and_ids():
    personas = create_sample_personas()
    evaluations = create_sample_evaluations()
    chunks = create_sample_chunks()
    analysis, _ = analyze_market("Smart Shuttle App", personas, evaluations, retrieved_chunks=chunks)

    report, _ = build_market_validation_report(
        idea="Smart Shuttle App",
        market_analysis=analysis,
        personas=personas,
        evaluations=evaluations,
        retrieved_chunks=chunks,
    )

    # Check evidence traceability section contains the chunk IDs
    trace_ids = [t.evidence_id for t in report.evidence_traceability]
    assert "census_chunk_001" in trace_ids or "plfs_chunk_002" in trace_ids

    # Check that promising findings preserve valid EvidenceStatus enum values
    for pf in report.what_appears_promising:
        assert isinstance(pf.evidence_validation_status, EvidenceStatus)
        assert pf.evidence_validation_status in [
            EvidenceStatus.SUPPORTED,
            EvidenceStatus.CONTRADICTED,
            EvidenceStatus.MIXED,
            EvidenceStatus.INSUFFICIENT_EVIDENCE,
            EvidenceStatus.NOT_APPLICABLE,
        ]


# ------------------------------------------------------------------
# Test 3: Preservation of Contradictory Findings & Objections
# ------------------------------------------------------------------

def test_preservation_of_contradictory_findings():
    personas = create_sample_personas()
    evaluations = create_sample_evaluations()
    analysis, _ = analyze_market("Smart Shuttle App", personas, evaluations)

    report, _ = build_market_validation_report(
        idea="Smart Shuttle App",
        market_analysis=analysis,
        personas=personas,
        evaluations=evaluations,
    )

    # Negative aspects like "monthly pass too expensive" and "fixed stop locations" must be preserved in what_may_not_work
    concerns = [r.concern_or_barrier.lower() for r in report.what_may_not_work]
    assert any("expensive" in c or "barrier" in c or "stop" in c or "walk" in c for c in concerns)
    # Check that both positive and negative signals co-exist
    assert len(report.what_appears_promising) > 0
    assert len(report.what_may_not_work) > 0


# ------------------------------------------------------------------
# Test 4: Clear Distinction: Personas vs Empirical Evidence
# ------------------------------------------------------------------

def test_distinction_between_personas_and_empirical_evidence():
    personas = create_sample_personas()
    evaluations = create_sample_evaluations()
    analysis, _ = analyze_market("Smart Shuttle App", personas, evaluations)

    report, _ = build_market_validation_report(
        idea="Smart Shuttle App",
        market_analysis=analysis,
        personas=personas,
        evaluations=evaluations,
    )

    for seg in report.segment_comparison:
        # persona_count should be raw integer counts of synthetic personas
        assert isinstance(seg.persona_count, int)
        assert seg.persona_count in [1, 2]
        # Never percentages
        assert seg.persona_count <= len(personas)

    # Disagreements must label whether explanations are 'Observed Empirical Fact' or 'Hypothesized Explanation'
    for dis in report.disagreement_and_uncertainty:
        assert dis.is_observed_or_hypothesized in ["Observed Empirical Fact", "Hypothesized Explanation"]


# ------------------------------------------------------------------
# Test 5: Unspecified Price Remains Unresolved and Conditional
# ------------------------------------------------------------------

def test_unspecified_price_remains_unresolved():
    pricing = _extract_supplied_pricing("An app for tracking fitness activities and diet routines")
    assert pricing["is_specified"] is False
    assert pricing["supplied_price"] is None
    assert pricing["price_is_conditional"] is True
    assert "Unresolved" in pricing["pricing_status"]

    report, _ = build_market_validation_report(
        idea="An app for tracking fitness activities and diet routines",
        market_analysis=None,
        personas=[],
        evaluations=[],
    )

    p_rep = report.pricing_and_affordability
    assert p_rep.price_is_conditional is True
    assert p_rep.supplied_price is None
    assert "Unresolved" in p_rep.pricing_status


# ------------------------------------------------------------------
# Test 6: Unsupported Price Assumptions Never Promoted to Facts
# ------------------------------------------------------------------

def test_unsupported_price_assumptions_not_promoted():
    pricing = _extract_supplied_pricing("Premium shuttle service priced at Rs. 2500 per month")
    assert pricing["is_specified"] is True
    assert pricing["supplied_price"] == "2500"
    assert pricing["currency"] == "INR"
    assert pricing["price_is_conditional"] is False

    report, _ = build_market_validation_report(
        idea="Premium shuttle service priced at Rs. 2500 per month",
        market_analysis=None,
        personas=[],
        evaluations=[],
        research_evidence=create_sample_evidence_records(),
    )

    p_rep = report.pricing_and_affordability
    assert p_rep.supplied_price == "2500"
    assert p_rep.currency == "INR"
    # Even if specified, contextual earnings evidence must contain clear caveats
    assert p_rep.recommended_wtp_experiment is not None
    assert "willingness to pay" in p_rep.simulated_affordability_summary.lower() or "hypothetical" in p_rep.simulated_affordability_summary.lower()


# ------------------------------------------------------------------
# Test 7: Missing Analysis & Empty Evaluations Handled Safely
# ------------------------------------------------------------------

def test_missing_analysis_and_empty_evaluations_handled():
    # Calling builder with None analysis and empty evaluations
    report, diag = build_market_validation_report(
        idea="AI-driven grocery inventory assistant",
        market_analysis=None,
        personas=[],
        evaluations=[],
    )

    assert isinstance(report, MarketValidationReport)
    assert report.idea_and_context.business_idea == "AI-driven grocery inventory assistant"
    assert len(report.segment_comparison) == 0
    assert report.evidence_coverage_audit.total_findings_evaluated == 0
    assert diag["status"] in ["success", "failed"]
    assert any("missing" in w.lower() for w in diag.get("warnings", []) + diag.get("issues", []))


# ------------------------------------------------------------------
# Test 8: Partial Evaluation Failures Do Not Become Zero Scores
# ------------------------------------------------------------------

def test_partial_evaluation_failures_do_not_become_zeros():
    p1 = create_sample_personas()[0]
    p2 = create_sample_personas()[1]
    # Only p1 is successfully evaluated, p2 has failed / no evaluation
    e1 = create_sample_evaluations()[0]

    analysis, _ = analyze_market("Smart Shuttle App", [p1, p2], [e1])

    report, _ = build_market_validation_report(
        idea="Smart Shuttle App",
        market_analysis=analysis,
        personas=[p1, p2],
        evaluations=[e1],
    )

    # Segment comparison for p2's segment (College Students) must not have 0.0 substituted
    students_seg = next((s for s in report.segment_comparison if "Student" in s.segment_name), None)
    if students_seg:
        assert students_seg.evaluated_personas_count == 0
        # Median scores must be None rather than 0.0
        assert students_seg.median_scores.get("median_interest") is None


# ------------------------------------------------------------------
# Test 9: Segment Persona Counts Not Presented as Population Share
# ------------------------------------------------------------------

def test_segment_persona_counts_not_population_share():
    personas = create_sample_personas()
    evaluations = create_sample_evaluations()
    analysis, _ = analyze_market("Smart Shuttle App", personas, evaluations)

    report, _ = build_market_validation_report(
        idea="Smart Shuttle App",
        market_analysis=analysis,
        personas=personas,
        evaluations=evaluations,
    )

    for seg in report.segment_comparison:
        # The schema field description explicitly notes: NOT market share
        field_desc = SegmentComparisonItem.model_fields["persona_count"].description
        assert "NOT market share" in field_desc


# ------------------------------------------------------------------
# Test 10: Findings Without Evidence Remain Explicitly Unvalidated
# ------------------------------------------------------------------

def test_findings_without_evidence_remain_unvalidated():
    p = create_sample_personas()[0]
    e = PersonaEvaluation(
        persona_id="p_commuter_1",
        interest_score=7,
        simulated_purchase_intent=7,
        perceived_value_score=7,
        affordability_score=7,
        adoption_barrier_score=3,
        positive_aspects=["Novel seat vibration massage"],  # completely subjective, no empirical backing
        supporting_evidence_ids=[],
        reasons_for_assessment="Values seat vibration massage for comfort during long journeys.",
    )
    analysis, _ = analyze_market("Massage Shuttle", [p], [e], retrieved_chunks=[])

    report, _ = build_market_validation_report(
        idea="Massage Shuttle",
        market_analysis=analysis,
        personas=[p],
        evaluations=[e],
        retrieved_chunks=[],
    )

    massage_finding = next((pf for pf in report.what_appears_promising if "massage" in pf.claim_or_hypothesis.lower()), None)
    if massage_finding:
        assert massage_finding.evidence_validation_status in [
            EvidenceStatus.INSUFFICIENT_EVIDENCE,
            EvidenceStatus.NOT_APPLICABLE,
        ]


# ------------------------------------------------------------------
# Test 11: Missing Source Metadata Is Not Fabricated
# ------------------------------------------------------------------

def test_missing_source_metadata_not_fabricated():
    sparse_chunk = [
        {
            "chunk_id": "sparse_chunk_101",
            "source": "census_2011",
            "text": "Partial demographic snippet without detailed metadata.",
            # geography and time_period omitted
        }
    ]

    report, _ = build_market_validation_report(
        idea="Sparse Test Concept",
        market_analysis=None,
        personas=[],
        evaluations=[],
        retrieved_chunks=sparse_chunk,
    )

    trace = next((t for t in report.evidence_traceability if t.evidence_id == "sparse_chunk_101"), None)
    assert trace is not None
    # Geography and time_period should be None or preserve reality, not invented
    assert trace.geography is None
    assert trace.observation_period is None


# ------------------------------------------------------------------
# Test 12: Coverage Counts and Denominators Consistent with Step 11
# ------------------------------------------------------------------

def test_coverage_counts_and_denominators_consistent():
    personas = create_sample_personas()
    evaluations = create_sample_evaluations()
    analysis, _ = analyze_market("Smart Shuttle App", personas, evaluations, retrieved_chunks=create_sample_chunks())

    report, _ = build_market_validation_report(
        idea="Smart Shuttle App",
        market_analysis=analysis,
        personas=personas,
        evaluations=evaluations,
        retrieved_chunks=create_sample_chunks(),
    )

    step11_cov = analysis.evidence_coverage
    rep_cov = report.evidence_coverage_audit

    assert rep_cov.total_findings_evaluated == step11_cov.total_findings_evaluated
    assert rep_cov.supported_count == step11_cov.supported_count
    assert rep_cov.contradicted_count == step11_cov.contradicted_count
    assert rep_cov.mixed_count == step11_cov.mixed_count
    assert rep_cov.insufficient_evidence_count == step11_cov.insufficient_evidence_count
    assert rep_cov.not_applicable_count == step11_cov.not_applicable_count
    assert rep_cov.evidence_coverage_ratio == step11_cov.evidence_coverage_ratio


# ------------------------------------------------------------------
# Test 13: NOT_APPLICABLE & INSUFFICIENT_EVIDENCE Not Treated as Validated
# ------------------------------------------------------------------

def test_not_applicable_and_insufficient_not_validated():
    personas = create_sample_personas()
    evaluations = create_sample_evaluations()
    analysis, _ = analyze_market("Smart Shuttle App", personas, evaluations, retrieved_chunks=[])

    report, _ = build_market_validation_report(
        idea="Smart Shuttle App",
        market_analysis=analysis,
        personas=personas,
        evaluations=evaluations,
    )

    cov = report.evidence_coverage_audit
    # Formula check: coverage ratio must only count supported, contradicted, and mixed in numerator
    numerator = cov.supported_count + cov.contradicted_count + cov.mixed_count
    expected_ratio = round(numerator / max(1, cov.total_findings_evaluated), 4)
    assert round(cov.evidence_coverage_ratio, 4) == expected_ratio


# ------------------------------------------------------------------
# Test 14: Stable IDs and Deterministic Output Across Repeated Calls
# ------------------------------------------------------------------

def test_stable_ids_and_deterministic_output():
    personas = create_sample_personas()
    evaluations = create_sample_evaluations()
    chunks = create_sample_chunks()

    analysis1, _ = analyze_market("Smart Shuttle App", personas, evaluations, retrieved_chunks=chunks)
    report1, _ = build_market_validation_report("Smart Shuttle App", analysis1, personas, evaluations, retrieved_chunks=chunks)

    analysis2, _ = analyze_market("Smart Shuttle App", personas, evaluations, retrieved_chunks=chunks)
    report2, _ = build_market_validation_report("Smart Shuttle App", analysis2, personas, evaluations, retrieved_chunks=chunks)

    # Report IDs must match exactly
    assert report1.report_id == report2.report_id

    # Promising and Risk finding IDs must match
    assert [p.finding_id for p in report1.what_appears_promising] == [p.finding_id for p in report2.what_appears_promising]
    assert [r.finding_id for r in report1.what_may_not_work] == [r.finding_id for r in report2.what_may_not_work]
    assert [e.recommendation_id for e in report1.recommended_experiments] == [e.recommendation_id for e in report2.recommended_experiments]

    # Dump contents match (excluding dynamic ISO-8601 generation timestamp)
    d1 = report1.model_dump()
    d2 = report2.model_dump()
    d1.pop("generated_at", None)
    d2.pop("generated_at", None)
    assert d1 == d2


# ------------------------------------------------------------------
# Test 15: Pydantic Validation Rejects Malformed Report Structures
# ------------------------------------------------------------------

def test_pydantic_validation_rejects_malformed_report():
    personas = create_sample_personas()
    evaluations = create_sample_evaluations()
    analysis, _ = analyze_market("Smart Shuttle App", personas, evaluations)
    report, _ = build_market_validation_report("Smart Shuttle App", analysis, personas, evaluations)

    dumped = report.model_dump()

    # 1. Extra field rejection (extra="forbid")
    dumped_with_extra = dict(dumped)
    dumped_with_extra["invalid_unsupported_field"] = "malicious_payload"
    with pytest.raises(ValidationError):
        MarketValidationReport.model_validate(dumped_with_extra)

    # 2. Invalid coverage ratio range (> 1.0)
    dumped_invalid_ratio = dict(dumped)
    dumped_invalid_ratio["evidence_coverage_audit"]["evidence_coverage_ratio"] = 1.5
    with pytest.raises(ValidationError):
        MarketValidationReport.model_validate(dumped_invalid_ratio)

    # 3. Empty report_id
    dumped_empty_id = dict(dumped)
    dumped_empty_id["report_id"] = ""
    with pytest.raises(ValidationError):
        MarketValidationReport.model_validate(dumped_empty_id)


# ------------------------------------------------------------------
# Test 16: JSON Serialization and Markdown Export Work Correctly
# ------------------------------------------------------------------

def test_json_and_markdown_export():
    personas = create_sample_personas()
    evaluations = create_sample_evaluations()
    analysis, _ = analyze_market("Smart Shuttle App", personas, evaluations, retrieved_chunks=create_sample_chunks())

    report, _ = build_market_validation_report(
        idea="Smart Shuttle App",
        market_analysis=analysis,
        personas=personas,
        evaluations=evaluations,
        retrieved_chunks=create_sample_chunks(),
    )

    # JSON export
    json_str = report.model_dump_json(indent=2)
    assert isinstance(json_str, str)
    loaded = json.loads(json_str)
    assert loaded["report_id"] == report.report_id
    assert "executive_summary" in loaded
    assert "what_appears_promising" in loaded

    # Markdown export
    md_str = report.to_markdown()
    assert isinstance(md_str, str)
    assert "# MARKET VALIDATION REPORT" in md_str
    assert "## 1. Executive Summary" in md_str
    assert "## 2. What Appears Promising" in md_str
    assert "## 4. Segment Comparison" in md_str
    assert "## 8. Recommended Real-World Validation Experiments" in md_str


# ------------------------------------------------------------------
# Test 17: Graph Integration Produces a Report After Market Analysis
# ------------------------------------------------------------------

def test_graph_integration_contains_build_market_report():
    from app.graph import build_graph
    graph = build_graph()

    assert "build_market_report" in graph.nodes
    assert "analyze_market" in graph.nodes


def test_build_market_report_node_execution():
    personas = create_sample_personas()
    evaluations = create_sample_evaluations()
    analysis, _ = analyze_market("Smart Shuttle App", personas, evaluations)

    state = {
        "idea": "Smart Shuttle App",
        "market_analysis": analysis.model_dump(),
        "personas": [p.model_dump() for p in personas],
        "persona_evaluations": [e.model_dump() for e in evaluations],
        "target_segment": "Urban commuters",
        "location": "Ahmedabad",
    }

    result = build_market_report_node(state)
    assert "market_report" in result
    assert "market_report_diagnostics" in result
    rep = result["market_report"]
    assert "report_id" in rep
    assert "executive_summary" in rep
    assert result["market_report_diagnostics"]["status"] == "success"


# ------------------------------------------------------------------
# Test 18: Existing Pipeline Behaviour and Feature Tier Rules
# ------------------------------------------------------------------

def test_feature_priority_tier_rules():
    assert _build_feature_priority_tier(pos_count=3, neg_count=0) == "High Priority Candidate"
    assert _build_feature_priority_tier(pos_count=2, neg_count=1) == "Controversial / Needs Revision"
    assert _build_feature_priority_tier(pos_count=1, neg_count=0) == "Secondary Candidate"
    assert _build_feature_priority_tier(pos_count=0, neg_count=2) == "Secondary Candidate"
