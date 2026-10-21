"""
tests/test_error_isolation.py
------------------------------
Tests that verify a failure in any single research source does NOT
prevent the other sources from returning evidence.

Approach: use monkeypatching / controlled exceptions to simulate failures.
No real datasets are altered. No mock data is injected into the application.

Note on patching Census/PLFS: research.py calls these via
  _fn = getattr(run_census_search, "func", run_census_search)
So we must patch using plain Python functions (not MagicMock), otherwise
getattr(mock, 'func', ...) returns a MagicMock sub-attribute and the
result of calling it is another MagicMock, not a dict with status='error'.
"""

import pytest
from unittest.mock import patch


# ──────────────────────────────────────────────────────────────────
# Minimal stubs for sources that should SUCCEED in each test
# ──────────────────────────────────────────────────────────────────

def _reddit_success():
    return [
        {
            "source": "reddit",
            "source_type": "historical_dataset",
            "title": "Organic delivery discussion",
            "text": "Great idea for families.",
            "subreddit": "india",
            "score": 50,
        }
    ]


def _trends_success():
    return [
        {
            "source": "google_trends",
            "keyword": "organic delivery",
            "geo": "IN-GJ",
            "relative_interest": [30] * 12,
            "trend_direction": "stable",
            "latest_value": 30,
            "average_value": 30,
            "peak_value": 30,
            "cache_hit": False,
        }
    ]


def _census_success():
    return {
        "status": "success",
        "source": "Census 2011",
        "geography": {"state": "Gujarat", "district": "Ahmedabad"},
        "pca": {
            "population": {"total": 7_000_000},
            "households": 1_500_000,
            "literacy": {"crude_literacy_rate_percent": 75.0},
        },
        "education": {
            "tru": "Total",
            "summary": {
                "literates": {"persons": 5_000_000},
                "levels": {"graduate_and_above": {"persons": 800_000}},
            },
        },
        "higher_education": {
            "summary": {
                "disciplines": {
                    "engineering_and_technology": {"persons": 80_000},
                    "medicine": {"persons": 25_000},
                    "teaching": {"persons": 22_000},
                }
            }
        },
    }


def _plfs_success():
    return {
        "status": "success",
        "source": "PLFS 2025",
        "geography": {
            "state": "Gujarat",
            "district": "Ahmedabad",
            "st": 24, "dc": 7,
        },
        "labour_indicators": {
            "usual_status_ps_plus_ss": {
                "lfpr_percent": 55.64,
                "wpr_percent": 55.03,
                "unemployment_rate_percent": 1.10,
            }
        },
        "earnings": {
            "regular_salaried": {"avg_monthly_salary_inr": 22638.0},
            "self_employed": {"avg_monthly_earnings_inr": 26330.0},
        },
        "education": {"graduate_and_above_percent": 23.2},
    }


# ─────────────────────────────────────────────────────────────────
# Plain function stubs (NOT MagicMock) so getattr(.., 'func', ..)
# returns the stub itself, not a sub-Mock attribute.
# ─────────────────────────────────────────────────────────────────

def _census_stub(**kwargs):
    return _census_success()


def _plfs_stub(**kwargs):
    return _plfs_success()


def _census_error_stub(**kwargs):
    raise Exception("Simulated Census crash")


def _plfs_error_stub(**kwargs):
    raise Exception("Simulated PLFS crash")


# ──────────────────────────────────────────────────────────────────
# Shared state dict injected into run_research
# ──────────────────────────────────────────────────────────────────

TEST_STATE = {
    "idea": "Online organic vegetable delivery for families in Ahmedabad",
    "keywords": ["organic", "delivery", "vegetable"],
    "target_segment": "Families",
    "location": "Ahmedabad",
    "district": "Ahmedabad",
    "research_type": "location_based",
}


# ──────────────────────────────────────────────────────────────────
# A. Trends fails — Reddit, Census, PLFS succeed
# ──────────────────────────────────────────────────────────────────

def test_a_trends_fails_others_succeed():
    """A Trends 429 must not discard successful Reddit, Census, or PLFS evidence."""
    with patch("app.nodes.research.run_reddit_search", return_value=_reddit_success()), \
         patch("app.nodes.research.run_trends_search",
               side_effect=Exception("Simulated Trends 429")), \
         patch("app.nodes.research.run_census_search", new=_census_stub), \
         patch("app.nodes.research.run_plfs_search", new=_plfs_stub):

        from app.nodes.research import run_research
        result = run_research(TEST_STATE)

    # Reddit succeeded
    assert len(result["reddit_evidence"]) >= 1, "Reddit evidence missing"
    # Trends failed — error recorded, not propagated
    assert len(result["trends_evidence"]) == 0
    trends_errors = [e for e in result["research_errors"]
                     if e.get("source") == "Google Trends"]
    assert len(trends_errors) >= 1, "Trends error not recorded"
    # Census succeeded
    assert len(result["census_evidence"]) >= 1, "Census evidence missing"
    # PLFS succeeded
    assert len(result["plfs_evidence"]) >= 1, "PLFS evidence missing"
    # Pipeline always completes
    assert result["research_complete"] is True


# ──────────────────────────────────────────────────────────────────
# B. Reddit fails — Trends, Census, PLFS succeed
# ──────────────────────────────────────────────────────────────────

def test_b_reddit_fails_others_succeed():
    """A Reddit dataset error must not affect Trends, Census, or PLFS."""
    with patch("app.nodes.research.run_reddit_search",
               side_effect=Exception("Simulated Reddit load failure")), \
         patch("app.nodes.research.run_trends_search",
               return_value=_trends_success()), \
         patch("app.nodes.research.run_census_search", new=_census_stub), \
         patch("app.nodes.research.run_plfs_search", new=_plfs_stub):

        from app.nodes.research import run_research
        result = run_research(TEST_STATE)

    assert len(result["reddit_evidence"]) == 0
    reddit_errors = [e for e in result["research_errors"]
                     if e.get("source") == "Reddit (Kaggle dataset)"]
    assert len(reddit_errors) >= 1

    assert len(result["trends_evidence"]) >= 1
    assert len(result["census_evidence"]) >= 1
    assert len(result["plfs_evidence"]) >= 1
    assert result["research_complete"] is True


# ──────────────────────────────────────────────────────────────────
# C. Census fails — Reddit, Trends, PLFS succeed
# ──────────────────────────────────────────────────────────────────

def test_c_census_fails_others_succeed():
    """A Census error must not affect Reddit, Trends, or PLFS."""
    with patch("app.nodes.research.run_reddit_search",
               return_value=_reddit_success()), \
         patch("app.nodes.research.run_trends_search",
               return_value=_trends_success()), \
         patch("app.nodes.research.run_census_search", new=_census_error_stub), \
         patch("app.nodes.research.run_plfs_search", new=_plfs_stub):

        from app.nodes.research import run_research
        result = run_research(TEST_STATE)

    assert len(result["census_evidence"]) == 0
    census_errors = [e for e in result["research_errors"]
                     if e.get("source") == "Census 2011"]
    assert len(census_errors) >= 1

    assert len(result["reddit_evidence"]) >= 1
    assert len(result["trends_evidence"]) >= 1
    assert len(result["plfs_evidence"]) >= 1
    assert result["research_complete"] is True


# ──────────────────────────────────────────────────────────────────
# D. PLFS fails — Reddit, Trends, Census succeed
# ──────────────────────────────────────────────────────────────────

def test_d_plfs_fails_others_succeed():
    """A PLFS error must not affect Reddit, Trends, or Census."""
    with patch("app.nodes.research.run_reddit_search",
               return_value=_reddit_success()), \
         patch("app.nodes.research.run_trends_search",
               return_value=_trends_success()), \
         patch("app.nodes.research.run_census_search", new=_census_stub), \
         patch("app.nodes.research.run_plfs_search", new=_plfs_error_stub):

        from app.nodes.research import run_research
        result = run_research(TEST_STATE)

    assert len(result["plfs_evidence"]) == 0
    plfs_errors = [e for e in result["research_errors"]
                   if e.get("source") == "PLFS 2025"]
    assert len(plfs_errors) >= 1

    assert len(result["reddit_evidence"]) >= 1
    assert len(result["trends_evidence"]) >= 1
    assert len(result["census_evidence"]) >= 1
    assert result["research_complete"] is True


# ──────────────────────────────────────────────────────────────────
# E. All sources fail — pipeline still completes
# ──────────────────────────────────────────────────────────────────

def test_e_all_sources_fail_pipeline_completes():
    """Even when every source fails, research_complete must be True."""
    with patch("app.nodes.research.run_reddit_search",
               side_effect=Exception("Reddit crash")), \
         patch("app.nodes.research.run_trends_search",
               side_effect=Exception("Trends crash")), \
         patch("app.nodes.research.run_census_search", new=_census_error_stub), \
         patch("app.nodes.research.run_plfs_search", new=_plfs_error_stub):

        from app.nodes.research import run_research
        result = run_research(TEST_STATE)

    assert result["research_complete"] is True
    assert len(result["research_errors"]) == 4
    assert len(result["reddit_evidence"]) == 0
    assert len(result["trends_evidence"]) == 0
    assert len(result["census_evidence"]) == 0
    assert len(result["plfs_evidence"]) == 0


# ──────────────────────────────────────────────────────────────────
# F. No duplicate error entries
# ──────────────────────────────────────────────────────────────────

def test_f_no_duplicate_errors():
    """Each source failure produces exactly one error entry per run."""
    with patch("app.nodes.research.run_reddit_search",
               side_effect=Exception("Reddit crash")), \
         patch("app.nodes.research.run_trends_search",
               side_effect=Exception("Trends crash")), \
         patch("app.nodes.research.run_census_search", new=_census_stub), \
         patch("app.nodes.research.run_plfs_search", new=_plfs_stub):

        from app.nodes.research import run_research
        result = run_research(TEST_STATE)

    sources = [e.get("source") for e in result["research_errors"]]
    assert sources.count("Reddit (Kaggle dataset)") == 1
    assert sources.count("Google Trends") == 1


# ──────────────────────────────────────────────────────────────────
# G. Trends structured error (rate_limited) is preserved
# ──────────────────────────────────────────────────────────────────

def test_g_trends_rate_limit_error_preserved():
    """
    When run_trends_search returns structured error records (not exceptions),
    they are stored in research_errors and successful ones in trends_evidence.
    """
    mixed_trends = [
        # First keyword succeeded
        {
            "source": "google_trends",
            "keyword": "organic delivery",
            "relative_interest": [30] * 12,
            "trend_direction": "stable",
            "latest_value": 30,
            "average_value": 30,
            "peak_value": 30,
            "cache_hit": False,
        },
        # Second keyword failed with rate limit
        {
            "source": "google_trends",
            "keyword": "vegetable box",
            "status": "error",
            "error_type": "rate_limited",
            "error": "429 after 3 retries",
        },
    ]

    with patch("app.nodes.research.run_reddit_search", return_value=_reddit_success()), \
         patch("app.nodes.research.run_trends_search", return_value=mixed_trends), \
         patch("app.nodes.research.run_census_search", return_value=_census_success()), \
         patch("app.nodes.research.run_plfs_search", return_value=_plfs_success()):

        from app.nodes.research import run_research
        result = run_research(TEST_STATE)

    # The successful trend is in evidence
    assert len(result["trends_evidence"]) == 1
    assert result["trends_evidence"][0]["keyword"] == "organic delivery"

    # The failed trend is in errors
    trends_errors = [e for e in result["research_errors"]
                     if e.get("source") == "Google Trends"]
    assert len(trends_errors) == 1
    assert "429" in trends_errors[0].get("error", "")
