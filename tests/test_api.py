"""
tests.test_api
--------------
Unit tests for IndiValidate FastAPI HTTP endpoints (/health and /api/analyze).
All expensive pipeline calls (LangGraph, Gemini, Reddit, Trends, ChromaDB) are mocked.
"""

import os

# Ensure mock key exists during test collection if not set
os.environ.setdefault("MISTRAL_API_KEY", "mock-test-key-for-api-tests")
os.environ.setdefault("GOOGLE_API_KEY", "mock-test-key-for-api-tests")
os.environ.setdefault("GEMINI_API_KEY", "mock-test-key-for-api-tests")

from unittest.mock import MagicMock, patch
import pytest
from fastapi.testclient import TestClient

from app.api import app, get_graph


@pytest.fixture
def client():
    """FastAPI TestClient fixture."""
    return TestClient(app)


# ----------------------------------------------------------------------
# 1. Health Endpoint Tests (/health)
# ----------------------------------------------------------------------

def test_health_endpoint_returns_200_and_expected_payload(client):
    """
    GET /health must return HTTP 200 and {'status': 'ok', 'service': 'IndiValidate'}.
    Crucial for JMeter load/concurrency benchmarking.
    """
    response = client.get("/health")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/json")
    data = response.json()
    assert data == {"status": "ok", "service": "IndiValidate"}


def test_health_endpoint_is_lightweight_and_never_invokes_graph(client):
    """
    GET /health must not invoke the LangGraph pipeline, LLMs, or research tools.
    """
    with patch("app.api.get_graph") as mock_get_graph:
        response = client.get("/health")
        assert response.status_code == 200
        mock_get_graph.assert_not_called()


# ----------------------------------------------------------------------
# 2. Input Validation Tests (POST /api/analyze -> HTTP 422)
# ----------------------------------------------------------------------

def test_analyze_missing_idea_field_returns_422(client):
    """POST /api/analyze without 'idea' must return HTTP 422."""
    response = client.post("/api/analyze", json={})
    assert response.status_code == 422
    assert "idea" in response.text.lower()


def test_analyze_empty_string_idea_returns_422(client):
    """POST /api/analyze with empty 'idea' string must return HTTP 422."""
    response = client.post("/api/analyze", json={"idea": ""})
    assert response.status_code == 422


def test_analyze_whitespace_only_idea_returns_422(client):
    """POST /api/analyze with whitespace-only 'idea' must return HTTP 422."""
    response = client.post("/api/analyze", json={"idea": "   \t \n  "})
    assert response.status_code == 422


def test_analyze_non_string_idea_returns_422(client):
    """POST /api/analyze with numeric/object 'idea' must return HTTP 422."""
    response = client.post("/api/analyze", json={"idea": 12345})
    assert response.status_code == 422


def test_analyze_extra_forbidden_fields_returns_422(client):
    """POST /api/analyze with unknown extra fields must return HTTP 422 (extra='forbid')."""
    payload = {
        "idea": "Electric rickshaw route optimizer",
        "unexpected_extra_field": "disallowed",
    }
    response = client.post("/api/analyze", json=payload)
    assert response.status_code == 422


def test_analyze_invalid_founder_context_returns_422(client):
    """
    POST /api/analyze with malformed founder_context (e.g. missing required problem_description)
    must return HTTP 422.
    """
    payload = {
        "idea": "Solar cold storage for peri-urban farmers",
        "founder_context": {
            "customer_category": "Farmers",
            # missing required 'problem_description'
        },
    }
    response = client.post("/api/analyze", json=payload)
    assert response.status_code == 422


# ----------------------------------------------------------------------
# 3. Successful Pipeline Invocation Tests (POST /api/analyze -> HTTP 200)
# ----------------------------------------------------------------------

def test_analyze_valid_request_without_founder_context_mocked(client):
    """
    POST /api/analyze with valid idea successfully invokes pipeline and returns report.
    """
    mock_report = {
        "report_id": "MVR-TEST001",
        "executive_summary": {
            "idea_description": "Smart laundry locker service",
            "target_customer_segments": ["College Students"],
            "core_verdict_summary": "Simulated personas show interest in convenience.",
            "key_validation_recommendation": "Interview 10 hostel students.",
        },
        "diagnostics": {"status": "success"},
    }

    mock_graph = MagicMock()
    mock_graph.invoke.return_value = {
        "idea": "Smart laundry locker service",
        "market_report": mock_report,
    }

    with patch("app.api.get_graph", return_value=mock_graph):
        payload = {"idea": "Smart laundry locker service"}
        response = client.post("/api/analyze", json=payload)

        assert response.status_code == 200
        data = response.json()
        assert data["report_id"] == "MVR-TEST001"
        assert data["executive_summary"]["idea_description"] == "Smart laundry locker service"

        # Verify state passed to graph
        mock_graph.invoke.assert_called_once()
        passed_state = mock_graph.invoke.call_args[0][0]
        assert passed_state["idea"] == "Smart laundry locker service"
        assert "founder_context" not in passed_state


def test_analyze_valid_request_with_founder_context_mocked(client):
    """
    POST /api/analyze with valid founder_context serializes it into initial_state.
    """
    mock_report = {
        "report_id": "MVR-FOUNDER01",
        "executive_summary": {
            "idea_description": "Cold storage leasing for smallholders",
            "target_customer_segments": ["Smallholder Farmers"],
            "core_verdict_summary": "High value proposition identified.",
            "key_validation_recommendation": "Run deposit smoke test.",
        },
    }

    mock_graph = MagicMock()
    mock_graph.invoke.return_value = {
        "idea": "Cold storage leasing for smallholders",
        "founder_context": {"customer_category": "Farmers in Nashik"},
        "market_report": mock_report,
    }

    with patch("app.api.get_graph", return_value=mock_graph):
        payload = {
            "idea": "Cold storage leasing for smallholders",
            "founder_context": {
                "customer_category": "Farmers in Nashik",
                "problem_description": "Perishable crops rot within 48 hours of harvest",
                "launch_geography": "Nashik",
                "geographic_scope": "local_city",
                "known_alternatives": ["Government cooperative godowns"],
                "pricing_model": "usage_based",
            },
        }
        response = client.post("/api/analyze", json=payload)

        assert response.status_code == 200
        data = response.json()
        assert data["report_id"] == "MVR-FOUNDER01"

        # Verify founder context was serialized into initial_state
        passed_state = mock_graph.invoke.call_args[0][0]
        assert passed_state["idea"] == "Cold storage leasing for smallholders"
        assert "founder_context" in passed_state
        fc = passed_state["founder_context"]
        assert fc["customer_category"] == "Farmers in Nashik"
        assert fc["launch_geography"] == "Nashik"
        assert fc["problem_description"] == "Perishable crops rot within 48 hours of harvest"


# ----------------------------------------------------------------------
# 4. Pipeline Failure & Error Handling Tests (POST /api/analyze -> HTTP 500)
# ----------------------------------------------------------------------

def test_analyze_pipeline_exception_returns_500(client):
    """
    When the graph raises an unexpected exception (e.g. LLM failure),
    the endpoint must catch it and return HTTP 500 without crashing.
    """
    mock_graph = MagicMock()
    mock_graph.invoke.side_effect = RuntimeError("External Gemini API quota exhausted")

    with patch("app.api.get_graph", return_value=mock_graph):
        payload = {"idea": "Automated drone delivery in rural hills"}
        response = client.post("/api/analyze", json=payload)

        assert response.status_code == 500
        data = response.json()
        assert "detail" in data
        assert "External Gemini API quota exhausted" in data["detail"]


def test_analyze_empty_market_report_returns_500(client):
    """
    When the graph finishes but produces an empty market_report dict,
    the endpoint must return HTTP 500 with diagnostic issues.
    """
    mock_graph = MagicMock()
    mock_graph.invoke.return_value = {
        "idea": "Failed idea run",
        "market_report": {},
        "market_report_diagnostics": {
            "status": "error",
            "issues": ["Census and Trends extraction both failed critically"],
        },
    }

    with patch("app.api.get_graph", return_value=mock_graph):
        payload = {"idea": "Failed idea run"}
        response = client.post("/api/analyze", json=payload)

        assert response.status_code == 500
        data = response.json()
        assert "detail" in data
        assert "Census and Trends extraction both failed" in data["detail"]
