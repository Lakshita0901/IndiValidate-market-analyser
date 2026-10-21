"""
tests.test_gemini_fallback_and_architecture
--------------------------------------------
Comprehensive test suite verifying the strict architecture for IndiValidate:
1. Evidence available -> Gemini evidence fallback is not called.
2. Evidence absent -> Gemini context is generated and passed to Mistral.
3. Mistral generates and evaluates personas after Gemini's fallback context.
4. Mistral quota failure -> Gemini does not take over.
5. Model-generated hypotheses never receive empirical evidence labels.
6. Report generation succeeds with zero supported evidence.
7. Report timestamps render correctly (ISO 8601, eliminating 'Invalid Date').
"""

from datetime import datetime, timezone
import json
from unittest.mock import MagicMock, patch
import pytest

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
    EvidenceCoverageMetrics,
    OverallEvaluationStatistics,
    AggregatedFeature,
    AggregatedConcern,
    SegmentAnalysis,
    EvidenceValidationItem,
)
from app.schemas.gemini_context import GeminiFallbackContext
from app.nodes.gemini_context import is_evidence_sufficient, gemini_context_node, generate_gemini_context
from app.graph import route_evidence_sufficiency, build_graph
from app.nodes.persona_generation import generate_personas, generate_personas_node
from app.nodes.persona_evaluation import evaluate_personas_node
from app.nodes.market_analysis import analyze_market
from app.nodes.market_report import build_market_validation_report
from app.llm import MistralRateLimitException


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------

def create_sample_personas():
    return [
        Persona(
            persona_id=f"persona_{i}",
            name=f"Customer {i}",
            customer_type=CustomerType.CONSUMER,
            segment="Urban Commuters",
            age_band="25-34",
            occupation="Tech Worker",
            behavioral_hypotheses=BehavioralHypotheses(
                price_sensitivity=6,
                convenience_preference=9,
                brand_trust_importance=5,
                risk_tolerance=6,
                digital_adoption=8,
            ),
            goals_and_needs=["Fast daily transit"],
            pain_points=["Traffic delays"],
            purchasing_constraints=["Monthly budget INR 3500"],
            provenance=PersonaProvenance(is_synthetic=True, is_statistically_representative=False),
        )
        for i in range(1, 5)
    ]


def create_sample_evaluations():
    return [
        PersonaEvaluation(
            persona_id=f"persona_{i}",
            interest_score=7,
            simulated_purchase_intent=6,
            perceived_value_score=7,
            affordability_score=6,
            adoption_barrier_score=4,
            positive_aspects=["App convenience"],
            negative_aspects=["Fixed stop locations"],
            needs_addressed=["Speed"],
            needs_unmet=["Door-to-door transit"],
            pricing_considerations="Moderate pricing",
            price_is_conditional=True,
            supporting_evidence_ids=[],
            evidence_gaps=["Local route feeder data"],
            unsupported_assumptions=["Route coverage"],
            reasons_for_assessment="Reasonable solution for commuters.",
        )
        for i in range(1, 5)
    ]


# ------------------------------------------------------------------
# Test 1: Evidence available -> Gemini evidence fallback is not called
# ------------------------------------------------------------------

def test_evidence_available_gemini_fallback_not_called():
    """When empirical evidence is present and sufficient, route_evidence_sufficiency returns 'sufficient'."""
    state = {
        "idea": "Smart shuttle service in Ahmedabad",
        "cleaned_evidence": [
            {"evidence_id": "c1", "source": "census_2011", "text": "Demographic data"},
            {"evidence_id": "c2", "source": "plfs_2025", "text": "Wage data"},
            {"evidence_id": "c3", "source": "reddit", "text": "Qualitative transit feedback"},
        ],
        "document_chunks": [
            {"chunk_id": "chunk_1", "text": "Census info"},
            {"chunk_id": "chunk_2", "text": "PLFS info"},
        ],
        "reddit_evidence": [{"title": "Transit delays"}],
        "trends_evidence": [{"keyword": "shuttle", "value": 65}],
        "census_evidence": [{"total_pop": 7200000}],
        "plfs_evidence": [{"mean_wage": 21500}],
    }

    assert is_evidence_sufficient(state) is True
    route = route_evidence_sufficiency(state)
    assert route == "sufficient"


# ------------------------------------------------------------------
# Test 2: Evidence absent -> Gemini context is generated and passed to Mistral
# ------------------------------------------------------------------

def test_evidence_absent_gemini_context_generated_and_passed_to_mistral():
    """When evidence is absent, Gemini context is generated without touching the empirical evidence pool."""
    state = {
        "idea": "On-demand hyper-local mobile tyre repair service for two-wheelers in Bangalore",
        "target_segment": "Daily two-wheeler commuters",
        "location": "Bangalore",
        "category": "Auto Services",
        "cleaned_evidence": [],
        "document_chunks": [],
        "reddit_evidence": [],
        "trends_evidence": [],
        "census_evidence": [],
        "plfs_evidence": [],
        "normalized_evidence": [],
    }

    assert is_evidence_sufficient(state) is False
    assert route_evidence_sufficiency(state) == "insufficient"

    # Mock Gemini LLM
    mock_gemini_llm = MagicMock()
    mock_gemini_context = GeminiFallbackContext(
        market_overview="Bangalore two-wheeler commuters face frequent puncture emergencies during peak traffic.",
        target_customer_profiles=["Daily office commuter", "Gig delivery rider", "College student"],
        pain_point_hypotheses=["Stranded on flyovers", "Lack of transparent pricing", "Long delays for roadside mechanics"],
        adoption_barrier_hypotheses=["Uncertainty about mechanic arrival time", "Skepticism of tyre patch durability"],
        explicit_assumptions=["Commuters will pay a 2x premium for <15 min arrival"],
        persona_generation_guidance=["Create archetypes spanning gig workers to corporate IT professionals"],
    )
    mock_gemini_llm.invoke.return_value = MagicMock(content=mock_gemini_context.model_dump_json())

    state["gemini_llm"] = mock_gemini_llm
    node_result = gemini_context_node(state)

    assert node_result["evidence_sufficient"] is False
    assert node_result["gemini_context"] is not None
    assert "market_overview" in node_result["gemini_context"]
    assert len(node_result["gemini_context"]["pain_point_hypotheses"]) == 3

    # CRITICAL EPISTEMIC RULE: Gemini context must NOT be inserted into the empirical evidence pool!
    assert "cleaned_evidence" not in node_result
    assert "normalized_evidence" not in node_result
    assert "document_chunks" not in node_result

    # Now verify this context is passed into Mistral's persona generation prompt
    mock_mistral_llm = MagicMock()
    mock_personas_list = create_sample_personas()
    # Mock Mistral response returning personas
    mock_mistral_llm.invoke.return_value = MagicMock(
        content=json.dumps([p.model_dump() for p in mock_personas_list])
    )

    state.update(node_result)
    state["persona_llm"] = mock_mistral_llm
    state["persona_count"] = 4

    p_result = generate_personas_node(state)
    assert len(p_result["personas"]) == 4

    # Verify Mistral received the Gemini context in prompt
    invoked_prompt = mock_mistral_llm.invoke.call_args[0][0]
    assert "MODEL-GENERATED STARTUP CONTEXT & HYPOTHESES" in invoked_prompt
    assert "Bangalore two-wheeler commuters" in invoked_prompt


# ------------------------------------------------------------------
# Test 3: Mistral generates and evaluates personas after Gemini context
# ------------------------------------------------------------------

def test_mistral_generates_and_evaluates_personas_after_gemini_context():
    """Verify that Mistral remains responsible for persona generation and evaluation after Gemini fallback."""
    sample_personas = create_sample_personas()
    sample_evals = create_sample_evaluations()

    mock_mistral_llm = MagicMock()
    mock_mistral_llm.invoke.return_value = MagicMock(
        content=json.dumps([p.model_dump() for p in sample_personas])
    )

    gemini_ctx = {
        "market_overview": "Context overview",
        "pain_point_hypotheses": ["P1", "P2"],
        "adoption_barrier_hypotheses": ["B1"],
        "explicit_assumptions": ["A1"],
        "persona_generation_guidance": ["G1"],
    }

    personas, diag = generate_personas(
        idea="Smart shuttle",
        count=4,
        llm=mock_mistral_llm,
        gemini_context=gemini_ctx,
    )

    assert len(personas) == 4
    # All personas generated under Gemini fallback must have empty supporting_evidence_ids
    for p in personas:
        assert p.provenance.supporting_evidence_ids == []
        assert any("gemini" in a.lower() for a in p.provenance.explicit_assumptions)


# ------------------------------------------------------------------
# Test 4: Mistral quota failure -> Gemini does not take over
# ------------------------------------------------------------------

def test_mistral_quota_failure_gemini_does_not_take_over():
    """
    STRICT RULE: Mistral remains responsible for generating and evaluating personas.
    Gemini must NOT be called as a fallback for Mistral quota failures or provider outages.
    """
    failing_mistral_llm = MagicMock()
    failing_mistral_llm.invoke.side_effect = MistralRateLimitException("Mistral 429 Rate limit exceeded")
    if hasattr(failing_mistral_llm, "with_structured_output"):
        del failing_mistral_llm.with_structured_output

    mock_gemini_llm = MagicMock()

    state = {
        "idea": "Smart shuttle app",
        "persona_count": 4,
        "persona_llm": failing_mistral_llm,
        "gemini_llm": mock_gemini_llm,
        "gemini_context": {"market_overview": "test"},
    }

    # Run persona generation node
    result = generate_personas_node(state)

    # Must fail explicitly
    assert result["personas"] == []
    assert result["persona_generation_diagnostics"]["status"] == "failed"
    assert "stage_failures" in result
    assert "persona_generation" in result["stage_failures"]

    # Gemini MUST NOT be called to generate personas
    mock_gemini_llm.invoke.assert_not_called()


# ------------------------------------------------------------------
# Test 5: Model-generated hypotheses never receive empirical evidence labels
# ------------------------------------------------------------------

def test_model_generated_hypotheses_never_receive_empirical_labels():
    """When empirical evidence is absent (0% coverage), no finding can be labeled SUPPORTED / Corroborated."""
    personas = create_sample_personas()
    evaluations = create_sample_evaluations()

    # Create MarketAnalysis with 0 supported count using analyze_market with no evidence
    mock_analysis, _ = analyze_market(
        idea="Smart electric shuttle service in Ahmedabad",
        personas=personas,
        evaluations=evaluations,
        retrieved_chunks=[],
    )

    report, diag = build_market_validation_report(
        idea="Smart electric shuttle service in Ahmedabad",
        market_analysis=mock_analysis,
        personas=personas,
        evaluations=evaluations,
        target_segment="Urban Commuters",
        research_question_answers=[],
    )

    # Assert that NO promising finding is marked SUPPORTED
    for pf in report.what_appears_promising:
        assert pf.evidence_validation_status != EvidenceStatus.SUPPORTED
        assert pf.evidence_validation_status in [
            EvidenceStatus.INSUFFICIENT_EVIDENCE,
            EvidenceStatus.MIXED,
            EvidenceStatus.CONTRADICTED,
            EvidenceStatus.NOT_APPLICABLE,
        ]

    # Assert that NO risk finding is marked SUPPORTED
    for rf in report.what_may_not_work:
        assert rf.evidence_validation_status != EvidenceStatus.SUPPORTED

    # Assert that NO feature prioritization item is marked SUPPORTED
    for fp in report.feature_prioritization:
        assert fp.evidence_validation_status != EvidenceStatus.SUPPORTED


# ------------------------------------------------------------------
# Test 6: Report generation succeeds with zero supported evidence
# ------------------------------------------------------------------

def test_report_generation_succeeds_with_zero_supported_evidence():
    """Verify that report generation succeeds honestly when supported_count == 0."""
    personas = create_sample_personas()
    evaluations = create_sample_evaluations()

    report, diag = build_market_validation_report(
        idea="Smart electric shuttle service in Ahmedabad",
        market_analysis=None,
        personas=personas,
        evaluations=evaluations,
        research_question_answers=[],
    )

    assert diag["status"] == "success"
    assert report.report_id.startswith("MVR-")
    assert report.evidence_coverage_audit.supported_count == 0

    # Executive summary must honestly highlight insufficient evidence
    exec_summary = report.executive_summary
    assert "insufficient" in exec_summary.next_validation_priority.lower() or "validate" in exec_summary.next_validation_priority.lower()


# ------------------------------------------------------------------
# Test 7: Report timestamps render correctly (no Invalid Date)
# ------------------------------------------------------------------

def test_report_timestamps_render_correctly():
    """Verify that generated_at is a valid ISO 8601 UTC timestamp parseable by Python and JavaScript."""
    report, _ = build_market_validation_report(
        idea="Smart electric shuttle service in Ahmedabad",
        personas=create_sample_personas(),
        evaluations=create_sample_evaluations(),
        research_question_answers=[],
    )

    gen_at = report.generated_at
    assert gen_at is not None
    assert len(gen_at) > 10

    # Must parse successfully via datetime.fromisoformat without raising ValueError
    parsed_dt = datetime.fromisoformat(gen_at)
    assert parsed_dt.year >= 2026

    # Test custom ISO timestamp injection is preserved
    custom_ts = "2026-10-19T12:00:00Z"
    report2, _ = build_market_validation_report(
        idea="Smart electric shuttle service in Ahmedabad",
        personas=create_sample_personas(),
        evaluations=create_sample_evaluations(),
        research_question_answers=[],
        generated_at=custom_ts,
    )
    assert report2.generated_at == custom_ts
