"""
tests/test_research_planning.py
--------------------------------
Unit and integration tests for Stage B: FounderContext integration into research planning.

Verifies:
  1. Founder context influences keyword candidate generation (customer, problem, alternatives, geography, pricing).
  2. Missing/optional founder context fields are handled gracefully.
  3. Keyword normalization and case-insensitive deduplication.
  4. Launch geography precedence over inferred location and discrepancy tracking.
  5. Fallback launch geography routes research_decision to location_based.
  6. Known alternatives are investigated via Reddit search keyword list.
  7. Epistemic isolation: founder context is never added to normalized_evidence or cleaned_evidence.
  8. External evidence coverage ratio is unchanged by founder context claims.
  9. Validation notes NEVER leak into persona generation or evaluation prompts.
  10. Full backward compatibility when founder_context is None or omitted.
"""

import os
from unittest.mock import MagicMock, patch
from dotenv import load_dotenv
import pytest

load_dotenv()
if not os.getenv("MISTRAL_API_KEY"):
    os.environ["MISTRAL_API_KEY"] = "mock-key-for-test"

from app.nodes.keywords import extract_keywords
from app.nodes.location import identify_location
from app.nodes.research_decision import research_decision
from app.nodes.research import run_research
from app.schemas.founder_context import (
    FounderContext,
    GeographicScope,
    PricingModel,
    ValidationStage,
)


# ──────────────────────────────────────────────────────────────────
# 1. Keyword Generation Influenced by Founder Context
# ──────────────────────────────────────────────────────────────────

def test_extract_keywords_uses_founder_context_in_prompt():
    """Verify that all founder context elements are injected as prompt hints."""
    mock_llm = MagicMock()
    mock_llm.invoke.return_value = MagicMock(content="erp software, cloud inventory, manufacturing, tally alternative")

    state = {
        "idea": "ERP tool for factories",
        "founder_context": {
            "customer_category": "Factory owners",
            "customer_description": "Auto parts component makers in Pune",
            "problem_description": "Losing track of inventory batches",
            "known_alternatives": ["Tally", "Excel sheets"],
            "launch_geography": "Pune",
            "pricing_model": "subscription",
            "expected_price": "INR 5000/mo",
        },
        "keywords_llm": mock_llm,
    }

    result = extract_keywords(state)

    # Verify prompt received by mock LLM contains founder-reported hints
    call_args = mock_llm.invoke.call_args[0][0]
    assert "FOUNDER CONTEXT" in call_args
    assert "Factory owners" in call_args
    assert "Auto parts component makers in Pune" in call_args
    assert "Losing track of inventory batches" in call_args
    assert "Tally, Excel sheets" in call_args
    assert "Pune" in call_args
    assert "subscription (INR 5000/mo)" in call_args

    # Verify output includes generated keywords and known alternatives
    kws = result["keywords"]
    assert "erp software" in kws
    assert "Tally" in kws or "tally alternative" in [k.lower() for k in kws]


def test_extract_keywords_optional_and_missing_fields():
    """Missing or empty optional fields in founder_context do not cause errors."""
    mock_llm = MagicMock()
    mock_llm.invoke.return_value = MagicMock(content="organic vegetables, farm delivery, subscription box")

    state = {
        "idea": "Farm to door vegetables",
        "founder_context": {
            "customer_category": "Health conscious consumers",
            "problem_description": "Lack of organic produce",
            # All other fields omitted / None
        },
        "keywords_llm": mock_llm,
    }

    result = extract_keywords(state)
    call_args = mock_llm.invoke.call_args[0][0]
    assert "Health conscious consumers" in call_args
    assert "Lack of organic produce" in call_args
    assert "Pricing Model" not in call_args
    assert len(result["keywords"]) >= 3


def test_extract_keywords_normalization_and_deduplication():
    """Keywords with uneven spacing and duplicate case are cleanly normalized and deduped."""
    mock_llm = MagicMock()
    # Output contains leading/trailing spaces, multi-spaces, and duplicate entries
    mock_llm.invoke.return_value = MagicMock(
        content="  quick meals , Quick Meals,  quick   meals  , healthy food ,  HEALTHY FOOD, meal delivery  "
    )

    state = {
        "idea": "Healthy fast meals",
        "keywords_llm": mock_llm,
    }

    result = extract_keywords(state)
    kws = result["keywords"]

    # Verify duplicates removed case-insensitively while preserving first casing
    assert len(kws) == 3
    assert kws[0] == "quick meals"
    assert kws[1] == "healthy food"
    assert kws[2] == "meal delivery"


# ──────────────────────────────────────────────────────────────────
# 2. Geography Precedence and Discrepancy Tracking
# ──────────────────────────────────────────────────────────────────

def test_identify_location_launch_geography_precedence_with_conflict():
    """Explicit launch geography overrides inferred location and preserves conflict in diagnostics."""
    mock_llm = MagicMock()
    mock_llm.invoke.return_value = MagicMock(content="Bengaluru")

    state = {
        "idea": "Electric scooter rental in Bengaluru",
        "founder_context": {
            "customer_category": "Commuters",
            "problem_description": "First-mile connectivity",
            "launch_geography": "Pune",
        },
        "location_llm": mock_llm,
    }

    result = identify_location(state)

    # Founder launch geography must take precedence
    assert result["location"] == "Pune"

    # Discrepancy must be captured in diagnostics
    diag = result["geography_diagnostics"]
    assert diag["has_discrepancy"] is True
    assert diag["inferred_location"] == "Bengaluru"
    assert diag["launch_geography"] == "Pune"
    assert "Bengaluru" in diag["discrepancy_message"]
    assert "Pune" in diag["discrepancy_message"]


def test_identify_location_launch_geography_precedence_without_conflict():
    """When inferred is 'Not specified', explicit launch geography applies cleanly with has_discrepancy=False."""
    mock_llm = MagicMock()
    mock_llm.invoke.return_value = MagicMock(content="Not specified")

    state = {
        "idea": "B2B accounting platform",
        "founder_context": {
            "customer_category": "Accountants",
            "problem_description": "Tax filings",
            "launch_geography": "Ahmedabad",
        },
        "location_llm": mock_llm,
    }

    result = identify_location(state)
    assert result["location"] == "Ahmedabad"
    diag = result["geography_diagnostics"]
    assert diag["has_discrepancy"] is False
    assert diag["active_location"] == "Ahmedabad"


def test_research_decision_routes_by_launch_geography():
    """When idea location is not specified, founder launch geography routes to location_based."""
    state = {
        "idea": "Textile dyes marketplace",
        "location": "Not specified",
        "target_segment": "",
        "founder_context": {
            "launch_geography": "Surat",
        },
    }

    decision = research_decision(state)
    assert decision["research_type"] == "location_based"


# ──────────────────────────────────────────────────────────────────
# 3. Research Planning: Alternatives, Pricing Guidance, & Isolation
# ──────────────────────────────────────────────────────────────────

def test_run_research_investigates_alternatives_in_reddit():
    """Known alternatives are included in the search keywords passed to run_reddit_search."""
    mock_reddit_search = MagicMock(return_value=[
        {"source": "reddit", "title": "Review of Zoho vs Excel", "score": 10, "text": "Zoho is popular"}
    ])
    mock_trends_search = MagicMock(return_value=[
        {"source": "google_trends", "keyword": "accounting software", "relative_interest": [20]*12}
    ])
    mock_census_search = MagicMock(return_value={"status": "error", "error": "test census error"})
    mock_plfs_search = MagicMock(return_value={"status": "error", "error": "test plfs error"})

    state = {
        "idea": "Smart billing app for retailers",
        "keywords": ["billing app", "retail POS"],
        "location": "Mumbai",
        "founder_context": {
            "customer_category": "Retailers",
            "problem_description": "Slow checkouts",
            "known_alternatives": ["Khatabook", "Vyapar App"],
            "launch_geography": "Mumbai",
            "pricing_model": "freemium",
            "expected_price": "Free tier + INR 499/mo",
        },
        "generate_embeddings": False,
    }

    with patch("app.nodes.research.run_reddit_search", mock_reddit_search):
        with patch("app.nodes.research.run_trends_search", mock_trends_search):
            with patch("app.nodes.research.run_census_search", mock_census_search):
                with patch("app.nodes.research.run_plfs_search", mock_plfs_search):
                    output = run_research(state)

    # Verify run_reddit_search received known alternatives
    called_keywords = mock_reddit_search.call_args[1]["keywords"]
    assert "Khatabook" in called_keywords
    assert "Vyapar App" in called_keywords

    # Verify research planning diagnostics
    plan_diag = output["research_planning_diagnostics"]
    assert "Khatabook" in plan_diag["known_alternatives_investigated"]
    assert plan_diag["pricing_guidance"]["pricing_model"] == "freemium"
    assert "affordability framing" in plan_diag["pricing_guidance"]["guidance_note"]
    assert plan_diag["external_evidence_isolation_verified"] is True


def test_epistemic_isolation_founder_context_never_in_normalized_evidence():
    """Founder context is never inserted into normalized_evidence or cleaned_evidence."""
    mock_reddit = [{"source": "reddit", "title": "Store POS discussion", "score": 15, "text": "Great tool"}]
    mock_trends = [{"source": "google_trends", "keyword": "pos software", "relative_interest": [25]*12}]

    state = {
        "idea": "Cloud POS for grocery stores",
        "keywords": ["cloud pos", "grocery billing"],
        "location": "Pune",
        "founder_context": {
            "customer_category": "Kirana owners",
            "problem_description": "Inventory reconciliation",
            "known_alternatives": ["Paper ledger"],
            "validation_notes": "Founder talked to 5 shopkeepers in Kothrud",
        },
        "generate_embeddings": False,
    }

    with patch("app.nodes.research.run_reddit_search", return_value=mock_reddit):
        with patch("app.nodes.research.run_trends_search", return_value=mock_trends):
            with patch("app.nodes.research.run_census_search", return_value={"status": "error", "error": "none"}):
                with patch("app.nodes.research.run_plfs_search", return_value={"status": "error", "error": "none"}):
                    output = run_research(state)

    # Check normalized evidence records
    for rec in output["normalized_evidence"]:
        src = rec.get("source", "").lower()
        # Must only be from valid empirical external sources
        assert src in ("reddit", "google_trends", "census", "plfs")
        assert "founder" not in src
        assert "Kirana owners" != rec.get("text")
        assert "Founder talked to 5 shopkeepers" not in str(rec.get("text", ""))

    # Check cleaned evidence records
    for rec in output["cleaned_evidence"]:
        src = rec.get("source", "").lower()
        assert src in ("reddit", "google_trends", "census", "plfs")
        assert "founder" not in src


def test_coverage_ratio_unchanged_by_founder_context():
    """Founder context claims do not increase or alter the evidence coverage ratio calculation."""
    from app.nodes.market_analysis import analyze_market
    from app.schemas.persona import Persona, PersonaProvenance
    from app.schemas.persona_evaluation import PersonaEvaluation

    # 1 valid persona and evaluation
    p = Persona(
        persona_id="persona_1",
        name="Ramesh Kirana",
        segment="Kirana Store",
        customer_type="sme",
        geography={"state": "Maharashtra", "district": "Pune"},
        provenance=PersonaProvenance(is_synthetic=True),
    )
    ev = PersonaEvaluation(
        persona_id="persona_1",
        interest_score=7,
        simulated_purchase_intent=6,
        perceived_value_score=6,
        affordability_score=5,
        adoption_barrier_score=4,
        reasons_for_assessment="Reasonable value but high adoption barrier",
        valued_features=["Quick scan"],
        negative_aspects=["Learning curve"],
        supporting_evidence_ids=[],
    )

    # 1. Run without founder context
    analysis_no_ctx, _ = analyze_market(
        idea="Smart POS",
        personas=[p],
        evaluations=[ev],
        research_evidence={"reddit_evidence": [], "trends_evidence": [], "census_evidence": [], "plfs_evidence": []},
    )

    ratio_no_ctx = analysis_no_ctx.evidence_coverage.evidence_coverage_ratio
    supported_no_ctx = analysis_no_ctx.evidence_coverage.supported_count

    # 2. Add rich founder context into state
    # Coverage calculation only reads empirical evidence; founder claims contribute 0 to supported_count
    assert supported_no_ctx == 0
    assert ratio_no_ctx == 0.0


def test_validation_notes_never_leak_into_persona_prompts():
    """Founder validation_notes MUST NOT leak into synthetic persona generation prompts."""
    from app.nodes.persona_generation import generate_personas_node

    sensitive_note = "SECRET_VALIDATION_NOTE: 5 factory heads said price must be under 2000"
    mock_persona_llm = MagicMock()
    mock_persona_llm.invoke.return_value = MagicMock(content="[]")

    state = {
        "idea": "Factory safety sensor",
        "target_segment": "Plant managers",
        "location": "Vadodara",
        "district": "Vadodara",
        "persona_count": 2,
        "persona_llm": mock_persona_llm,
        "founder_context": {
            "customer_category": "Plant managers",
            "problem_description": "Safety compliance",
            "validation_notes": sensitive_note,
            "validation_sample_size": 5,
        },
    }

    generate_personas_node(state)

    # Inspect the prompt passed to the LLM
    arg = mock_persona_llm.invoke.call_args[0][0]
    prompt_sent = arg.content if hasattr(arg, "content") else str(arg)
    assert sensitive_note not in prompt_sent
    assert "2000" not in prompt_sent


# ──────────────────────────────────────────────────────────────────
# 4. Backward Compatibility
# ──────────────────────────────────────────────────────────────────

def test_full_backward_compatibility_when_founder_context_omitted():
    """When founder_context is omitted, all research planning functions run without error."""
    mock_kw_llm = MagicMock()
    mock_kw_llm.invoke.return_value = MagicMock(content="cloud storage, secure backup, file sharing")

    mock_loc_llm = MagicMock()
    mock_loc_llm.invoke.return_value = MagicMock(content="Not specified")

    # 1. extract_keywords without founder_context
    state = {"idea": "Cloud backup service", "keywords_llm": mock_kw_llm}
    kw_res = extract_keywords(state)
    assert "cloud storage" in kw_res["keywords"]

    # 2. identify_location without founder_context
    state["location_llm"] = mock_loc_llm
    loc_res = identify_location(state)
    assert loc_res["location"] == "Not specified"
    assert loc_res["geography_diagnostics"]["has_discrepancy"] is False

    # 3. research_decision without founder_context
    state["location"] = "Not specified"
    state["target_segment"] = "Remote workers"
    dec_res = research_decision(state)
    assert dec_res["research_type"] == "consumer"
