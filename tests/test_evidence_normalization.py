"""
tests/test_evidence_normalization.py
------------------------------------
Unit and integration tests for the Common Evidence Schema and Normalizer (Step 2).

Verifies:
  - Valid normalization of Reddit, Google Trends, Census 2011, and PLFS 2025.
  - Optional and missing field handling.
  - Invalid numeric values and malformed records.
  - Empty source results handling.
  - Source provenance and time-period preservation.
  - Census state-level fallback metadata and limitations.
  - PLFS units and survey-weighted indicator metadata.
  - Google Trends cache vs fresh fetch metadata.
  - Source error isolation (failed sources produce no fake records; valid sources normalize).
  - Integration with run_research node preserving raw evidence and research_errors.
"""

import pytest
from unittest.mock import patch

from app.schemas.evidence import (
    EvidenceRecord,
    EvidenceType,
    GeographyScope,
    SourceType,
)
from app.schemas.normalizer import (
    normalize_all_evidence,
    normalize_census_records,
    normalize_plfs_records,
    normalize_reddit_records,
    normalize_trends_records,
)


# ------------------------------------------------------------------
# Fixtures & Sample Payloads
# ------------------------------------------------------------------

SAMPLE_REDDIT_RAW = [
    {
        "source": "reddit",
        "source_type": "historical_dataset",
        "dataset": "Kaggle Reddit dataset",
        "title": "Fresh organic vegetable delivery experience in Ahmedabad",
        "text": "Subscribed to a local weekly farm box. The vegetables were very fresh and delivered on time.",
        "subreddit": "ahmedabad",
        "score": 42,
        "created_at": "2024-03-15",
        "url": "https://reddit.com/r/ahmedabad/comments/xyz123",
        "keywords_matched": ["organic", "delivery", "vegetable"],
        "relevance_query": "organic vegetable delivery",
    }
]

SAMPLE_TRENDS_FRESH = [
    {
        "source": "google_trends",
        "keyword": "organic delivery",
        "geo": "IN-GJ",
        "time_range": "today 12-m",
        "relative_interest": [20.0, 25.0, 30.0, 28.0],
        "date_labels": ["2024-01-01", "2024-02-01", "2024-03-01", "2024-04-01"],
        "trend_direction": "rising",
        "latest_value": 28.0,
        "peak_value": 30.0,
        "average_value": 25.8,
        "cache_hit": False,
        "retrieval_note": "Fresh fetch (attempt 1).",
    }
]

SAMPLE_TRENDS_CACHED = [
    {
        "source": "google_trends",
        "keyword": "vegetable box",
        "geo": "IN-GJ",
        "time_range": "today 12-m",
        "relative_interest": [15.0, 18.0],
        "date_labels": ["2024-01-01", "2024-02-01"],
        "trend_direction": "stable",
        "latest_value": 18.0,
        "peak_value": 18.0,
        "average_value": 16.5,
        "cache_hit": True,
        "cache_age_seconds": 360,
        "retrieval_note": "Served from local cache (age 360s / TTL 3600s).",
    }
]

SAMPLE_CENSUS_AHMEDABAD = [
    {
        "status": "success",
        "source": "Census 2011",
        "source_type": "official_government_dataset",
        "geography": {
            "state": "Gujarat",
            "district": "Ahmadabad",
            "level": "district",
            "tru": "Total",
            "requested_location": "Ahmedabad",
        },
        "metadata": {
            "census_year": 2011,
            "datasets_consulted": ["PCA", "C-08", "C-08A"],
        },
        "pca": {
            "population": {
                "total": 7214225,
                "male": 3788051,
                "female": 3426174,
                "sex_ratio_females_per_1000_males": 904.5,
            },
            "households": 1510134,
            "literacy": {
                "literate_total": 5435760,
                "illiterate_total": 1778465,
                "crude_literacy_rate_percent": 75.35,
                "effective_literacy_rate_percent": 85.31,
            },
            "workers": {
                "total_workers": 2594952,
                "work_participation_rate_percent": 35.97,
                "categories": {
                    "cultivators": {"count": 142670, "share_of_workers_percent": 5.5},
                    "agricultural_labourers": {"count": 268954, "share_of_workers_percent": 10.36},
                    "household_industry": {"count": 54876, "share_of_workers_percent": 2.11},
                    "other_workers": {"count": 2128452, "share_of_workers_percent": 82.02},
                },
            },
        },
        "education": {
            "tru": "Total",
            "is_state_fallback": False,
            "summary": {
                "levels": {
                    "graduate_and_above": {"persons": 817630, "males": 476839, "females": 340791}
                }
            },
        },
        "higher_education": {
            "is_state_fallback": False,
            "summary": {
                "disciplines": {
                    "engineering_and_technology": {"persons": 86953},
                    "medicine": {"persons": 26190},
                    "teaching": {"persons": 23435},
                    "agriculture_and_dairying": {"persons": 1274},
                }
            },
        },
    }
]

SAMPLE_CENSUS_STATE_FALLBACK = [
    {
        "status": "success",
        "source": "Census 2011",
        "source_type": "official_government_dataset",
        "geography": {
            "state": "Maharashtra",
            "district": "Pune",
            "level": "district",
            "tru": "Total",
            "requested_location": "Pune",
        },
        "pca": {
            "population": {"total": 9429408, "male": 4924105, "female": 4505303, "sex_ratio_females_per_1000_males": 915.0},
            "households": 2100000,
            "literacy": {"crude_literacy_rate_percent": 86.15},
            "workers": {"work_participation_rate_percent": 41.5, "total_workers": 3900000, "categories": {}},
        },
        "education": {
            "tru": "Total",
            "is_state_fallback": True,
            "summary": {
                "levels": {"graduate_and_above": {"persons": 8500000}}
            },
        },
        "higher_education": {
            "is_state_fallback": True,
            "summary": {
                "disciplines": {
                    "engineering_and_technology": {"persons": 800000},
                    "medicine": {"persons": 250000},
                    "teaching": {"persons": 200000},
                    "agriculture_and_dairying": {"persons": 15000},
                }
            },
        },
    }
]

SAMPLE_PLFS_AHMEDABAD = [
    {
        "status": "success",
        "source": "PLFS 2025",
        "source_type": "official_government_microdata",
        "geography": {
            "state": "Gujarat",
            "district": "Ahmedabad",
            "st": 24,
            "dc": 7,
            "sector": "Total",
            "level": "district",
        },
        "sample_metadata": {
            "sample_persons_total": 6423,
            "sample_persons_age_15_plus": 5155,
            "estimated_population_total": 6716074,
            "estimated_population_age_15_plus": 5279051,
        },
        "labour_indicators": {
            "benchmark_population": "Age 15 and above (Working Age Population)",
            "usual_status_ps_plus_ss": {
                "lfpr_percent": 55.64,
                "wpr_percent": 55.03,
                "unemployment_rate_percent": 1.10,
            },
        },
        "earnings": {
            "regular_salaried": {
                "avg_monthly_salary_inr": 22638.27,
                "median_monthly_salary_inr": 18000.0,
                "sample_size": 1349,
            },
            "self_employed": {
                "avg_monthly_earnings_inr": 26330.75,
                "median_monthly_earnings_inr": 20000.0,
                "sample_size": 844,
            },
        },
        "education": {
            "graduate_and_above_percent": 23.2,
            "secondary_and_above_percent": 53.31,
            "not_literate_percent": 8.67,
        },
        "household": {
            "status": "available",
            "sample_households": 1500,
            "avg_household_size": 4.19,
            "avg_monthly_consumer_expenditure_inr": 16416.82,
        },
    }
]


# ------------------------------------------------------------------
# 1. Reddit Normalization Tests
# ------------------------------------------------------------------

def test_reddit_normalization_valid():
    records = normalize_reddit_records(SAMPLE_REDDIT_RAW)
    assert len(records) == 1
    rec = records[0]

    assert isinstance(rec, EvidenceRecord)
    assert rec.source == SourceType.REDDIT
    assert rec.evidence_type == EvidenceType.DISCUSSION
    assert "Ahmedabad" in rec.title
    assert "Subreddit: r/ahmedabad" in rec.content
    assert rec.value == 42
    assert rec.unit == "upvotes"
    assert rec.time_period == "2024-03-15"
    assert rec.provenance["dataset"] == "Kaggle Reddit dataset"
    assert rec.metadata["subreddit"] == "ahmedabad"
    assert any("Historical dataset" in lim for lim in rec.limitations)
    assert rec.evidence_id.startswith("ev_reddit_")


def test_reddit_normalization_missing_fields_and_malformed():
    malformed = [
        {"status": "error", "error": "file not found"},
        {"status": "no_results", "error": "no posts found"},
        {"title": "", "text": ""},  # empty content
        {"title": "Valid title", "text": "Some text", "score": "invalid_number"},
        "not a dict",
    ]
    records = normalize_reddit_records(malformed)
    # Only the one with valid title and text should survive
    assert len(records) == 1
    assert records[0].value is None
    assert records[0].unit is None


# ------------------------------------------------------------------
# 2. Google Trends Normalization Tests
# ------------------------------------------------------------------

def test_trends_normalization_valid_fresh():
    records = normalize_trends_records(SAMPLE_TRENDS_FRESH)
    assert len(records) == 1
    rec = records[0]

    assert rec.source == SourceType.GOOGLE_TRENDS
    assert rec.evidence_type == EvidenceType.SEARCH_INTEREST
    assert rec.unit == "relative_interest_index"
    assert rec.value == 28.0
    assert rec.metadata["cache_hit"] is False
    assert rec.metadata["trend_direction"] == "rising"
    assert rec.geography.state == "Gujarat"
    assert rec.geography.country == "India"
    assert any("0-100 scale" in lim for lim in rec.limitations)
    assert rec.evidence_id.startswith("ev_trends_")


def test_trends_normalization_cache_hit_metadata():
    records = normalize_trends_records(SAMPLE_TRENDS_CACHED)
    assert len(records) == 1
    rec = records[0]

    assert rec.metadata["cache_hit"] is True
    assert rec.metadata["cache_age_seconds"] == 360
    assert any("Served from local cache" in lim for lim in rec.limitations)


def test_trends_normalization_errors_and_malformed_ignored():
    err_data = [
        {"status": "error", "error": "429 Too Many Requests"},
        {"status": "no_data", "keyword": "rare term"},
        {"keyword": ""},
        None,
    ]
    records = normalize_trends_records(err_data)
    assert len(records) == 0


# ------------------------------------------------------------------
# 3. Census 2011 Normalization Tests
# ------------------------------------------------------------------

def test_census_normalization_valid_district():
    records = normalize_census_records(SAMPLE_CENSUS_AHMEDABAD)
    # Expect: population, households, literacy, workforce, C-08 graduates, C-08A disciplines
    assert len(records) >= 5

    types = [r.evidence_type for r in records]
    assert EvidenceType.DEMOGRAPHIC_STATISTIC in types
    assert EvidenceType.EDUCATION_STATISTIC in types
    assert EvidenceType.LABOUR_STATISTIC in types

    pop_rec = next(r for r in records if "Population" in r.title)
    assert pop_rec.value == 7214225
    assert pop_rec.unit == "people"
    assert pop_rec.time_period == "2011"
    assert pop_rec.geography.district == "Ahmadabad"
    assert pop_rec.geography.state == "Gujarat"

    grad_rec = next(r for r in records if "Graduate & Above" in r.title)
    assert grad_rec.value == 817630
    assert grad_rec.metadata["is_state_fallback"] is False


def test_census_normalization_state_fallback_metadata():
    records = normalize_census_records(SAMPLE_CENSUS_STATE_FALLBACK)
    assert len(records) >= 4

    grad_rec = next(r for r in records if "Graduate & Above" in r.title)
    assert grad_rec.metadata["is_state_fallback"] is True
    assert any("state-level aggregate shown as fallback" in lim for lim in grad_rec.limitations)
    assert "State-level fallback" in grad_rec.title


def test_census_normalization_missing_sections_and_malformed():
    incomplete = [{
        "status": "success",
        "geography": {"state": "Gujarat", "district": "Surat"},
        "pca": {"population": {"total": 6000000}},  # no households, literacy, education
    }]
    records = normalize_census_records(incomplete)
    assert len(records) == 1
    assert records[0].value == 6000000


# ------------------------------------------------------------------
# 4. PLFS 2025 Normalization Tests
# ------------------------------------------------------------------

def test_plfs_normalization_valid_indicators():
    records = normalize_plfs_records(SAMPLE_PLFS_AHMEDABAD)
    # Expect: labour indicators, salary, self-employed, education, household context
    assert len(records) >= 4

    labour_rec = next(r for r in records if r.evidence_type == EvidenceType.LABOUR_STATISTIC)
    assert labour_rec.value["lfpr_percent"] == 55.64
    assert labour_rec.value["wpr_percent"] == 55.03
    assert labour_rec.value["unemployment_rate_percent"] == 1.10
    assert labour_rec.unit == "percent"
    assert labour_rec.time_period == "2025 (Annual)"
    assert labour_rec.metadata["survey_weighted"] is True

    sal_rec = next(r for r in records if "Regular Salaried" in r.title)
    assert sal_rec.value == 22638.27
    assert sal_rec.unit == "INR/month"
    assert sal_rec.metadata["sample_size"] == 1349

    hh_rec = next(r for r in records if r.evidence_type == EvidenceType.HOUSEHOLD_STATISTIC)
    assert hh_rec.value["avg_household_size"] == 4.19
    assert hh_rec.value["avg_monthly_consumer_expenditure_inr"] == 16416.82


def test_plfs_normalization_limitations_and_non_census_caveats():
    records = normalize_plfs_records(SAMPLE_PLFS_AHMEDABAD)
    labour_rec = next(r for r in records if r.evidence_type == EvidenceType.LABOUR_STATISTIC)
    assert any("not a full census" in lim for lim in labour_rec.limitations)


# ------------------------------------------------------------------
# 5. Empty Results & Edge Cases
# ------------------------------------------------------------------

def test_empty_source_results_returns_empty():
    assert normalize_all_evidence(None, None, None, None) == []
    assert normalize_all_evidence([], [], [], []) == []


def test_deterministic_evidence_id():
    recs1 = normalize_reddit_records(SAMPLE_REDDIT_RAW)
    recs2 = normalize_reddit_records(SAMPLE_REDDIT_RAW)
    assert len(recs1) == len(recs2)
    assert recs1[0].evidence_id == recs2[0].evidence_id


def test_source_failure_isolation_in_normalizer():
    # Trends and Census fail, but Reddit and PLFS succeed
    mixed = normalize_all_evidence(
        reddit_evidence=SAMPLE_REDDIT_RAW,
        trends_evidence=[{"status": "error", "error": "Trends 429"}],
        census_evidence=[{"status": "error", "error": "Census file missing"}],
        plfs_evidence=SAMPLE_PLFS_AHMEDABAD,
    )
    sources = {r.source for r in mixed}
    assert SourceType.REDDIT in sources
    assert SourceType.PLFS in sources
    assert SourceType.GOOGLE_TRENDS not in sources
    assert SourceType.CENSUS not in sources


# ------------------------------------------------------------------
# 6. Integration Test with run_research Node
# ------------------------------------------------------------------

def test_run_research_produces_normalized_evidence():
    from app.nodes.research import run_research

    state = {
        "idea": "Vegetable delivery in Ahmedabad",
        "keywords": ["vegetable", "delivery"],
        "target_segment": "Families",
        "location": "Ahmedabad",
        "district": "Ahmedabad",
        "research_type": "location_based",
    }

    with patch("app.nodes.research.run_reddit_search", return_value=SAMPLE_REDDIT_RAW), \
         patch("app.nodes.research.run_trends_search", return_value=SAMPLE_TRENDS_FRESH), \
         patch("app.nodes.research.run_census_search", return_value=SAMPLE_CENSUS_AHMEDABAD[0]), \
         patch("app.nodes.research.run_plfs_search", return_value=SAMPLE_PLFS_AHMEDABAD[0]):

        result = run_research(state)

    assert result["research_complete"] is True
    # Raw evidences preserved
    assert len(result["reddit_evidence"]) == 1
    assert len(result["trends_evidence"]) == 1
    assert len(result["census_evidence"]) == 1
    assert len(result["plfs_evidence"]) == 1
    # Normalized evidence collection populated
    assert "normalized_evidence" in result
    norm = result["normalized_evidence"]
    assert isinstance(norm, list)
    assert len(norm) > 0
    # Every normalized record can be parsed back into EvidenceRecord
    validated = [EvidenceRecord.model_validate(r) for r in norm]
    assert len(validated) == len(norm)
