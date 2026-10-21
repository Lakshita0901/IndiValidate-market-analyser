"""
tests.test_persona_evaluation
-----------------------------
Comprehensive test suite for Step 10: Multi-Persona Evaluation and Intent Simulation.

Verifies:
1. Persona evaluation schema validation and score bounds (1-10 integer scales).
2. Score direction and validation (adoption barrier, value, affordability, etc.).
3. Correct persona-to-evaluation association.
4. Diverse evaluations across different personas.
5. Evidence citation integrity.
6. Handling of missing evidence and uncertainty flags.
7. Handling of conflicting evidence.
8. Unspecified price behavior (price_is_conditional=True).
9. Malformed LLM output and bounded retry behavior.
10. Isolated evaluation failures and partial generation success.
11. Missing credentials and provider failure handling.
12. No invented evidence IDs in supporting_evidence_ids.
13. No claim that simulated intent is actual conversion probability.
14. Graph integration after persona generation.
15. End-to-end node integration.
"""

import json
import os
import pytest
from dotenv import load_dotenv
from pydantic import ValidationError

load_dotenv()
# Ensure import of nodes with top-level LLM succeeds during test collection
if not os.getenv("MISTRAL_API_KEY"):
    os.environ["MISTRAL_API_KEY"] = "mock-key-for-test"

from app.schemas.persona import (
    BehavioralHypotheses,
    CustomerType,
    Persona,
    PersonaProvenance,
)
from app.schemas.persona_evaluation import PersonaEvaluation
from app.nodes.persona_evaluation import (
    evaluate_personas,
    evaluate_personas_node,
    is_price_specified,
)
from app.rag.retriever import RetrievedChunk


# ------------------------------------------------------------------
# Test Fixtures & Helpers
# ------------------------------------------------------------------

def make_sample_persona(pid: str, name: str, price_sens: int = 5, digital: int = 5) -> Persona:
    return Persona(
        persona_id=pid,
        name=name,
        customer_type=CustomerType.CONSUMER,
        segment="Young Urban Professionals",
        age_band="25-34",
        occupation="Software Developer",
        behavioral_hypotheses=BehavioralHypotheses(
            price_sensitivity=price_sens,
            convenience_preference=8,
            brand_trust_importance=6,
            risk_tolerance=7,
            digital_adoption=digital,
        ),
        goals_and_needs=["Fast daily commute", "Cost predictability"],
        pain_points=["Traffic delays", "Unreliable public buses"],
        purchasing_constraints=["Monthly commute budget under INR 4,000"],
        provenance=PersonaProvenance(
            is_synthetic=True,
            is_statistically_representative=False,
        ),
    )


def make_valid_evaluation_dict(pid: str = "persona_1") -> dict:
    return {
        "persona_id": pid,
        "interest_score": 8,
        "simulated_purchase_intent": 7,
        "perceived_value_score": 8,
        "affordability_score": 6,
        "adoption_barrier_score": 3,
        "positive_aspects": ["Saves 30 minutes daily", "Predictable scheduling"],
        "negative_aspects": ["Requires downloading dedicated app"],
        "needs_addressed": ["Fast daily commute"],
        "needs_unmet": ["Inter-city travel coverage"],
        "pricing_considerations": "Willing to pay up to INR 150 per trip",
        "price_is_conditional": False,
        "valued_features": ["Live GPS tracking", "Guaranteed seat"],
        "unnecessary_features": ["In-ride entertainment"],
        "reasons_for_assessment": "The service directly solves daily commute delays and fits within tech comfort level.",
        "supporting_persona_attributes": ["convenience_preference", "digital_adoption"],
        "supporting_evidence_ids": ["chunk_1"],
        "unsupported_assumptions": ["Assumed routes cover tech parks"],
        "evidence_gaps": ["Peak hour frequency data unavailable"],
        "is_simulation": True,
        "is_conversion_probability": False,
    }


# ------------------------------------------------------------------
# 1. Schema Validation and Score Bounds
# ------------------------------------------------------------------

def test_evaluation_schema_validation_and_bounds():
    valid_data = make_valid_evaluation_dict()
    eval_obj = PersonaEvaluation.model_validate(valid_data)
    assert eval_obj.persona_id == "persona_1"
    assert eval_obj.interest_score == 8
    assert eval_obj.simulated_purchase_intent == 7
    assert eval_obj.is_simulation is True
    assert eval_obj.is_conversion_probability is False

    # Score below 1 must fail
    bad_low = make_valid_evaluation_dict()
    bad_low["interest_score"] = 0
    with pytest.raises(ValidationError):
        PersonaEvaluation.model_validate(bad_low)

    # Score above 10 must fail
    bad_high = make_valid_evaluation_dict()
    bad_high["adoption_barrier_score"] = 11
    with pytest.raises(ValidationError):
        PersonaEvaluation.model_validate(bad_high)


# ------------------------------------------------------------------
# 2. Score Direction and Extra Fields Forbidden
# ------------------------------------------------------------------

def test_score_direction_and_extra_fields():
    # Extra unexpected fields must be rejected (extra="forbid")
    data_with_extra = make_valid_evaluation_dict()
    data_with_extra["real_world_conversion_rate"] = 0.45
    with pytest.raises(ValidationError):
        PersonaEvaluation.model_validate(data_with_extra)

    # Empty reasons must fail
    bad_reasons = make_valid_evaluation_dict()
    bad_reasons["reasons_for_assessment"] = "   "
    with pytest.raises(ValidationError):
        PersonaEvaluation.model_validate(bad_reasons)


# ------------------------------------------------------------------
# 3. Correct Persona-to-Evaluation Association
# ------------------------------------------------------------------

def test_persona_to_evaluation_association():
    p1 = make_sample_persona("persona_alpha", "Alpha User")
    p2 = make_sample_persona("persona_beta", "Beta User")

    def mock_llm(prompt: str) -> str:
        if "persona_alpha" in prompt:
            return json.dumps(make_valid_evaluation_dict("persona_alpha"))
        else:
            return json.dumps(make_valid_evaluation_dict("persona_beta"))

    evals, diag = evaluate_personas(
        idea="Electric shuttle for tech workers",
        personas=[p1, p2],
        llm=mock_llm,
    )

    assert len(evals) == 2
    assert evals[0].persona_id == "persona_alpha"
    assert evals[1].persona_id == "persona_beta"
    assert diag["evaluated_count"] == 2


# ------------------------------------------------------------------
# 4. Diverse Evaluations Across Different Personas
# ------------------------------------------------------------------

def test_diverse_evaluations_for_different_personas():
    p_budget = make_sample_persona("p_budget", "Cost-Sensitive Worker", price_sens=9, digital=3)
    p_premium = make_sample_persona("p_premium", "Senior Tech Lead", price_sens=2, digital=9)

    def mock_diverse_llm(prompt: str) -> str:
        if "p_budget" in prompt:
            d = make_valid_evaluation_dict("p_budget")
            d["interest_score"] = 4
            d["simulated_purchase_intent"] = 3
            d["affordability_score"] = 2
            d["adoption_barrier_score"] = 8
            d["reasons_for_assessment"] = "Budget constraints make this difficult to adopt."
            return json.dumps(d)
        else:
            d = make_valid_evaluation_dict("p_premium")
            d["interest_score"] = 9
            d["simulated_purchase_intent"] = 8
            d["affordability_score"] = 9
            d["adoption_barrier_score"] = 2
            d["reasons_for_assessment"] = "High disposable income and urgent need for convenience."
            return json.dumps(d)

    evals, diag = evaluate_personas(
        idea="Premium on-demand workplace shuttle service",
        personas=[p_budget, p_premium],
        llm=mock_diverse_llm,
    )

    assert len(evals) == 2
    assert evals[0].interest_score != evals[1].interest_score
    assert evals[0].affordability_score < evals[1].affordability_score
    assert evals[0].adoption_barrier_score > evals[1].adoption_barrier_score


# ------------------------------------------------------------------
# 5. Evidence Citation Integrity & Stripping Invented IDs
# ------------------------------------------------------------------

def test_evidence_citation_integrity_and_invented_ids():
    p = make_sample_persona("p_1", "Test User")

    fake_chunk = RetrievedChunk(
        chunk_id="valid_chunk_101",
        document_id="doc_1",
        text="PLFS survey shows 65% tech workers commute by private vehicles.",
        distance=0.15,
        source="plfs_2025",
    )

    def mock_llm_with_invented_id(prompt: str) -> str:
        d = make_valid_evaluation_dict("p_1")
        # Claims valid_chunk_101 AND a totally fabricated invented_chunk_999
        d["supporting_evidence_ids"] = ["valid_chunk_101", "invented_chunk_999"]
        return json.dumps(d)

    evals, diag = evaluate_personas(
        idea="Electric shuttle service",
        personas=[p],
        retrieved_chunks=[fake_chunk],
        llm=mock_llm_with_invented_id,
    )

    assert len(evals) == 1
    # valid_chunk_101 kept
    assert "valid_chunk_101" in evals[0].supporting_evidence_ids
    # invented_chunk_999 removed from supporting_evidence_ids
    assert "invented_chunk_999" not in evals[0].supporting_evidence_ids
    # moved to unsupported assumptions
    assert any("invented_chunk_999" in a for a in evals[0].unsupported_assumptions)


# ------------------------------------------------------------------
# 6. Handling of Missing Evidence and Uncertainty Flags
# ------------------------------------------------------------------

def test_missing_evidence_and_uncertainty_handling():
    p = make_sample_persona("p_1", "Test User")

    def mock_llm(prompt: str) -> str:
        d = make_valid_evaluation_dict("p_1")
        d["supporting_evidence_ids"] = []
        d["evidence_gaps"] = ["No district-level commuter statistics available for this micro-market"]
        return json.dumps(d)

    evals, diag = evaluate_personas(
        idea="Hyperlocal electric boat ferry",
        personas=[p],
        retrieved_chunks=[],
        research_evidence={},
        llm=mock_llm,
    )

    assert len(evals) == 1
    assert len(evals[0].supporting_evidence_ids) == 0
    assert "No district-level commuter statistics available for this micro-market" in evals[0].evidence_gaps


# ------------------------------------------------------------------
# 7. Handling of Conflicting Evidence
# ------------------------------------------------------------------

def test_conflicting_evidence_preserved():
    p = make_sample_persona("p_1", "Test User")

    def mock_conflict_llm(prompt: str) -> str:
        d = make_valid_evaluation_dict("p_1")
        d["negative_aspects"] = ["Reddit reports indicate high cancellation rates in monsoon, conflicting with claims of 99% reliability."]
        d["reasons_for_assessment"] = "Persona is interested, but empirical user reports contradict claimed service uptime."
        return json.dumps(d)

    evals, diag = evaluate_personas(
        idea="Monsoon-ready shuttle system",
        personas=[p],
        llm=mock_conflict_llm,
    )

    assert len(evals) == 1
    assert "contradict" in evals[0].reasons_for_assessment or "conflicting" in evals[0].negative_aspects[0]


# ------------------------------------------------------------------
# 8. Unspecified Price Detection and Behavior
# ------------------------------------------------------------------

def test_unspecified_price_detection_and_behavior():
    # Price unspecified idea
    unspecified_idea = "AI-powered tool that summarizes complex tax compliance for small businesses"
    assert is_price_specified(unspecified_idea) is False

    # Price specified ideas
    specified_idea_1 = "SaaS for accountants priced at Rs. 499 per month"
    assert is_price_specified(specified_idea_1) is True

    specified_idea_2 = "Accounting software subscription of $29 per user"
    assert is_price_specified(specified_idea_2) is True

    p = make_sample_persona("p_1", "Small Business Owner")

    def mock_llm(prompt: str) -> str:
        d = make_valid_evaluation_dict("p_1")
        d["price_is_conditional"] = False  # Model didn't set it
        d["pricing_considerations"] = None
        return json.dumps(d)

    evals, diag = evaluate_personas(
        idea=unspecified_idea,
        personas=[p],
        llm=mock_llm,
    )

    assert len(evals) == 1
    assert diag["price_specified_in_idea"] is False
    # Enforced to True because price was unspecified in idea
    assert evals[0].price_is_conditional is True
    assert "Conditional" in evals[0].pricing_considerations


# ------------------------------------------------------------------
# 9. Malformed LLM Output and Bounded Retries
# ------------------------------------------------------------------

def test_malformed_llm_output_and_bounded_retry():
    p = make_sample_persona("p_1", "Test User")
    call_count = 0

    def mock_failing_then_succeeding_llm(prompt: str) -> str:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return "Not valid JSON at all: Here is my review..."
        return json.dumps(make_valid_evaluation_dict("p_1"))

    evals, diag = evaluate_personas(
        idea="Smart commute shuttle",
        personas=[p],
        llm=mock_failing_then_succeeding_llm,
        max_retries=2,
    )

    assert len(evals) == 1
    assert call_count == 2
    assert any("JSON decoding error" in issue for issue in diag["issues"])


# ------------------------------------------------------------------
# 10. Isolated Evaluation Failures and Partial Success
# ------------------------------------------------------------------

def test_isolated_evaluation_failures_and_partial_success():
    p1 = make_sample_persona("p_good", "Good User")
    p2 = make_sample_persona("p_bad", "Failing User")

    def mock_partial_llm(prompt: str) -> str:
        if "p_good" in prompt:
            return json.dumps(make_valid_evaluation_dict("p_good"))
        else:
            return "Total garbage text that never parses as json"

    evals, diag = evaluate_personas(
        idea="Smart commute shuttle",
        personas=[p1, p2],
        llm=mock_partial_llm,
        max_retries=1,
    )

    assert len(evals) == 1
    assert evals[0].persona_id == "p_good"
    assert diag["evaluated_count"] == 1
    assert diag["evaluation_failures_count"] == 1


# ------------------------------------------------------------------
# 11. Missing Credentials Handling
# ------------------------------------------------------------------

def test_missing_credentials_handling(monkeypatch):
    monkeypatch.delenv("MISTRAL_API_KEY", raising=False)

    p = make_sample_persona("p_1", "Test User")

    evals, diag = evaluate_personas(
        idea="Some business idea",
        personas=[p],
        llm=None,
    )

    assert len(evals) == 0
    assert any("Mistral API key not found" in issue for issue in diag["issues"])


# ------------------------------------------------------------------
# 12. No Claim That Simulated Intent is Actual Conversion Probability
# ------------------------------------------------------------------

def test_no_claim_of_conversion_probability():
    bad_data = make_valid_evaluation_dict()
    bad_data["is_conversion_probability"] = True

    with pytest.raises(ValidationError):
        PersonaEvaluation.model_validate(bad_data)

    bad_sim = make_valid_evaluation_dict()
    bad_sim["is_simulation"] = False

    with pytest.raises(ValidationError):
        PersonaEvaluation.model_validate(bad_sim)


# ------------------------------------------------------------------
# 13. Score Averages in Diagnostics
# ------------------------------------------------------------------

def test_score_averages_in_diagnostics():
    p1 = make_sample_persona("p_1", "User 1")
    p2 = make_sample_persona("p_2", "User 2")

    def mock_llm(prompt: str) -> str:
        if "p_1" in prompt:
            d = make_valid_evaluation_dict("p_1")
            d["interest_score"] = 6
            d["simulated_purchase_intent"] = 4
            return json.dumps(d)
        else:
            d = make_valid_evaluation_dict("p_2")
            d["interest_score"] = 10
            d["simulated_purchase_intent"] = 8
            return json.dumps(d)

    evals, diag = evaluate_personas(
        idea="Commute service",
        personas=[p1, p2],
        llm=mock_llm,
    )

    assert len(evals) == 2
    avgs = diag["score_averages"]
    assert avgs["avg_interest_score"] == 8.0
    assert avgs["avg_simulated_purchase_intent"] == 6.0


# ------------------------------------------------------------------
# 14. Graph Integration Verification
# ------------------------------------------------------------------

def test_graph_integration_contains_evaluate_personas():
    from app.graph import build_graph
    graph = build_graph()
    # Ensure evaluate_personas is an existing node in graph
    assert "evaluate_personas" in graph.nodes
    assert "generate_personas" in graph.nodes


# ------------------------------------------------------------------
# 15. LangGraph Node Integration
# ------------------------------------------------------------------

def test_evaluate_personas_node_execution():
    p = make_sample_persona("p_node", "Node Test User")

    def mock_llm(prompt: str) -> str:
        return json.dumps(make_valid_evaluation_dict("p_node"))

    state = {
        "idea": "B2B SaaS for manufacturing workflow automation",
        "personas": [p.model_dump()],
        "evaluation_llm": mock_llm,
        "evaluate_personas": True,
    }

    result = evaluate_personas_node(state)
    assert "persona_evaluations" in result
    assert "persona_evaluation_diagnostics" in result
    assert len(result["persona_evaluations"]) == 1
    assert result["persona_evaluations"][0]["persona_id"] == "p_node"


# ------------------------------------------------------------------
# 16. Vector Store Unavailable Fallback & Progress Logging Tests
# ------------------------------------------------------------------

def test_evaluate_personas_unavailable_vector_store_graceful_fallback(capsys):
    """
    When vector storage is unavailable or not provided, evaluate_personas
    falls back cleanly to state retrieved chunks without claiming vector store grounding.
    """
    p = make_sample_persona("p_fallback", "Fallback Test User")

    def mock_llm(prompt: str) -> str:
        # Verify prompt received the fallback evidence context
        assert "RETRIEVED MARKET EVIDENCE" in prompt or "census" in prompt
        d = make_valid_evaluation_dict("p_fallback")
        d["supporting_evidence_ids"] = ["fallback_chunk_1"]
        return json.dumps(d)

    dummy_chunk = {
        "chunk_id": "fallback_chunk_1",
        "document_id": "doc_1",
        "text": "Ahmedabad census 2011 literacy observation text",
        "source": "census_2011",
    }

    evals, diag = evaluate_personas(
        idea="Smart EV fleet charging hub in Ahmedabad",
        personas=[p],
        vector_store=None,
        retrieved_chunks=[dummy_chunk],
        llm=mock_llm,
    )

    assert len(evals) == 1
    assert evals[0].persona_id == "p_fallback"
    assert "fallback_chunk_1" in evals[0].supporting_evidence_ids
    # Grounding status must reflect fallback, not successful vector search
    assert diag["vector_store_grounding_status"] == "none_provided_fallback_to_state_chunks"

    # Progress output should have been printed
    captured = capsys.readouterr()
    assert "Evaluating persona [1/1] 'p_fallback'" in captured.out
    assert "done (" in captured.out


def test_evaluate_personas_concurrency_ordering_and_speed():
    """
    Verify that max_concurrency=3 executes faster than sequential execution
    while strictly preserving the exact input order of personas in the result list.
    """
    import time
    personas = [
        make_sample_persona(f"p_{i}", f"User {i}")
        for i in range(1, 6)
    ]

    def mock_delayed_llm(prompt: str) -> str:
        time.sleep(0.08)  # simulate network/inference latency
        for p in personas:
            if p.persona_id in prompt or p.name in prompt:
                return json.dumps(make_valid_evaluation_dict(p.persona_id))
        return json.dumps(make_valid_evaluation_dict("p_1"))

    # Test concurrency = 3
    t0 = time.time()
    evals_conc, diag_conc = evaluate_personas(
        idea="Smart commute shuttle",
        personas=personas,
        llm=mock_delayed_llm,
        max_concurrency=3,
    )
    t_conc = time.time() - t0

    assert len(evals_conc) == 5
    # Order must match original persona list exactly
    assert [e.persona_id for e in evals_conc] == [p.persona_id for p in personas]
    assert diag_conc["concurrency"] == 3
    assert diag_conc["evaluated_count"] == 5
    assert diag_conc["evaluation_failures_count"] == 0

    # Test concurrency = 1 (sequential)
    t1 = time.time()
    evals_seq, diag_seq = evaluate_personas(
        idea="Smart commute shuttle",
        personas=personas,
        llm=mock_delayed_llm,
        max_concurrency=1,
    )
    t_seq = time.time() - t1

    assert [e.persona_id for e in evals_seq] == [p.persona_id for p in personas]
    # Concurrency=3 must complete faster than sequential
    assert t_conc < t_seq


def test_evaluate_personas_retrieval_caching():
    """
    Verify that multiple personas sharing identical queries reuse cached retrieval
    results without issuing duplicate queries to the retriever.
    """
    from unittest.mock import MagicMock
    from app.rag.retriever import RetrievalResult

    p1 = make_sample_persona("p_1", "User 1")
    p2 = make_sample_persona("p_2", "User 2")
    # Both personas have the exact same segment and occupation -> same query!
    p1.segment = "Common Segment"
    p1.occupation = "Analyst"
    p2.segment = "Common Segment"
    p2.occupation = "Analyst"

    mock_retriever = MagicMock()
    mock_retriever.vector_store.count.return_value = 10
    mock_chunk = RetrievedChunk(
        chunk_id="chunk_cached_01",
        document_id="doc_1",
        text="Cached evidence chunk text",
        distance=0.25,
        source="census_2011",
    )
    mock_retriever.retrieve.return_value = RetrievalResult(
        query="idea Common Segment Analyst",
        chunks=[mock_chunk],
        total_retrieved=1,
        collection_name="test",
        embedding_model="test",
        embedding_dimensions=768,
        filters_applied=None,
        diagnostics={},
    )

    def mock_llm(prompt: str) -> str:
        d = make_valid_evaluation_dict("p_1")
        d["supporting_evidence_ids"] = ["chunk_cached_01"]
        return json.dumps(d)

    evals, diag = evaluate_personas(
        idea="idea",
        personas=[p1, p2],
        retriever=mock_retriever,
        llm=mock_llm,
        max_concurrency=2,
    )

    assert len(evals) == 2
    # mock_retriever.retrieve should only be called once because of caching!
    assert mock_retriever.retrieve.call_count == 1
    assert "chunk_cached_01" in evals[0].supporting_evidence_ids
    assert "chunk_cached_01" in evals[1].supporting_evidence_ids

