"""
tests/test_rate_limit.py
-------------------------
Mocked unit and integration tests for Mistral rate-limit handling:
1. Rate-limit detection (HTTP 429, code 1300, 'Rate limit exceeded').
2. Retry-after extraction from headers, JSON responses, and error strings.
3. Bounded exponential backoff with jitter and retry limits (never indefinite).
4. RateLimitCoordinator inter-request pacing and thread cooldown.
5. Intermediate stage caching and partial persona evaluation reuse without pipeline restart.
6. User-friendly frontend/API error formatting and secret/traceback redaction.
"""

import time
from typing import Any, Dict
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.api import (
    _compute_cache_key,
    _intermediate_state_cache,
    app,
)
from app.llm import (
    MistralRateLimitException,
    calculate_backoff,
    classify_mistral_error,
    is_rate_limit_error,
    is_terminal_error,
)
from app.nodes.idea_analysis import analyze_idea
from app.nodes.keywords import extract_keywords
from app.nodes.location import identify_location
from app.nodes.persona_evaluation import (
    RateLimitCoordinator,
    evaluate_personas,
    evaluate_personas_node,
)
from app.nodes.persona_generation import generate_personas_node
from app.nodes.target import identify_target
from app.schemas.persona import BehavioralHypotheses, CustomerType, Persona


# =====================================================================
# 1. Rate-Limit Detection & Diagnostic Details Tests
# =====================================================================

def test_classify_live_mistral_429_code_1300():
    """Verify live Mistral error shape: HTTP 429, code 1300, 'Rate limit exceeded'."""
    raw_error_text = (
        "SDKError: status_code: 429, body: {'message': 'Rate limit exceeded', 'code': 1300}"
    )
    exc = Exception(raw_error_text)

    diag = classify_mistral_error(exc)

    assert diag["classification"] == "rate_limit"
    assert diag["status_code"] == 429
    assert diag["error_code"] == 1300
    assert diag["is_terminal"] is False
    assert is_rate_limit_error(exc) is True
    assert is_terminal_error(exc) is False
    assert (
        diag["user_message"]
        == "Mistral API rate limit reached. Check your organization’s API limits and usage, then retry after the indicated wait."
    )


def test_classify_rate_limit_redacts_api_keys_and_tokens():
    """Verify raw secrets and Bearer tokens are redacted in raw_message."""
    leak_err = (
        "Rate limit exceeded (code 1300) for Bearer secret_token_12345678 "
        "with api_key='sk-live-9876543210' mistral_api_key='mis-9988776655'"
    )
    exc = Exception(leak_err)
    diag = classify_mistral_error(exc)

    assert "secret_token_12345678" not in diag["raw_message"]
    assert "sk-live-9876543210" not in diag["raw_message"]
    assert "mis-9988776655" not in diag["raw_message"]
    assert "[REDACTED]" in diag["raw_message"]


# =====================================================================
# 2. Retry-After Extraction Tests
# =====================================================================

def test_extract_retry_after_from_response_headers():
    """Verify retry-after is extracted from response headers."""
    mock_resp = MagicMock()
    mock_resp.status_code = 429
    mock_resp.headers = {"Retry-After": "8"}

    exc = Exception("HTTP 429 Rate limit exceeded")
    exc.response = mock_resp

    diag = classify_mistral_error(exc)
    assert diag["classification"] == "rate_limit"
    assert diag["retry_after"] == 8.0


def test_extract_retry_after_from_ms_headers():
    """Verify retry-after-ms is extracted and converted to seconds."""
    mock_resp = MagicMock()
    mock_resp.status_code = 429
    mock_resp.headers = {"retry-after-ms": "4500"}

    exc = Exception("HTTP 429 Rate limit exceeded")
    exc.response = mock_resp

    diag = classify_mistral_error(exc)
    assert diag["retry_after"] == 4.5


def test_extract_retry_after_from_error_string_regex():
    """Verify retry-after is parsed via regex when headers are absent."""
    exc1 = Exception("Rate limit exceeded. Please wait 15 seconds before trying again.")
    diag1 = classify_mistral_error(exc1)
    assert diag1["retry_after"] == 15.0

    exc2 = Exception("HTTP 429: Rate limit exceeded (retry_after=6.5)")
    diag2 = classify_mistral_error(exc2)
    assert diag2["retry_after"] == 6.5


# =====================================================================
# 3. Bounded Exponential Backoff with Jitter Tests
# =====================================================================

def test_calculate_backoff_respects_retry_after():
    """Verify calculate_backoff uses server's retry-after when present."""
    wait = calculate_backoff(attempt=1, retry_after=5.0, max_backoff=30.0)
    # Server retry-after 5.0 + small jitter [0.1, 0.4]
    assert 5.1 <= wait <= 5.5

    # Capped at max_backoff if server value is excessive
    capped_wait = calculate_backoff(attempt=1, retry_after=120.0, max_backoff=30.0)
    assert capped_wait == 30.0


def test_calculate_backoff_exponential_growth_and_jitter():
    """Verify exponential progression without retry_after."""
    w1 = calculate_backoff(attempt=1, base_delay=2.0, max_backoff=30.0)
    w2 = calculate_backoff(attempt=2, base_delay=2.0, max_backoff=30.0)
    w3 = calculate_backoff(attempt=3, base_delay=2.0, max_backoff=30.0)

    # attempt 1: 2 * 2^0 + jitter (0.5 to 1.5) = 2.5 to 3.5
    assert 2.4 <= w1 <= 3.6
    # attempt 2: 2 * 2^1 + jitter = 4.5 to 5.5
    assert 4.4 <= w2 <= 5.6
    # attempt 3: 2 * 2^2 + jitter = 8.5 to 9.5
    assert 8.4 <= w3 <= 9.6

    # Verify capped at max_backoff
    w_large = calculate_backoff(attempt=10, base_delay=2.0, max_backoff=25.0)
    assert w_large <= 25.0


def test_coordinator_inter_request_spacing_and_cooldown():
    """Verify RateLimitCoordinator paces requests and establishes cooldown."""
    coord = RateLimitCoordinator(min_spacing_seconds=0.05)

    t0 = time.time()
    coord.wait_for_slot()
    coord.wait_for_slot()
    t1 = time.time()
    assert (t1 - t0) >= 0.04  # spaced by min_spacing

    # Trigger rate limit cooldown of 0.1s
    cooldown = coord.trigger_cooldown(retry_after=0.1, attempt=1)
    assert cooldown >= 0.1

    t2 = time.time()
    coord.wait_for_slot()
    t3 = time.time()
    assert (t3 - t2) >= 0.09


# =====================================================================
# 4. Persona Evaluation Partial Stage Reuse Tests
# =====================================================================

def _make_dummy_persona(p_id: str) -> Persona:
    return Persona(
        persona_id=p_id,
        name=f"User {p_id}",
        segment="Commuter",
        customer_type=CustomerType.CONSUMER,
        behavioral_hypotheses=BehavioralHypotheses(
            price_sensitivity=5,
            convenience_preference=6,
            brand_trust_importance=5,
            risk_tolerance=5,
            digital_adoption=6,
        ),
    )


def test_evaluate_personas_reuses_cached_evaluations_without_llm():
    """Verify that personas already present in cached_evaluations are NOT re-invoked."""
    p1 = _make_dummy_persona("p1")
    p2 = _make_dummy_persona("p2")

    cached_eval_p1 = {
        "persona_id": "p1",
        "interest_score": 8,
        "simulated_purchase_intent": 7,
        "perceived_value_score": 8,
        "affordability_score": 6,
        "adoption_barrier_score": 3,
        "price_is_conditional": True,
        "reasons_for_assessment": "Cached assessment",
    }

    mock_llm = MagicMock()
    # Mock LLM returns evaluation for p2
    mock_llm.invoke.return_value = MagicMock(
        content='''{
            "persona_id": "p2",
            "interest_score": 6,
            "simulated_purchase_intent": 5,
            "perceived_value_score": 6,
            "affordability_score": 7,
            "adoption_barrier_score": 4,
            "price_is_conditional": true,
            "reasons_for_assessment": "Evaluated p2"
        }'''
    )

    evals, diag = evaluate_personas(
        idea="Smart EV shuttle service in Pune",
        personas=[p1, p2],
        llm=mock_llm,
        cached_evaluations=[cached_eval_p1],
        max_concurrency=1,
    )

    # p1 came from cache, p2 called LLM -> LLM invoked only ONCE, not twice!
    assert mock_llm.invoke.call_count == 1
    assert len(evals) == 2
    assert diag["reused_count"] == 1
    assert evals[0].persona_id == "p1"
    assert evals[0].interest_score == 8
    assert evals[1].persona_id == "p2"
    assert evals[1].interest_score == 6


def test_evaluate_personas_node_full_reuse():
    """Verify evaluate_personas_node immediately reuses complete persona_evaluations."""
    state = {
        "idea": "Smart EV shuttle",
        "personas": [_make_dummy_persona("p1").model_dump()],
        "persona_evaluations": [{
            "persona_id": "p1",
            "interest_score": 9,
            "simulated_purchase_intent": 8,
            "perceived_value_score": 9,
            "affordability_score": 7,
            "adoption_barrier_score": 2,
            "price_is_conditional": True,
            "reasons_for_assessment": "Reused",
        }],
    }

    output = evaluate_personas_node(state)
    assert len(output["persona_evaluations"]) == 1
    assert output["persona_evaluations"][0]["persona_id"] == "p1"
    assert output["persona_evaluation_diagnostics"].get("status") == "reused_from_cache"


# =====================================================================
# 5. Pipeline Node Stage Reuse Tests
# =====================================================================

def test_pipeline_nodes_stage_reuse():
    """Verify that completed outputs in state prevent redundant LLM invocations."""
    mock_llm = MagicMock()

    # 1. analyze_idea
    state_with_cat = {"idea": "Test idea", "category": "Transportation", "idea_llm": mock_llm}
    res_cat = analyze_idea(state_with_cat)
    assert res_cat["category"] == "Transportation"
    assert mock_llm.invoke.call_count == 0

    # 2. identify_location
    state_with_loc = {
        "idea": "Test idea",
        "location": "Pune",
        "geography_diagnostics": {"inferred_location": "Pune", "has_discrepancy": False},
        "location_llm": mock_llm,
    }
    res_loc = identify_location(state_with_loc)
    assert res_loc["location"] == "Pune"
    assert mock_llm.invoke.call_count == 0

    # 3. extract_keywords
    state_with_kw = {"idea": "Test idea", "keywords": ["electric", "shuttle"], "keywords_llm": mock_llm}
    res_kw = extract_keywords(state_with_kw)
    assert res_kw["keywords"] == ["electric", "shuttle"]
    assert mock_llm.invoke.call_count == 0

    # 4. identify_target
    state_with_tgt = {"idea": "Test idea", "target_segment": "Commuters", "target_llm": mock_llm}
    res_tgt = identify_target(state_with_tgt)
    assert res_tgt["target_segment"] == "Commuters"
    assert mock_llm.invoke.call_count == 0

    # 5. generate_personas_node
    cached_personas = [_make_dummy_persona("p1").model_dump()]
    state_with_personas = {
        "idea": "Test idea",
        "persona_count": 1,
        "personas": cached_personas,
        "persona_llm": mock_llm,
    }
    res_personas = generate_personas_node(state_with_personas)
    assert len(res_personas["personas"]) == 1
    assert mock_llm.invoke.call_count == 0


# =====================================================================
# 6. API Error Response & Rate-Limit Friendly Message Tests
# =====================================================================

def test_api_429_returns_friendly_message_and_retry_after():
    """Verify /api/analyze returns HTTP 429 with exact required message and Retry-After header."""
    client = TestClient(app)

    # Clear cache before test
    _intermediate_state_cache.clear()

    # Simulate graph raising MistralRateLimitException with code 1300 and retry_after 9
    with patch("app.api.get_graph") as mock_get_graph:
        mock_graph = MagicMock()
        mock_graph.stream.side_effect = MistralRateLimitException(
            message="Rate limit exceeded",
            retry_after=9.0,
            status_code=429,
            error_code=1300,
        )
        mock_get_graph.return_value = mock_graph

        resp = client.post("/api/analyze", json={"idea": "Smart EV shuttle service"})

        assert resp.status_code == 429
        data = resp.json()
        assert (
            data["detail"]
            == "Mistral API rate limit reached. Check your organization’s API limits and usage, then retry after the indicated wait."
        )
        assert resp.headers.get("retry-after") == "9"


def test_api_retains_intermediate_cache_for_retry():
    """Verify pipeline state is preserved in intermediate cache when rate limit occurs."""
    client = TestClient(app)
    _intermediate_state_cache.clear()

    idea_str = "Smart EV shuttle service in Pune"
    cache_key = _compute_cache_key(idea_str, None, 10)

    # Simulate a stream that completes analyze_idea and keywords, then hits 429
    def mock_stream_steps(initial_state):
        yield {"analyze_idea": {"category": "Transportation"}}
        yield {"extract_keywords": {"keywords": ["shuttle", "metro"]}}
        raise MistralRateLimitException(
            message="Rate limit exceeded",
            retry_after=5.0,
            partial_evaluations=[{"persona_id": "p1", "interest_score": 8}],
        )

    with patch("app.api.get_graph") as mock_get_graph:
        mock_graph = MagicMock()
        mock_graph.stream.side_effect = mock_stream_steps
        mock_get_graph.return_value = mock_graph

        resp = client.post("/api/analyze", json={"idea": idea_str})
        assert resp.status_code == 429

        # Verify intermediate cache preserved completed stages
        assert cache_key in _intermediate_state_cache
        cached = _intermediate_state_cache[cache_key]
        assert cached.get("category") == "Transportation"
        assert cached.get("keywords") == ["shuttle", "metro"]
        assert len(cached.get("persona_evaluations", [])) == 1
        assert cached["persona_evaluations"][0]["persona_id"] == "p1"
