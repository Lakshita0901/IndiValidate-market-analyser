"""
tests/test_mistral_integration.py
---------------------------------
Comprehensive test suite verifying the migration from Gemini to Mistral AI
for IndiValidate runtime text-generation nodes.

Verifies:
  1. Mistral configuration and client initialization (MISTRAL_MODEL, MISTRAL_API_KEY).
  2. Missing credentials and provider failure handling.
  3. Mistral error classification and diagnostic isolation (401, 402, 404, 429, timeout).
  4. Persona generation with Mistral response parsing and validation.
  5. Persona evaluation with Mistral structured output.
  6. LLM-native fallback answers using configured Mistral model.
  7. Strict confirmation that runtime text generation nodes no longer depend on Gemini.
  8. Strict confirmation that the embedding provider remains independent and unmodified.
"""

import json
import os
from unittest.mock import MagicMock, patch

import pytest
from langchain_core.messages import AIMessage
from langchain_mistralai import ChatMistralAI

from app.llm import (
    DEFAULT_MISTRAL_MODEL,
    classify_mistral_error,
    get_llm,
    get_mistral_api_key,
    get_mistral_model_name,
    has_mistral_api_key,
    is_terminal_error,
)
from app.nodes.idea_analysis import analyze_idea
from app.nodes.keywords import extract_keywords
from app.nodes.location import identify_location
from app.nodes.persona_evaluation import evaluate_personas
from app.nodes.persona_generation import generate_personas
from app.nodes.target import identify_target
from app.rag.embeddings import GoogleEmbeddingProvider
from app.schemas.persona import BehavioralHypotheses, CustomerType, Persona, PersonaProvenance
from app.schemas.persona_evaluation import PersonaEvaluation
from app.services.fallback_answer import answer_research_questions, get_configured_llm


# ----------------------------------------------------------------------
# 1. Mistral Configuration and Client Initialization
# ----------------------------------------------------------------------

def test_mistral_config_defaults_and_env_override(monkeypatch):
    """Verify default model is mistral-small-latest and respects MISTRAL_MODEL override."""
    monkeypatch.delenv("MISTRAL_MODEL", raising=False)
    assert get_mistral_model_name() == DEFAULT_MISTRAL_MODEL

    monkeypatch.setenv("MISTRAL_MODEL", "mistral-large-latest")
    assert get_mistral_model_name() == "mistral-large-latest"


def test_mistral_client_factory_initialization(monkeypatch):
    """Verify get_llm instantiates ChatMistralAI with expected parameters."""
    monkeypatch.setenv("MISTRAL_API_KEY", "mock-test-key-12345")
    monkeypatch.setenv("MISTRAL_MODEL", "mistral-small-latest")

    llm = get_llm(temperature=0.4, timeout=30.0, max_retries=2)
    assert isinstance(llm, ChatMistralAI)
    assert llm.model == "mistral-small-latest"
    assert llm.temperature == 0.4
    assert llm.timeout == 30.0
    assert llm.max_retries == 2


# ----------------------------------------------------------------------
# 2. Missing Credentials and Error Classification
# ----------------------------------------------------------------------

def test_missing_credentials_handling(monkeypatch):
    """When MISTRAL_API_KEY is not set, has_mistral_api_key returns False and diagnostics isolate it."""
    monkeypatch.delenv("MISTRAL_API_KEY", raising=False)

    assert has_mistral_api_key() is False
    assert get_mistral_api_key() is None

    # Error classification for missing key
    diag = classify_mistral_error(RuntimeError("Missing key test"))
    assert diag["classification"] == "missing_api_key"
    assert diag["is_terminal"] is True
    assert "MISTRAL_API_KEY" in diag["user_message"]


def test_mistral_error_classification():
    """Verify classification of 401, 402, 404, 429, and timeouts without leaking credentials."""
    # 401 unauthorized
    diag_401 = classify_mistral_error(Exception("Error response 401: Unauthorized Invalid API Key"))
    assert diag_401["classification"] == "invalid_credentials"
    assert diag_401["is_terminal"] is True

    # 402 insufficient credits
    diag_402 = classify_mistral_error(Exception("402 Payment Required: Insufficient account credit"))
    assert diag_402["classification"] == "insufficient_credits"
    assert diag_402["is_terminal"] is True

    # 404 model not found
    diag_404 = classify_mistral_error(Exception("404 Not Found: model_not_found"))
    assert diag_404["classification"] == "model_not_found"
    assert diag_404["is_terminal"] is True

    # 429 rate limit (transient)
    diag_429 = classify_mistral_error(Exception("429 Too Many Requests: Rate limit exceeded"))
    assert diag_429["classification"] == "rate_limit"
    assert diag_429["is_terminal"] is False
    assert is_terminal_error(Exception("429 Rate limit")) is False

    # Timeout (transient)
    diag_timeout = classify_mistral_error(TimeoutError("Request timed out after 45 seconds"))
    assert diag_timeout["classification"] == "timeout"
    assert diag_timeout["is_terminal"] is False


def test_error_sanitization_removes_secrets():
    """Verify error messages with Bearer tokens or API keys have secrets redacted."""
    raw = "Failed with Bearer secret_mistral_key_99887766 and api-key: abcdef12345678"
    diag = classify_mistral_error(Exception(raw))
    assert "secret_mistral_key" not in diag["raw_message"]
    assert "[REDACTED]" in diag["raw_message"]


# ----------------------------------------------------------------------
# 3. Persona Generation with Mistral
# ----------------------------------------------------------------------

def test_persona_generation_with_mistral_mock():
    """Verify generate_personas parses structured JSON returned by Mistral."""
    mock_payload = {
        "personas": [
            {
                "persona_id": "p_001",
                "name": "Rajesh Sharma - Fleet Manager",
                "segment": "SMB Logistics Operator",
                "customer_type": "b2b",
                "geography": {"state": "Gujarat", "district": "Ahmedabad"},
                "age_band": "36-45",
                "occupation": "Fleet Manager",
                "education_level": "Bachelor of Commerce",
                "income_band": "INR 45,000/month",
                "household_context": "Nuclear family of 4",
                "household_size": 4,
                "b2b_attributes": {
                    "job_role": "Fleet Operations Lead",
                    "organization_size": "20-50 vehicles",
                    "purchasing_authority": "Recommender",
                    "procurement_constraints": ["Monthly recurring budget limit"],
                },
                "behavioral_hypotheses": {
                    "digital_adoption": 7,
                    "price_sensitivity": 8,
                    "risk_tolerance": 4,
                    "convenience_preference": 9,
                    "brand_trust_importance": 7,
                },
                "goals_and_needs": ["Reduce charging turnaround time", "Predictable operating expenses"],
                "pain_points": ["High spare part procurement delay"],
                "purchasing_constraints": ["High upfront charger installation deposits"],
                "usage_context": "Manages 12 light commercial electric vehicles in Ahmedabad.",
                "provenance": {
                    "supporting_evidence_ids": ["doc_cen_01"],
                    "observed_market_statistics": {"district_workers": 120000},
                    "inferred_attributes": {},
                    "explicit_assumptions": ["Assumed 5 years fleet operating history"],
                    "unknown_or_unavailable_attributes": [],
                    "is_synthetic": True,
                    "is_statistically_representative": False,
                },
            }
        ]
    }

    mock_llm = MagicMock()
    mock_llm.invoke.return_value = AIMessage(content=json.dumps(mock_payload))

    personas, diag = generate_personas(
        idea="Smart EV fleet depot charging in Ahmedabad",
        target_segment="Logistics fleets",
        location="Ahmedabad, Gujarat",
        count=1,
        llm=mock_llm,
    )

    assert len(personas) == 1
    assert personas[0].persona_id == "p_001"
    assert "Rajesh Sharma" in personas[0].name
    assert personas[0].occupation == "Fleet Manager"
    assert diag["generated_count"] == 1


# ----------------------------------------------------------------------
# 4. Persona Evaluation with Mistral
# ----------------------------------------------------------------------

def test_persona_evaluation_with_mistral_mock():
    """Verify evaluate_personas parses structured evaluation JSON returned by Mistral."""
    sample_persona = Persona(
        persona_id="p_test_01",
        name="Sunita Patel - Daily Commuter",
        segment="Commuter",
        customer_type=CustomerType.CONSUMER,
        geography={"state": "Maharashtra", "district": "Pune"},
        age_band="26-35",
        occupation="Software QA Engineer",
        income_band="INR 60,000/month",
        behavioral_hypotheses=BehavioralHypotheses(digital_adoption=8, price_sensitivity=6),
        goals_and_needs=["Save commute time"],
        purchasing_constraints=["Schedule reliability"],
        usage_context="Daily commuter using metro and auto-rickshaws.",
        provenance=PersonaProvenance(),
    )

    eval_payload = {
        "persona_id": "p_test_01",
        "interest_score": 7,
        "simulated_purchase_intent": 6,
        "perceived_value_score": 7,
        "affordability_score": 8,
        "adoption_barrier_score": 5,
        "positive_aspects": ["Direct routing addresses key commute delays", "Guaranteed seat reservation"],
        "negative_aspects": ["Fixed departure schedule limits flexibility"],
        "needs_addressed": ["Save commute time", "Comfortable travel"],
        "needs_unmet": ["Late-night return trips"],
        "pricing_considerations": "INR 80/trip fits monthly transportation budget.",
        "price_is_conditional": True,
        "valued_features": ["Live GPS tracking", "Guaranteed seat reservation"],
        "unnecessary_features": ["In-ride entertainment"],
        "reasons_for_assessment": "Commute delays and high digital comfort make this attractive despite fixed schedule.",
        "supporting_persona_attributes": ["digital_adoption", "price_sensitivity"],
        "supporting_evidence_ids": [],
        "unsupported_assumptions": ["Assumed routes serve Pune IT parks"],
        "evidence_gaps": ["Peak rush hour service frequency"],
        "is_simulation": True,
        "is_conversion_probability": False,
    }

    mock_llm = MagicMock()
    mock_llm.invoke.return_value = AIMessage(content=json.dumps(eval_payload))

    evaluations, diag = evaluate_personas(
        idea="Electric shuttle with app reservation",
        personas=[sample_persona],
        llm=mock_llm,
        max_concurrency=1,
    )

    assert len(evaluations) == 1
    ev = evaluations[0]
    assert ev.persona_id == "p_test_01"
    assert ev.interest_score == 7
    assert ev.simulated_purchase_intent == 6
    assert "Live GPS tracking" in ev.valued_features
    assert diag["evaluated_count"] == 1


# ----------------------------------------------------------------------
# 5. LLM-Native Fallback Answers with Mistral
# ----------------------------------------------------------------------

def test_fallback_answers_with_mistral_mock(monkeypatch):
    """Verify fallback_answer service uses Mistral and returns model_knowledge answers."""
    monkeypatch.setenv("MISTRAL_API_KEY", "mock-mistral-key")

    mock_answer_json = {
        "question": "What is the core customer problem, and what indicates real market demand or urgency?",
        "answer": "Urban commuters face severe last-mile transit gaps between rail stations and business districts.",
        "basis": "model_knowledge",
        "supporting_sources": [],
        "assumptions": ["Commuter willingness to pay is supported by existing cab fares."],
        "confidence": "Medium - Model-derived qualitative synthesis.",
        "limitations": ["Requires local survey validation."],
        "requires_external_validation": True,
    }

    mock_llm = MagicMock()
    mock_llm.invoke.return_value = AIMessage(content=json.dumps(mock_answer_json))

    with patch("app.services.fallback_answer.get_configured_llm", return_value=mock_llm):
        answers, diag = answer_research_questions(
            idea="Smart shuttle connecting IT parks to metro",
            questions=["What is the core customer problem, and what indicates real market demand or urgency?"],
            retrieved_chunks=[],
            llm=mock_llm,
        )

        assert len(answers) == 1
        assert answers[0].basis.value == "model_knowledge"
        assert answers[0].requires_external_validation is True


# ----------------------------------------------------------------------
# 6. Confirmation that Runtime Text Generation No Longer Depends on Gemini
# ----------------------------------------------------------------------

def test_runtime_text_generation_does_not_require_gemini(monkeypatch):
    """
    Ensure all runtime text-generation nodes (idea_analysis, location, keywords,
    target, persona_generation, persona_evaluation, fallback_answer) operate
    without GEMINI_API_KEY or GOOGLE_API_KEY in the environment.
    """
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.setenv("MISTRAL_API_KEY", "mock-mistral-key")

    mock_llm = MagicMock()

    # 1. idea_analysis
    mock_llm.invoke.return_value = AIMessage(content="Transportation & Mobility")
    res_idea = analyze_idea({"idea": "Metro shuttle service", "llm": mock_llm})
    assert res_idea["category"] == "Transportation & Mobility"

    # 2. location
    mock_llm.invoke.return_value = AIMessage(content="Ahmedabad")
    res_loc = identify_location({"idea": "Metro shuttle in Ahmedabad", "llm": mock_llm})
    assert res_loc["location"] == "Ahmedabad"

    # 3. keywords
    mock_llm.invoke.return_value = AIMessage(content="shuttle, metro, transit, commute")
    res_kw = extract_keywords({"idea": "Metro shuttle in Ahmedabad", "llm": mock_llm})
    assert "shuttle" in res_kw["keywords"]

    # 4. target
    mock_llm.invoke.return_value = AIMessage(content="Daily office commuters")
    res_target = identify_target({"idea": "Metro shuttle in Ahmedabad", "llm": mock_llm})
    assert res_target["target_segment"] == "Daily office commuters"

    # 5. fallback_answer get_configured_llm works with Mistral
    configured = get_configured_llm()
    assert isinstance(configured, ChatMistralAI)


# ----------------------------------------------------------------------
# 7. Confirmation that Embedding Provider Remains Independent
# ----------------------------------------------------------------------

def test_embedding_provider_remains_independent(monkeypatch):
    """
    Verify GoogleEmbeddingProvider is independent from Mistral text-generation,
    retains its models/gemini-embedding-001 default, and requires Google credentials.
    """
    # Without Google credentials, provider initialization raises ValueError
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.setenv("MISTRAL_API_KEY", "mock-mistral-key")

    with pytest.raises(ValueError, match="Google API key not found in environment"):
        GoogleEmbeddingProvider()

    # With Google credentials, it initializes models/gemini-embedding-001 (3072 dims)
    monkeypatch.setenv("GEMINI_API_KEY", "mock-gemini-key")
    provider = GoogleEmbeddingProvider()
    assert provider.model_name == "models/gemini-embedding-001"
    assert provider.dimensions == 3072
