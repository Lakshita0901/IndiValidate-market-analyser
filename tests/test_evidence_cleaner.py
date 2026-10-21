"""
tests/test_evidence_cleaner.py
------------------------------
Unit and integration tests for Evidence Cleaning and Standardization (Step 3).

Verifies:
  - Whitespace normalization and non-printable control character removal.
  - Stable deduplication and duplicate counts.
  - Distinct records are never improperly merged.
  - Numeric and unit validation (rejecting NaN, Inf, invalid percentages).
  - Missing geography or dates are never fabricated.
  - Census fallback and PLFS survey-weighting preservation.
  - Google Trends metadata (cache status, relative interest caveats) preservation.
  - Deterministic Reddit relevance classification (known r/jobs false positive).
  - Multi-metric decomposition into atomic single-indicator records.
  - Source error isolation and integration with run_research node.
"""

import math
import pytest
from unittest.mock import patch

from app.schemas.evidence import (
    EvidenceRecord,
    EvidenceType,
    GeographyScope,
    SourceType,
)
from app.schemas.cleaner import (
    assess_reddit_relevance,
    clean_evidence,
    clean_text,
    decompose_multi_metric_record,
    standardize_geography,
    validate_numeric_value,
)


# ------------------------------------------------------------------
# Test Fixtures & Samples
# ------------------------------------------------------------------

_DEFAULT_GEO = object()

def _make_sample_record(
    source=SourceType.CENSUS,
    evidence_type=EvidenceType.DEMOGRAPHIC_STATISTIC,
    title="Census 2011: Population (Ahmedabad, Total)",
    content="Census 2011 Total Population in Ahmedabad: 7,214,225 persons.",
    value=7214225,
    unit="people",
    geography=_DEFAULT_GEO,
    time_period="2011",
    evidence_id="ev_test_123",
    metadata=None,
    limitations=None,
    relevance=None,
) -> EvidenceRecord:
    actual_geo = (
        GeographyScope(country="India", state="Gujarat", district="Ahmedabad", rural_urban="Total", level="district")
        if geography is _DEFAULT_GEO
        else geography
    )
    return EvidenceRecord(
        evidence_id=evidence_id,
        source=source,
        evidence_type=evidence_type,
        title=title,
        content=content,
        value=value,
        unit=unit,
        geography=actual_geo,
        time_period=time_period,
        provenance={"dataset": "Test dataset"},
        metadata=metadata or {},
        limitations=limitations or ["Test limitation."],
        relevance=relevance,
    )


# ------------------------------------------------------------------
# 1. Text Cleaning Tests
# ------------------------------------------------------------------

def test_clean_text_whitespace_and_control_characters():
    # Dirty text with control characters, tabs, multiple spaces, and excessive newlines
    dirty = "Hello\x00\x08World!\t\tThis   is  a\x1f test.\n\n\n\nPreserve   meaningful-punctuation: $100, 50% & URLs https://example.com."
    cleaned = clean_text(dirty)

    assert "\x00" not in cleaned
    assert "\x08" not in cleaned
    assert "\x1f" not in cleaned
    assert "  " not in cleaned  # no double spaces
    assert "\n\n\n" not in cleaned  # no triple newlines
    assert "Hello World!" in cleaned
    assert "Preserve meaningful-punctuation: $100, 50% & URLs https://example.com." in cleaned


def test_clean_text_preserves_negation_and_quotes():
    text = "We did 'not' receive the produce. No vegetables were delivered, never again!"
    cleaned = clean_text(text)
    assert "did 'not' receive" in cleaned
    assert "No vegetables were delivered, never again!" in cleaned


# ------------------------------------------------------------------
# 2. Deduplication Tests
# ------------------------------------------------------------------

def test_stable_deduplication():
    rec1 = _make_sample_record(evidence_id="ev_1", title="Census 2011: Population (Ahmedabad)", value=7000000)
    rec2 = _make_sample_record(evidence_id="ev_2", title="Census 2011: Population (Ahmedabad)", value=7000000)  # exact content duplicate

    cleaned, diag = clean_evidence([rec1, rec2])
    assert len(cleaned) == 1
    assert diag["duplicates_removed_count"] == 1


def test_distinct_records_not_merged():
    pop_rec = _make_sample_record(evidence_id="ev_pop", title="Census 2011: Population (Ahmedabad)", value=7000000, unit="people")
    hh_rec = _make_sample_record(evidence_id="ev_hh", title="Census 2011: Households (Ahmedabad)", value=1500000, unit="households")

    cleaned, diag = clean_evidence([pop_rec, hh_rec])
    assert len(cleaned) == 2
    assert diag["duplicates_removed_count"] == 0


# ------------------------------------------------------------------
# 3. Numeric & Unit Validation Tests
# ------------------------------------------------------------------

def test_validate_numeric_rejects_nan_and_inf():
    is_valid, err = validate_numeric_value(float("nan"), "percent", EvidenceType.LABOUR_STATISTIC, {})
    assert not is_valid
    assert "NaN" in err

    is_valid, err = validate_numeric_value(float("inf"), "people", EvidenceType.DEMOGRAPHIC_STATISTIC, {})
    assert not is_valid
    assert "Infinity" in err


def test_validate_numeric_percentages_range():
    # Valid percentage
    is_valid, _ = validate_numeric_value(55.64, "percent", EvidenceType.LABOUR_STATISTIC, {})
    assert is_valid

    # Out of range percentages
    is_valid, err = validate_numeric_value(120.5, "percent", EvidenceType.LABOUR_STATISTIC, {})
    assert not is_valid
    assert "outside the valid range" in err

    is_valid, err = validate_numeric_value(-5.0, "percent", EvidenceType.LABOUR_STATISTIC, {})
    assert not is_valid
    assert "outside the valid range" in err


def test_validate_numeric_relative_interest_index_range():
    is_valid, _ = validate_numeric_value(27.0, "relative_interest_index", EvidenceType.SEARCH_INTEREST, {})
    assert is_valid

    is_valid, err = validate_numeric_value(150.0, "relative_interest_index", EvidenceType.SEARCH_INTEREST, {})
    assert not is_valid


def test_validate_numeric_counts_non_negative():
    is_valid, _ = validate_numeric_value(1500, "people", EvidenceType.DEMOGRAPHIC_STATISTIC, {})
    assert is_valid

    is_valid, err = validate_numeric_value(-50, "people", EvidenceType.DEMOGRAPHIC_STATISTIC, {})
    assert not is_valid
    assert "cannot be negative" in err


def test_validate_numeric_self_employed_loss_allowed():
    # Normal salary cannot be negative
    is_valid, err = validate_numeric_value(-5000.0, "INR/month", EvidenceType.EARNINGS_STATISTIC, {})
    assert not is_valid

    # Self-employed with documented business net loss is allowed
    is_valid, err = validate_numeric_value(-3500.0, "INR/month", EvidenceType.EARNINGS_STATISTIC, {"reporting_net_loss_count": 5})
    assert is_valid


# ------------------------------------------------------------------
# 4. Geography and Time Standardization Tests
# ------------------------------------------------------------------

def test_standardize_geography_census_spelling():
    geo = GeographyScope(country="India", state="gujarat", district="Ahmadabad", rural_urban="total", level="district")
    std = standardize_geography(geo)

    assert std.district == "Ahmedabad"  # Standardized Census spelling
    assert std.state == "Gujarat"
    assert std.rural_urban == "Total"
    assert std.country == "India"


def test_missing_geography_and_date_not_guessed():
    rec = _make_sample_record(
        source=SourceType.REDDIT,
        evidence_type=EvidenceType.DISCUSSION,
        title="Discussion on online shopping",
        geography=None,
        time_period=None,
    )
    cleaned, _ = clean_evidence([rec])
    assert len(cleaned) == 1
    assert cleaned[0].geography is None  # Not fabricated
    assert cleaned[0].time_period is None  # Not fabricated


# ------------------------------------------------------------------
# 5. Metadata & Fallback Preservation Tests
# ------------------------------------------------------------------

def test_census_fallback_preservation():
    rec = _make_sample_record(
        title="Census 2011: Graduate & Above (Pune, State-level fallback)",
        metadata={"is_state_fallback": True, "graduate_and_above": 8500000},
        limitations=["District-level data unavailable; state-level fallback."],
    )
    cleaned, _ = clean_evidence([rec])
    assert len(cleaned) == 1
    assert cleaned[0].metadata["is_state_fallback"] is True
    assert any("state-level fallback" in lim for lim in cleaned[0].limitations)


def test_plfs_weighting_and_sample_size_preservation():
    rec = _make_sample_record(
        source=SourceType.PLFS,
        evidence_type=EvidenceType.EARNINGS_STATISTIC,
        title="PLFS 2025: Regular Salaried Monthly Earnings (Ahmedabad)",
        value=22638.27,
        unit="INR/month",
        metadata={"survey_weighted": True, "sample_size": 1349},
    )
    cleaned, _ = clean_evidence([rec])
    assert len(cleaned) == 1
    assert cleaned[0].metadata["survey_weighted"] is True
    assert cleaned[0].metadata["sample_size"] == 1349


def test_google_trends_metadata_preservation():
    rec = _make_sample_record(
        source=SourceType.GOOGLE_TRENDS,
        evidence_type=EvidenceType.SEARCH_INTEREST,
        title="Google Trends: 'organic delivery' search interest (IN-GJ)",
        value=28.0,
        unit="relative_interest_index",
        metadata={"cache_hit": True, "cache_age_seconds": 360, "trend_direction": "rising"},
    )
    cleaned, _ = clean_evidence([rec])
    assert len(cleaned) == 1
    assert cleaned[0].metadata["cache_hit"] is True
    assert cleaned[0].metadata["trend_direction"] == "rising"


# ------------------------------------------------------------------
# 6. Reddit Relevance Assessment Tests
# ------------------------------------------------------------------

def test_reddit_relevance_known_false_positive_scenario():
    # The known false positive: user searching for organic vegetable delivery matched a post
    # in r/jobs about a warehouse worker getting laid off.
    warehouse_job_rec = _make_sample_record(
        source=SourceType.REDDIT,
        evidence_type=EvidenceType.DISCUSSION,
        title="take lowpaying warehouse job wait unemployment",
        content="Subreddit: r/jobs. Excerpt: 'furloughed from logistics position, got fired need personally deliver companys property back'. Matched Keywords: online delivery service",
        value=1,
        unit="upvotes",
        geography=None,
        metadata={
            "subreddit": "jobs",
            "post_title": "take lowpaying warehouse job wait unemployment",
            "post_text": "furloughed position logistics coordinator, got fired need deliver property back",
            "keywords_matched": ["online delivery service"],
        },
    )

    cleaned, diag = clean_evidence(
        [warehouse_job_rec],
        query="online organic vegetable delivery service for families in Ahmedabad",
        keywords=["organic vegetable delivery", "Ahmedabad families"],
    )

    assert len(cleaned) == 1
    # Must NOT be deleted; must be preserved with transparent relevance flag
    rec = cleaned[0]
    assert rec.relevance == "irrelevant"
    assert "r/jobs" in rec.metadata["relevance_reason"]
    assert diag["relevance_breakdown"]["irrelevant"] == 1


def test_reddit_relevance_consumer_post():
    consumer_rec = _make_sample_record(
        source=SourceType.REDDIT,
        evidence_type=EvidenceType.DISCUSSION,
        title="Fresh organic vegetable delivery in Ahmedabad",
        content="Subreddit: r/ahmedabad. Excerpt: 'Tried the weekly organic farm box grocery delivery. Very fresh produce and doorstep delivery.'",
        value=50,
        unit="upvotes",
        geography=None,
        metadata={
            "subreddit": "ahmedabad",
            "post_title": "Fresh organic vegetable delivery in Ahmedabad",
            "post_text": "Tried the weekly organic farm box grocery delivery. Very fresh produce and doorstep delivery.",
        },
    )

    cleaned, diag = clean_evidence([consumer_rec], query="organic vegetable delivery")
    assert len(cleaned) == 1
    assert cleaned[0].relevance == "potentially_relevant"
    assert diag["relevance_breakdown"]["potentially_relevant"] == 1


def test_reddit_relevance_insufficient_context():
    short_rec = _make_sample_record(
        source=SourceType.REDDIT,
        evidence_type=EvidenceType.DISCUSSION,
        title="delivery",
        content="Subreddit: r/india. Excerpt: 'good.'",
        value=0,
        unit="upvotes",
        metadata={"subreddit": "india", "post_title": "delivery", "post_text": "good."},
    )

    cleaned, diag = clean_evidence([short_rec])
    assert len(cleaned) == 1
    assert cleaned[0].relevance == "insufficient_context"


# ------------------------------------------------------------------
# 7. Multi-Metric Decomposition Tests
# ------------------------------------------------------------------

def test_multi_metric_decomposition_plfs_labour():
    compound_rec = _make_sample_record(
        source=SourceType.PLFS,
        evidence_type=EvidenceType.LABOUR_STATISTIC,
        title="PLFS 2025: Labour Indicators (Usual Status, Ahmedabad)",
        value={"lfpr_percent": 55.64, "wpr_percent": 55.03, "unemployment_rate_percent": 1.10},
        unit="percent",
    )

    atomic_recs = decompose_multi_metric_record(compound_rec)
    assert len(atomic_recs) == 3

    titles = [r.title for r in atomic_recs]
    assert any("Labour Force Participation Rate (LFPR)" in t for t in titles)
    assert any("Worker Population Ratio (WPR)" in t for t in titles)
    assert any("Unemployment Rate (UR)" in t for t in titles)

    lfpr = next(r for r in atomic_recs if "LFPR" in r.title)
    assert lfpr.value == 55.64
    assert lfpr.unit == "percent"
    assert lfpr.evidence_id.endswith("_lfpr")


def test_multi_metric_decomposition_census_c08a():
    compound_rec = _make_sample_record(
        source=SourceType.CENSUS,
        evidence_type=EvidenceType.EDUCATION_STATISTIC,
        title="Census 2011: Higher Education Disciplines (Ahmedabad)",
        value={
            "engineering_and_technology": 86953,
            "medicine": 26190,
            "teaching": 23435,
            "agriculture_and_dairying": 1274,
        },
        unit="people",
    )

    atomic_recs = decompose_multi_metric_record(compound_rec)
    assert len(atomic_recs) == 4

    eng = next(r for r in atomic_recs if "Engineering" in r.title)
    assert eng.value == 86953
    assert eng.unit == "people"


def test_multi_metric_decomposition_plfs_household():
    compound_rec = _make_sample_record(
        source=SourceType.PLFS,
        evidence_type=EvidenceType.HOUSEHOLD_STATISTIC,
        title="PLFS 2025: Household Size & Expenditure (Ahmedabad)",
        value={"avg_household_size": 4.19, "avg_monthly_consumer_expenditure_inr": 16416.82},
        unit="INR/month",
    )

    atomic_recs = decompose_multi_metric_record(compound_rec)
    assert len(atomic_recs) == 2

    size_rec = next(r for r in atomic_recs if "Household Size" in r.title)
    assert size_rec.value == 4.19
    assert size_rec.unit == "persons_per_household"

    hce_rec = next(r for r in atomic_recs if "Consumer Expenditure" in r.title)
    assert hce_rec.value == 16416.82
    assert hce_rec.unit == "INR/month"


# ------------------------------------------------------------------
# 8. Source Error Isolation & Integration Tests
# ------------------------------------------------------------------

def test_partial_cleaning_failure_and_isolation():
    valid_rec = _make_sample_record(title="Valid Population", value=5000000, unit="people")
    corrupt_rec = _make_sample_record(title="Corrupt Rate", value=150.0, unit="percent")  # invalid >100%

    cleaned, diag = clean_evidence([valid_rec, corrupt_rec])
    # The valid record must be preserved; corrupt record rejected
    assert len(cleaned) == 1
    assert cleaned[0].title == "Valid Population"
    assert diag["numeric_issues_flagged_count"] == 1


def test_integration_run_research_produces_cleaned_evidence():
    from app.nodes.research import run_research

    state = {
        "idea": "Online organic vegetable delivery in Ahmedabad",
        "keywords": ["organic", "vegetable", "delivery"],
        "target_segment": "Families",
        "location": "Ahmedabad",
        "district": "Ahmedabad",
        "research_type": "location_based",
    }

    mock_trends = [{
        "source": "google_trends",
        "keyword": "organic delivery",
        "geo": "IN-GJ",
        "latest_value": 30.0,
        "average_value": 25.0,
        "peak_value": 35.0,
        "trend_direction": "rising",
        "cache_hit": False,
    }]

    mock_census = {
        "status": "success",
        "source": "Census 2011",
        "geography": {"state": "Gujarat", "district": "Ahmedabad"},
        "pca": {"population": {"total": 7000000}, "households": 1500000},
    }

    mock_plfs = {
        "status": "success",
        "source": "PLFS 2025",
        "geography": {"state": "Gujarat", "district": "Ahmedabad"},
        "labour_indicators": {
            "usual_status_ps_plus_ss": {"lfpr_percent": 55.64, "wpr_percent": 55.03, "unemployment_rate_percent": 1.10}
        },
        "earnings": {"regular_salaried": {"avg_monthly_salary_inr": 22638.0}},
    }

    with patch("app.nodes.research.run_reddit_search", return_value=[]), \
         patch("app.nodes.research.run_trends_search", return_value=mock_trends), \
         patch("app.nodes.research.run_census_search", return_value=mock_census), \
         patch("app.nodes.research.run_plfs_search", return_value=mock_plfs):

        result = run_research(state)

    assert result["research_complete"] is True
    assert "normalized_evidence" in result
    assert "cleaned_evidence" in result
    assert "cleaning_diagnostics" in result
    assert len(result["cleaned_evidence"]) > 0
    # PLFS compound labour metric was decomposed into atomic records in cleaned_evidence
    cleaned_titles = [r["title"] for r in result["cleaned_evidence"]]
    assert any("LFPR" in t for t in cleaned_titles)
    assert any("WPR" in t for t in cleaned_titles)
    assert any("UR" in t for t in cleaned_titles)
