"""
tests/test_structured_output_and_failures.py
--------------------------------------------
Regression tests verifying:
1. Robust JSON parsing (unescaped newlines, control characters, markdown wrapping, trailing commas).
2. Sanitized diagnostic capturing without credential leakage.
3. Native structured output fallback and parsing in fallback answers.
4. Explicit persona generation failure surfacing and stage failure tracking.
5. Final report failure state handling without false positive summaries.
6. API endpoint stage failure reporting.
"""

import json
import pytest
from unittest.mock import MagicMock
from fastapi import HTTPException

from app.schemas.persona import Persona, CustomerType
from app.schemas.market_report import AnswerBasis, ResearchQuestionAnswer, MarketValidationReport
from app.utils.json_utils import (
    parse_json_robust,
    repair_json_string,
    extract_json_candidate,
    capture_failed_response_diagnostics,
    sanitize_sensitive_text,
)
from app.nodes.persona_generation import generate_personas, generate_personas_node
from app.nodes.market_report import build_market_validation_report, build_market_report_node
from app.services.fallback_answer import generate_fallback_answer, clean_and_sanitize_rqa


def test_parse_json_robust_unescaped_newlines():
    """Verify raw unescaped newlines and control characters inside JSON strings parse without error."""
    raw = '{\n  "question": "What is the problem?",\n  "answer": "Line 1\nLine 2\r\nLine 3 with\ttab",\n  "basis": "model_knowledge"\n}'
    parsed = parse_json_robust(raw)
    assert parsed["question"] == "What is the problem?"
    assert "Line 1\nLine 2\r\nLine 3" in parsed["answer"]
    assert parsed["basis"] == "model_knowledge"


def test_parse_json_robust_markdown_fences_and_chitchat():
    """Verify markdown fences and conversational intro/outro are cleanly stripped."""
    raw = (
        "Certainly! Here is the JSON representation you requested:\n"
        "```json\n"
        "{\n"
        '  "status": "ready",\n'
        '  "count": 5\n'
        "}\n"
        "```\n"
        "Please let me know if you need any adjustments!"
    )
    parsed = parse_json_robust(raw)
    assert parsed["status"] == "ready"
    assert parsed["count"] == 5


def test_parse_json_robust_trailing_commas():
    """Verify trailing commas before closing braces/brackets are repaired."""
    raw = '{\n  "items": [1, 2, 3, ],\n  "nested": {"key": "val", },\n}'
    parsed = parse_json_robust(raw)
    assert parsed["items"] == [1, 2, 3]
    assert parsed["nested"]["key"] == "val"


def test_parse_json_robust_blank_or_invalid_raises():
    """Verify empty or completely non-JSON text raises a JSONDecodeError."""
    with pytest.raises(json.JSONDecodeError):
        parse_json_robust("")

    with pytest.raises(json.JSONDecodeError):
        parse_json_robust("This is plain text with no braces or brackets at all.")


def test_capture_failed_response_diagnostics_sanitizes_credentials():
    """Verify sensitive headers, Bearer tokens, and keys are redacted from diagnostics."""
    fake_secret = "mstrl_abcdef1234567890xyz"
    raw_response = f"Authorization: Bearer {fake_secret} returned malformed payload."
    exc = Exception(f"Failed request to api_key={fake_secret} endpoint")

    diag = capture_failed_response_diagnostics(
        provider="mistral",
        model="open-mistral-nemo",
        raw_response=raw_response,
        exc=exc,
    )

    assert diag["provider"] == "mistral"
    assert diag["model"] == "open-mistral-nemo"
    assert fake_secret not in diag["raw_preview"]
    assert "[REDACTED]" in diag["raw_preview"]
    assert fake_secret not in diag["error"]
    assert "[REDACTED]" in diag["error"]


def test_generate_fallback_answer_with_raw_control_chars():
    """Verify generate_fallback_answer handles raw control characters without crashing."""
    mock_llm = MagicMock()
    # LLM returns raw text with unescaped newlines inside strings
    mock_llm.invoke.return_value.content = (
        '{\n  "question": "What is real market demand?",\n'
        '  "answer": "Demand is high.\nMultiple commuter cohorts face delays.",\n'
        '  "basis": "model_knowledge",\n'
        '  "supporting_sources": [],\n'
        '  "assumptions": ["Assumes regular city commute schedules"],\n'
        '  "confidence": "Moderate",\n'
        '  "limitations": ["No direct telemetry"],\n'
        '  "requires_external_validation": true\n}'
    )
    # Ensure with_structured_output is bypassed for this raw parser test
    del mock_llm.with_structured_output

    rqa = generate_fallback_answer(
        question="What is real market demand?",
        idea="Smart shuttle",
        basis=AnswerBasis.MODEL_KNOWLEDGE,
        supporting_sources=[],
        evidence_items=[],
        llm=mock_llm,
    )

    assert rqa.basis == AnswerBasis.MODEL_KNOWLEDGE
    assert "Demand is high.\nMultiple commuter cohorts face delays." in rqa.answer
    assert rqa.requires_external_validation is True


def test_persona_generation_failure_surfaces_explicitly():
    """Verify that when persona generation fails, status is marked as failed and not silently empty."""
    failing_llm = MagicMock()
    failing_llm.invoke.side_effect = RuntimeError("Mistral API request timed out after 90 seconds.")
    if hasattr(failing_llm, "with_structured_output"):
        del failing_llm.with_structured_output

    personas, diag = generate_personas(
        idea="Smart shuttle",
        count=5,
        llm=failing_llm,
        max_retries=1,
    )

    assert len(personas) == 0
    assert diag["status"] == "failed"
    assert any("timed out" in issue.lower() or "failed" in issue.lower() for issue in diag["issues"])

    # Test LangGraph node execution explicitly tags stage_failures
    node_res = generate_personas_node({
        "idea": "Smart shuttle",
        "persona_count": 5,
        "persona_llm": failing_llm,
        "generate_personas": True,
    })

    assert node_res["personas"] == []
    assert node_res["persona_generation_diagnostics"]["status"] == "failed"
    assert "stage_failures" in node_res
    assert "persona_generation" in node_res["stage_failures"]


def test_report_generation_handles_missing_personas_honestly():
    """Verify that if personas are missing, executive summary does not claim favorable signals."""
    report, diag = build_market_validation_report(
        idea="Smart shuttle",
        personas=[],
        evaluations=[],
        market_analysis=None,
        research_question_answers=[],
    )

    assert diag["status"] == "failed"
    assert any("zero personas" in issue.lower() for issue in diag["issues"])
    # Executive summary must not claim favorable simulated signals
    exec_summary = report.executive_summary
    assert not any("favorable simulated interest in core features" in s.lower() for s in exec_summary.strongest_promising_signals)
    assert any("incomplete" in s.lower() or "zero personas" in s.lower() for s in exec_summary.strongest_promising_signals)


def test_api_rejects_stage_failures():
    """Verify /api/analyze endpoint raises HTTP 500 when stage_failures are present."""
    from app.api import analyze_idea_endpoint, AnalyzeRequest
    from unittest.mock import patch

    mock_graph = MagicMock()
    # Graph completes but indicates stage_failures
    mock_graph.invoke.return_value = {
        "idea": "Smart shuttle",
        "personas": [],
        "persona_generation_diagnostics": {
            "status": "failed",
            "issues": ["Mistral API request timed out."],
        },
        "stage_failures": ["persona_generation"],
        "market_report": {},
    }

    with patch("app.api.get_graph", return_value=mock_graph):
        with pytest.raises(HTTPException) as exc_info:
            analyze_idea_endpoint(AnalyzeRequest(idea="Smart shuttle"))

        assert exc_info.value.status_code == 500
        assert "persona_generation" in exc_info.value.detail


def test_next_priority_assigned_with_personas_and_zero_supported_evidence():
    """
    Exact regression test for the Step 12 bug:
    Persona generation: 4/4 successful
    Persona evaluation: 4/4 completed
    Evidence coverage: 0 supported, 17 insufficient
    Previously raised: UnboundLocalError: cannot access local variable 'next_priority'
    """
    from app.schemas.persona import Persona, CustomerType, BehavioralHypotheses, PersonaProvenance
    from app.schemas.persona_evaluation import PersonaEvaluation
    from app.schemas.market_analysis import MarketAnalysis, EvidenceCoverageMetrics, OverallEvaluationStatistics

    personas = [
        Persona(
            persona_id=f"persona_{i}",
            name=f"User {i}",
            customer_type=CustomerType.CONSUMER,
            segment="Urban Commuters",
            age_band="25-34",
            occupation="Professional",
            behavioral_hypotheses=BehavioralHypotheses(
                price_sensitivity=5,
                convenience_preference=8,
                brand_trust_importance=6,
                risk_tolerance=5,
                digital_adoption=8,
            ),
            goals_and_needs=["Fast transit"],
            pain_points=["Delays"],
            purchasing_constraints=["Budget"],
            provenance=PersonaProvenance(is_synthetic=True, is_statistically_representative=False),
        )
        for i in range(1, 5)
    ]

    evaluations = [
        PersonaEvaluation(
            persona_id=f"persona_{i}",
            interest_score=7,
            simulated_purchase_intent=6,
            perceived_value_score=7,
            affordability_score=6,
            adoption_barrier_score=4,
            positive_aspects=["App convenience"],
            negative_aspects=["Route availability"],
            needs_addressed=["Transit speed"],
            needs_unmet=["Cost"],
            pricing_considerations="Moderate",
            price_is_conditional=True,
            supporting_evidence_ids=[],
            evidence_gaps=["Local route timings"],
            unsupported_assumptions=["Route coverage"],
            reasons_for_assessment="Reasonable solution.",
        )
        for i in range(1, 5)
    ]

    from app.nodes.market_analysis import analyze_market

    mock_analysis, _ = analyze_market(
        idea="Smart shuttle booking app for urban commuters",
        personas=personas,
        evaluations=evaluations,
        retrieved_chunks=[],
    )

    report, diag = build_market_validation_report(
        idea="Smart shuttle booking app for urban commuters",
        market_analysis=mock_analysis,
        personas=personas,
        evaluations=evaluations,
        target_segment="Urban Commuters",
        research_question_answers=[],
    )

    assert diag["status"] == "success"
    exec_summary = report.executive_summary
    # Crucial assertion: next_validation_priority must be defined, non-empty, and honest
    assert isinstance(exec_summary.next_validation_priority, str)
    assert len(exec_summary.next_validation_priority) > 0
    assert "insufficient" in exec_summary.next_validation_priority.lower() or "validate" in exec_summary.next_validation_priority.lower()

    # Verify honest reporting of 0 supported evidence
    assert report.evidence_coverage_audit.supported_count == 0
    assert report.evidence_coverage_audit.insufficient_evidence_count >= 0


def test_next_priority_assigned_when_evaluations_missing():
    """Verify next_priority assignment when personas exist but evaluations are empty."""
    from app.schemas.persona import Persona, CustomerType, BehavioralHypotheses, PersonaProvenance

    personas = [
        Persona(
            persona_id="persona_1",
            name="User 1",
            customer_type=CustomerType.CONSUMER,
            segment="Commuter",
            age_band="25-34",
            occupation="Professional",
            behavioral_hypotheses=BehavioralHypotheses(
                price_sensitivity=5,
                convenience_preference=8,
                brand_trust_importance=6,
                risk_tolerance=5,
                digital_adoption=8,
            ),
            goals_and_needs=["Fast transit"],
            pain_points=["Delays"],
            purchasing_constraints=["Budget"],
            provenance=PersonaProvenance(is_synthetic=True, is_statistically_representative=False),
        )
    ]

    report, diag = build_market_validation_report(
        idea="Smart shuttle booking app",
        market_analysis=None,
        personas=personas,
        evaluations=[],
        research_question_answers=[],
    )

    assert diag["status"] == "failed"
    assert "persona evaluation produced zero evaluations" in diag["issues"][0]
    exec_summary = report.executive_summary
    assert isinstance(exec_summary.next_validation_priority, str)
    assert "evaluate" in exec_summary.next_validation_priority.lower() or "connectivity" in exec_summary.next_validation_priority.lower()


def test_next_priority_assigned_when_upstream_analysis_missing():
    """Verify next_priority assignment when upstream market_analysis is None."""
    from app.schemas.persona import Persona, CustomerType, BehavioralHypotheses, PersonaProvenance
    from app.schemas.persona_evaluation import PersonaEvaluation

    personas = [
        Persona(
            persona_id="persona_1",
            name="User 1",
            customer_type=CustomerType.CONSUMER,
            segment="Commuter",
            age_band="25-34",
            occupation="Professional",
            behavioral_hypotheses=BehavioralHypotheses(
                price_sensitivity=5,
                convenience_preference=8,
                brand_trust_importance=6,
                risk_tolerance=5,
                digital_adoption=8,
            ),
            goals_and_needs=["Fast transit"],
            pain_points=["Delays"],
            purchasing_constraints=["Budget"],
            provenance=PersonaProvenance(is_synthetic=True, is_statistically_representative=False),
        )
    ]
    evaluations = [
        PersonaEvaluation(
            persona_id="persona_1",
            interest_score=8,
            simulated_purchase_intent=7,
            perceived_value_score=8,
            affordability_score=7,
            adoption_barrier_score=3,
            positive_aspects=["App convenience"],
            negative_aspects=["Cost"],
            needs_addressed=["Transit speed"],
            needs_unmet=["Affordability"],
            pricing_considerations="Fair",
            price_is_conditional=True,
            supporting_evidence_ids=[],
            evidence_gaps=[],
            unsupported_assumptions=[],
            reasons_for_assessment="Good fit.",
        )
    ]

    report, diag = build_market_validation_report(
        idea="Smart shuttle booking app",
        market_analysis=None,
        personas=personas,
        evaluations=evaluations,
        research_question_answers=[],
    )

    assert diag["status"] == "success"
    exec_summary = report.executive_summary
    assert isinstance(exec_summary.next_validation_priority, str)
    assert len(exec_summary.next_validation_priority) > 0

