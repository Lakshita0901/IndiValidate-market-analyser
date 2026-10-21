"""
tests.test_fallback_answer
--------------------------
Unit and regression tests for LLM-native fallback answering and research question analysis.

Test coverage:
1. All sources returning empty results but LLM successfully answering (model_knowledge).
2. Partial evidence combined with general knowledge (mixed).
3. Complete evidence-backed answers (retrieved_evidence).
4. Missing API credentials or LLM failure (graceful error isolation, no crashes).
5. Unsupported statistics and fabricated citations/URLs rejected or flagged.
6. Report rendering of model-knowledge answers in Markdown.
7. API and existing pipeline regression with extended MarketValidationReport.
"""

import json
from unittest.mock import MagicMock, patch
import pytest

from app.schemas.market_report import AnswerBasis, MarketValidationReport, ResearchQuestionAnswer
from app.services.fallback_answer import (
    DEFAULT_RESEARCH_QUESTIONS,
    VALID_SOURCES,
    answer_research_questions,
    assess_evidence_sufficiency,
    build_deterministic_fallback_answer,
    clean_and_sanitize_rqa,
    extract_evidence_items,
    generate_fallback_answer,
    get_configured_llm,
)
from app.nodes.market_report import build_market_validation_report


# ─────────────────────────────────────────────────────────────────────────────
# 1. All Sources Empty -> LLM Answers via Model Knowledge
# ─────────────────────────────────────────────────────────────────────────────

def test_all_sources_empty_model_knowledge_answer():
    """
    When all research tools (Reddit, Google Trends, Census, PLFS, web search) return
    no results, the system must NOT return 'no data available'.
    The LLM must answer using learned knowledge and reasoning (basis: model_knowledge).
    """
    empty_evidence = {
        "census_evidence": [],
        "plfs_evidence": [],
        "reddit_evidence": [],
        "trends_evidence": [],
    }

    mock_llm = MagicMock()
    mock_llm.invoke.return_value.content = json.dumps({
        "question": "What is the core customer problem, and what indicates real market demand or urgency?",
        "answer": (
            "Based on domain reasoning, EV fleet operators experience severe scheduling unpredictability "
            "due to public charger queues. The primary friction is vehicle downtime eating into daily route revenues. "
            "Current live market conditions and local charging queue metrics could not be empirically verified."
        ),
        "basis": "model_knowledge",
        "supporting_sources": [],
        "assumptions": [
            "Commercial fleet operators operate under tight delivery turnaround windows.",
            "Live market figures and competitor queue times could not be empirically verified."
        ],
        "confidence": "Moderate - Reasoned hypothesis derived from logistics and EV fleet domain knowledge.",
        "limitations": [
            "Independent model reasoning only; no live external data was retrieved.",
            "Requires field validation with real prospective operators."
        ],
        "requires_external_validation": True,
    })

    answers, diag = answer_research_questions(
        idea="Smart reservation and power management for commercial EV fleet charging depots in Ahmedabad",
        questions=["What is the core customer problem, and what indicates real market demand or urgency?"],
        evidence_data=empty_evidence,
        retrieved_chunks=[],
        llm=mock_llm,
    )

    assert len(answers) == 1
    rqa = answers[0]
    assert rqa.basis == AnswerBasis.MODEL_KNOWLEDGE
    assert rqa.requires_external_validation is True
    assert len(rqa.supporting_sources) == 0
    assert "downtime" in rqa.answer.lower()
    assert "no data available" not in rqa.answer.lower()
    assert len(rqa.assumptions) >= 1
    assert len(rqa.limitations) >= 1
    assert "Moderate" in rqa.confidence


# ─────────────────────────────────────────────────────────────────────────────
# 2. Partial Evidence -> Mixed Basis
# ─────────────────────────────────────────────────────────────────────────────

def test_partial_evidence_mixed_answer():
    """
    When partial evidence exists, the LLM combines retrieved evidence with general knowledge,
    clearly distinguishing externally supported findings from model-generated inferences.
    """
    partial_evidence = {
        "plfs_evidence": [
            {
                "source": "plfs_2025",
                "indicator": "regular_salaried_avg_inr",
                "value": "24500",
                "unit": "INR/month",
                "text": "PLFS 2025 regular salaried average wage in urban Gujarat: INR 24,500/month.",
            }
        ],
        "census_evidence": [],
        "reddit_evidence": [],
        "trends_evidence": [],
    }

    mock_llm = MagicMock()
    mock_llm.invoke.return_value.content = json.dumps({
        "question": "What are the willingness-to-pay dynamics and realistic pricing considerations for this offering?",
        "answer": (
            "Empirically, PLFS 2025 data indicates an urban benchmark wage of INR 24,500/month in Gujarat. "
            "By model reasoning, a SaaS pricing tier of INR 3,000/month per fleet vehicle represents ~12% "
            "of an operator driver's base monthly cost, which is viable only if electricity and downtime savings exceed that cost. "
            "Externally verified facts from PLFS 2025 provide labor benchmarks, while specific willingness to pay remains an inference."
        ),
        "basis": "mixed",
        "supporting_sources": ["plfs_2025"],
        "assumptions": [
            "Fleet operators evaluate software costs as a percentage of total operational overhead."
        ],
        "confidence": "Moderate - Benchmark earnings verified by PLFS 2025; price acceptance remains a hypothesis.",
        "limitations": [
            "Macroeconomic wage data does not directly measure enterprise willingness to pay."
        ],
        "requires_external_validation": True,
    })

    answers, diag = answer_research_questions(
        idea="Smart EV fleet charging reservation software",
        questions=["What are the willingness-to-pay dynamics and realistic pricing considerations for this offering?"],
        evidence_data=partial_evidence,
        retrieved_chunks=[],
        llm=mock_llm,
    )

    assert len(answers) == 1
    rqa = answers[0]
    assert rqa.basis == AnswerBasis.MIXED
    assert "plfs_2025" in rqa.supporting_sources
    assert rqa.requires_external_validation is True
    assert "PLFS 2025" in rqa.answer


# ─────────────────────────────────────────────────────────────────────────────
# 3. Complete Evidence-Backed Answers
# ─────────────────────────────────────────────────────────────────────────────

def test_complete_evidence_retrieved_evidence_answer():
    """
    When strong, multiple relevant evidence items exist, the basis is retrieved_evidence.
    """
    rich_chunks = [
        {"chunk_id": "C-1", "source": "reddit", "text": "Alternative options currently used by fleet managers include diesel generators for backup charging."},
        {"chunk_id": "C-2", "source": "reddit", "text": "Public fast chargers are the primary alternative workaround but have 2-hour wait queues."},
        {"chunk_id": "C-3", "source": "google_trends", "text": "Google Trends shows rising search volume for alternative backup power and charging solutions in Gujarat."},
    ]

    mock_llm = MagicMock()
    mock_llm.invoke.return_value.content = json.dumps({
        "question": "What existing alternatives, incumbents, or workarounds do customers currently rely on?",
        "answer": (
            "Based strictly on retrieved empirical findings from Reddit and Google Trends, operators rely on "
            "public fast charging stations and backup diesel generators. Retrieved discussions document 2-hour wait queues "
            "as a primary operational bottleneck."
        ),
        "basis": "retrieved_evidence",
        "supporting_sources": ["reddit", "google_trends"],
        "assumptions": [
            "Retrieved community discussions represent authentic commercial operator workarounds."
        ],
        "confidence": "High - Corroborated by community discussions and search trend data.",
        "limitations": [
            "Reddit posts reflect qualitative operator sentiment rather than a structured audit."
        ],
        "requires_external_validation": False,
    })

    answers, diag = answer_research_questions(
        idea="EV fleet charging hub",
        questions=["What existing alternatives, incumbents, or workarounds do customers currently rely on?"],
        retrieved_chunks=rich_chunks,
        llm=mock_llm,
    )

    assert len(answers) == 1
    rqa = answers[0]
    assert rqa.basis == AnswerBasis.RETRIEVED_EVIDENCE
    assert "reddit" in rqa.supporting_sources
    assert "google_trends" in rqa.supporting_sources
    assert rqa.requires_external_validation is False


# ─────────────────────────────────────────────────────────────────────────────
# 4. Missing API Credentials or LLM Failure
# ─────────────────────────────────────────────────────────────────────────────

def test_missing_credentials_or_llm_failure_isolation():
    """
    If LLM credentials are missing or the LLM call throws an exception,
    the pipeline must NOT crash. It must return a deterministic fallback answer.
    """
    failing_llm = MagicMock()
    failing_llm.invoke.side_effect = RuntimeError("Quota exceeded or connection error")

    answers, diag = answer_research_questions(
        idea="Smart bus tracking in tier-2 cities",
        questions=["What is the core customer problem, and what indicates real market demand or urgency?"],
        evidence_data={},
        retrieved_chunks=[],
        llm=failing_llm,
    )

    assert len(answers) == 1
    rqa = answers[0]
    # Failure is isolated, clean fallback is returned
    assert rqa.basis == AnswerBasis.MODEL_KNOWLEDGE
    assert rqa.requires_external_validation is True
    assert "LLM" in rqa.answer or "domain knowledge" in rqa.answer
    assert len(rqa.supporting_sources) == 0


def test_unconfigured_llm_returns_deterministic_fallback():
    """
    When llm is None and environment keys are not present, answer generation
    succeeds with a clean fallback.
    """
    with patch.dict("os.environ", {}, clear=True):
        assert get_configured_llm() is None
        rqa = generate_fallback_answer(
            question="What is the core customer problem?",
            idea="On-demand farm machinery rental",
            basis=AnswerBasis.MODEL_KNOWLEDGE,
            supporting_sources=[],
            evidence_items=[],
            llm=None,
        )
        assert rqa.basis == AnswerBasis.MODEL_KNOWLEDGE
        assert rqa.requires_external_validation is True
        assert len(rqa.supporting_sources) == 0


# ─────────────────────────────────────────────────────────────────────────────
# 5. Unsupported Statistics and Fabricated Citations Rejected
# ─────────────────────────────────────────────────────────────────────────────

def test_clean_and_sanitize_rqa_rejects_hallucinated_citations_and_urls():
    """
    Verify that clean_and_sanitize_rqa:
    - Strips fabricated URLs.
    - Wipes hallucinated sources when basis is model_knowledge.
    - Limits supporting_sources to actually verified sources.
    - Ensures requires_external_validation is True for model_knowledge.
    """
    hallucinated_rqa = ResearchQuestionAnswer(
        question="What is the market size?",
        answer="According to https://fake-stats-reports.com/report.pdf, 87% of operators prefer this tool.",
        basis=AnswerBasis.MODEL_KNOWLEDGE,
        supporting_sources=["fake_census_url", "gartner_2026"],  # Hallucinated!
        assumptions=[],
        confidence="Very High",
        limitations=[],
        requires_external_validation=False,  # Unsound claim!
    )

    cleaned = clean_and_sanitize_rqa(hallucinated_rqa, allowed_sources=["census_2011"])

    # Fabricated sources must be wiped
    assert cleaned.supporting_sources == []
    # External validation must be forced to True
    assert cleaned.requires_external_validation is True
    # Live URL must be sanitized
    assert "https://fake-stats-reports.com" not in cleaned.answer
    assert "[Live URL omitted - unverified]" in cleaned.answer
    # Default assumptions/limitations added
    assert any("model knowledge" in a.lower() for a in cleaned.assumptions)


# ─────────────────────────────────────────────────────────────────────────────
# 6. Report Rendering of Model-Knowledge Answers
# ─────────────────────────────────────────────────────────────────────────────

def test_report_rendering_of_model_knowledge_answers():
    """
    Verify that MarketValidationReport renders Section 9: Core Research Questions Analysis
    in Markdown format with basis tags, confidence, sources, and assumptions.
    """
    rq_answer = ResearchQuestionAnswer(
        question="What are the critical customer adoption barriers?",
        answer="Primary barriers include high upfront capital expenditure and switching friction from legacy setups.",
        basis=AnswerBasis.MODEL_KNOWLEDGE,
        supporting_sources=[],
        assumptions=["Capital equipment purchases require sign-off from CFO."],
        confidence="Moderate - Derived from B2B procurement patterns.",
        limitations=["Subject to validation through customer discovery."],
        requires_external_validation=True,
    )

    report, diag = build_market_validation_report(
        idea="Solar-powered refrigeration units for rural dairies in Anand",
        research_question_answers=[rq_answer],
    )

    assert len(report.research_questions_analysis) == 1
    assert report.research_questions_analysis[0].basis == AnswerBasis.MODEL_KNOWLEDGE

    md = report.to_markdown()
    assert "## 9. Core Research Questions Analysis" in md
    assert "### Q1: What are the critical customer adoption barriers?" in md
    assert "- **Basis**: `model_knowledge`" in md
    assert "**External Validation Required**: `True`" in md
    assert "- **Supporting Sources**: None (Model Knowledge Fallback)" in md
    assert "Capital equipment purchases require sign-off" in md


# ─────────────────────────────────────────────────────────────────────────────
# 7. API and Existing Pipeline Regression
# ─────────────────────────────────────────────────────────────────────────────

def test_pipeline_integration_build_market_validation_report_runs_all_defaults():
    """
    Verify that build_market_validation_report automatically evaluates all 5 default
    research questions when none are provided, without breaking existing fields.
    """
    mock_llm = MagicMock()
    mock_llm.invoke.return_value.content = json.dumps({
        "question": "Default question",
        "answer": "Reasoned model knowledge response.",
        "basis": "model_knowledge",
        "supporting_sources": [],
        "assumptions": ["Standard market hypothesis"],
        "confidence": "Moderate",
        "limitations": ["Requires customer validation"],
        "requires_external_validation": True,
    })

    report, diag = build_market_validation_report(
        idea="Smart drone delivery for emergency medical supplies in Uttarakhand",
        llm=mock_llm,
    )

    assert len(report.research_questions_analysis) == len(DEFAULT_RESEARCH_QUESTIONS)
    for rqa in report.research_questions_analysis:
        assert isinstance(rqa, ResearchQuestionAnswer)
        assert rqa.basis in {AnswerBasis.RETRIEVED_EVIDENCE, AnswerBasis.MIXED, AnswerBasis.MODEL_KNOWLEDGE}

    # Verify existing report fields are intact
    assert report.report_id.startswith("MVR-")
    assert report.executive_summary is not None
    assert report.evidence_coverage_audit is not None
    assert report.pricing_and_affordability is not None
