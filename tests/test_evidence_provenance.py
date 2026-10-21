import pytest
from app.schemas.market_analysis import EvidenceStatus
from app.schemas.market_report import AnswerBasis, ResearchQuestionAnswer, MarketValidationReport
from app.nodes.market_analysis import _cross_validate_finding as evaluate_evidence_for_finding
from app.services.fallback_answer import (
    assess_evidence_sufficiency as classify_evidence_basis,
    clean_and_sanitize_rqa,
    build_deterministic_fallback_answer,
)
from app.nodes.market_report import build_market_validation_report


def test_google_trends_cannot_prove_operational_claim():
    """
    Requirement 4: Do not treat a Google Trends result as proof of an operational claim.
    """
    records = {
        "ev_trends_1": {
            "source": "google_trends",
            "text": "Rising search index for charging stations in Ahmedabad.",
            "geography": "Ahmedabad",
        }
    }
    # Operational claim
    finding = "High operational reliability with 99.5% uptime hardware maintenance and zero dispatcher latency."
    result = evaluate_evidence_for_finding(finding, ["ev_trends_1"], records)

    assert result.evidence_status != EvidenceStatus.SUPPORTED
    assert result.evidence_status == EvidenceStatus.INSUFFICIENT_EVIDENCE
    assert len(result.supporting_evidence_ids) == 0
    assert any("search query activity" in c.lower() or "operational" in c.lower() for c in result.caveats)


def test_google_trends_validly_proves_search_interest():
    """
    Google Trends genuinely corroborates public search interest and keyword demand trends.
    """
    records = {
        "ev_trends_2": {
            "source": "google_trends",
            "text": "Search interest volume for commercial EV fleet charging in Gujarat grew 40% year-over-year.",
            "geography": "Gujarat",
        }
    }
    finding = "Strong growing public search trend and awareness volume for commercial charging reservation."
    result = evaluate_evidence_for_finding(finding, ["ev_trends_2"], records)

    assert result.evidence_status == EvidenceStatus.SUPPORTED
    assert "ev_trends_2" in result.supporting_evidence_ids


def test_reddit_cannot_prove_market_wide_statistic():
    """
    Requirement 4: Do not treat qualitative Reddit discussion as a verified market-wide statistic.
    """
    records = {
        "ev_reddit_1": {
            "source": "reddit",
            "text": "Multiple drivers on r/ahmedabad noted wait queues at fast charging hubs.",
            "geography": "Ahmedabad",
        }
    }
    # Market-wide statistical assertion
    finding = "Product captures a 35% nationwide market share across total addressable market penetration."
    result = evaluate_evidence_for_finding(finding, ["ev_reddit_1"], records)

    assert result.evidence_status != EvidenceStatus.SUPPORTED
    assert result.evidence_status == EvidenceStatus.INSUFFICIENT_EVIDENCE
    assert len(result.supporting_evidence_ids) == 0
    assert any("qualitative anecdotal discussion" in c.lower() or "statistical" in c.lower() for c in result.caveats)


def test_reddit_validly_proves_qualitative_user_complaints():
    """
    Reddit qualitative discussion validly corroborates user complaints and friction points.
    """
    records = {
        "ev_reddit_2": {
            "source": "reddit",
            "text": "Driver complaints on Reddit report severe 60-90 minute queues and broken charging cables.",
            "geography": "Ahmedabad",
        }
    }
    finding = "Commercial drivers face frequent queue delays and friction at public stations."
    result = evaluate_evidence_for_finding(finding, ["ev_reddit_2"], records)

    assert result.evidence_status == EvidenceStatus.SUPPORTED
    assert "ev_reddit_2" in result.supporting_evidence_ids


def test_invalid_and_missing_source_metadata_rejected():
    """
    Requirement 2 & 5: Ensure 'Empirically Supported' appears only when underlying evidence
    has valid source metadata and is not missing or unknown.
    """
    records = {
        "ev_bad_1": {
            "source": "unknown",  # Invalid source
            "text": "Some unverified text without verifiable publisher source.",
        },
        "ev_bad_2": {
            "source": "census_2011",
            "text": "",  # Empty text
        },
    }
    finding = "General market observation claim."
    result = evaluate_evidence_for_finding(finding, ["ev_bad_1", "ev_bad_2", "nonexistent_id"], records)

    assert result.evidence_status == EvidenceStatus.INSUFFICIENT_EVIDENCE
    assert len(result.supporting_evidence_ids) == 0
    assert any("lacks verified source metadata" in c.lower() for c in result.caveats)
    assert any("empty text" in c.lower() for c in result.caveats)


def test_fallback_basis_downgrades_to_model_knowledge_when_sources_missing():
    """
    Requirement 5: If evidence is missing or unverified, label finding as model_knowledge.
    """
    rqa = ResearchQuestionAnswer(
        question="What are the critical customer adoption barriers?",
        answer="Switching inertia from existing billing arrangements.",
        basis=AnswerBasis.RETRIEVED_EVIDENCE,  # Incorrectly tagged
        supporting_sources=["hallucinated_source_abc"],
        assumptions=[],
        confidence="High - Corroborated by empirical evidence.",
        limitations=[],
        requires_external_validation=False,
    )

    # Allowed verified sources do not include the hallucinated source
    cleaned = clean_and_sanitize_rqa(rqa, allowed_sources=["census_2011", "plfs_2025"])

    assert cleaned.basis == AnswerBasis.MODEL_KNOWLEDGE
    assert cleaned.supporting_sources == []
    assert cleaned.requires_external_validation is True
    # Confidence must not claim high empirical support
    assert "corroborated by empirical" not in cleaned.confidence.lower()
    assert "high" not in cleaned.confidence.lower()
    assert any("model knowledge" in a.lower() for a in cleaned.assumptions)


def test_classify_evidence_basis_guardrails():
    """
    Requirement 4: Verify classify_evidence_basis does not assign RETRIEVED_EVIDENCE
    to operational questions solely based on Google Trends, nor statistical questions solely on Reddit.
    """
    # 1. Operational question with only trends
    items_trends = [
        {"source": "google_trends", "text": "charging station uptime operational maintenance search trend"},
        {"source": "google_trends", "text": "fleet dispatcher operational delay search volume"},
        {"source": "google_trends", "text": "battery degradation charging speed trends in gujarat"},
    ]
    basis, sources, _ = classify_evidence_basis(
        "What are the critical operational and hardware maintenance risks?",
        items_trends,
    )
    # Must be MIXED, not RETRIEVED_EVIDENCE
    assert basis == AnswerBasis.MIXED
    assert "google_trends" in sources

    # 2. Market-wide statistical question with only reddit
    items_reddit = [
        {"source": "reddit", "text": "Ahmedabad drivers discuss tam total addressable market penetration"},
        {"source": "reddit", "text": "Reddit comment discussing nationwide market share of EV delivery"},
        {"source": "reddit", "text": "Fleet driver thread on market size and driver percentages"},
    ]
    basis2, sources2, _ = classify_evidence_basis(
        "What is the total addressable market size and nationwide market share?",
        items_reddit,
    )
    # Must be MIXED, not RETRIEVED_EVIDENCE
    assert basis2 == AnswerBasis.MIXED
    assert "reddit" in sources2


def test_report_export_distinguishes_basis_labels():
    """
    Requirement 3: Distinguish retrieved_evidence, mixed, and model_knowledge in exports.
    """
    rq_retrieved = ResearchQuestionAnswer(
        question="What is the core customer problem?",
        answer="Delivery queues cause revenue losses.",
        basis=AnswerBasis.RETRIEVED_EVIDENCE,
        supporting_sources=["reddit"],
        confidence="High",
        requires_external_validation=False,
    )
    rq_mixed = ResearchQuestionAnswer(
        question="What are willingness-to-pay dynamics?",
        answer="Labour context shows software budget is realistic.",
        basis=AnswerBasis.MIXED,
        supporting_sources=["plfs_2025"],
        confidence="Moderate",
        requires_external_validation=True,
    )
    rq_model = ResearchQuestionAnswer(
        question="What are key adoption barriers?",
        answer="Discom transformer sanction delays.",
        basis=AnswerBasis.MODEL_KNOWLEDGE,
        supporting_sources=[],
        confidence="Moderate",
        requires_external_validation=True,
    )

    report, _ = build_market_validation_report(
        idea="Commercial charging hubs",
        research_question_answers=[rq_retrieved, rq_mixed, rq_model],
    )

    md = report.to_markdown()
    assert "- **Basis**: `retrieved_evidence`" in md
    assert "- **Basis**: `mixed`" in md
    assert "- **Basis**: `model_knowledge`" in md

    # Check JSON serialization
    report_dict = report.model_dump()
    bases = [q["basis"] for q in report_dict["research_questions_analysis"]]
    assert bases == ["retrieved_evidence", "mixed", "model_knowledge"]
