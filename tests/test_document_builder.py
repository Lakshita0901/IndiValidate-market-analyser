"""
test_document_builder.py
------------------------
Comprehensive test suite for Step 4: Convert Cleaned Evidence into Retrieval-Ready Documents.

Tests coverage:
  1. All four sources (Reddit, Google Trends, Census, PLFS) producing appropriate readable text.
  2. Atomic metrics becoming separate documents.
  3. Metadata preservation and serialization (including to_chroma_metadata).
  4. Stable document IDs across repeated runs.
  5. Missing optional fields handled gracefully.
  6. Reddit irrelevant records being excluded by default and separated in diagnostics.
  7. Optional inclusion of irrelevant records when requested.
  8. No fabricated facts or units.
  9. Empty evidence collections handling.
  10. Malformed records isolation.
  11. Research errors remaining separate from document content.
  12. End-to-end integration with run_research producing retrieval_documents.
"""

import json
from unittest.mock import patch
import pytest

from app.rag.document_builder import (
    RetrievalDocument,
    build_retrieval_documents,
    format_geography,
    format_value,
)
from app.schemas.evidence import (
    EvidenceRecord,
    EvidenceType,
    GeographyScope,
    SourceType,
)
from app.schemas.cleaner import clean_evidence
from app.nodes.research import run_research


# ------------------------------------------------------------------
# Test Fixtures
# ------------------------------------------------------------------

def make_sample_reddit_record(
    title: str = "Best organic produce delivery in Ahmedabad",
    text: str = "Looking for fresh pesticide-free vegetables delivered weekly.",
    subreddit: str = "ahmedabad",
    score: int = 15,
    relevance: str = "potentially_relevant",
) -> EvidenceRecord:
    return EvidenceRecord(
        evidence_id="ev_reddit_sample_123",
        source=SourceType.REDDIT,
        evidence_type=EvidenceType.DISCUSSION,
        title=f"Reddit Discussion: {title}",
        content=f"Subreddit: r/{subreddit}. Title: '{title}'. Excerpt: '{text}'.",
        value=score,
        unit="upvotes",
        geography=None,
        time_period="2023-08-15",
        retrieved_at="2026-10-10T20:00:00Z",
        provenance={"source_type": "historical_dataset", "dataset": "Kaggle Reddit dataset", "url": "https://reddit.com/r/ahmedabad/123"},
        metadata={
            "subreddit": subreddit,
            "post_title": title,
            "post_text": text,
            "score": score,
            "keywords_matched": ["organic", "vegetable"],
            "relevance_reason": "Post directly discusses commercial consumer delivery or food topics.",
        },
        relevance=relevance,
        limitations=["Historical dataset observation from Kaggle archive."],
    )


def make_sample_trends_record(
    keyword: str = "organic vegetables",
    geo_code: str = "IN-GJ",
    state: str = "Gujarat",
    latest: float = 52.0,
    average: float = 44.5,
    trend_dir: str = "rising",
    is_cached: bool = True,
) -> EvidenceRecord:
    return EvidenceRecord(
        evidence_id="ev_trends_sample_456",
        source=SourceType.GOOGLE_TRENDS,
        evidence_type=EvidenceType.SEARCH_INTEREST,
        title=f"Google Trends: '{keyword}' search interest ({geo_code})",
        content=f"Google Trends relative search interest for '{keyword}' in {geo_code}: latest index={latest}/100.",
        value=latest,
        unit="relative_interest_index",
        geography=GeographyScope(country="India", state=state, level="state"),
        time_period="2023-10 to 2024-10 (today 12-m)",
        retrieved_at="2026-10-10T20:00:00Z",
        provenance={"source": "Google Trends via pytrends", "endpoint": "interest_over_time"},
        metadata={
            "keyword": keyword,
            "geo_code": geo_code,
            "trend_direction": trend_dir,
            "latest_value": latest,
            "average_value": average,
            "peak_value": 85.0,
            "cache_hit": is_cached,
            "cache_age_seconds": 120,
        },
        relevance="unreviewed",
        limitations=["Relative search interest on a 0-100 scale; does not represent absolute search volume."],
    )


def make_sample_census_record(
    indicator: str = "Population",
    value: int = 7214225,
    unit: str = "people",
    is_fallback: bool = False,
) -> EvidenceRecord:
    return EvidenceRecord(
        evidence_id="ev_census_sample_789",
        source=SourceType.CENSUS,
        evidence_type=EvidenceType.DEMOGRAPHIC_STATISTIC,
        title=f"Census 2011: {indicator} (Ahmedabad, Total)",
        content=f"Census 2011 Total Population in Ahmedabad, Gujarat (Total): 7,214,225 persons.",
        value=value,
        unit=unit,
        geography=GeographyScope(country="India", state="Gujarat", district="Ahmedabad", rural_urban="Total", level="district"),
        time_period="2011",
        retrieved_at=None,
        provenance={"dataset": "Primary Census Abstract (PCA 2011)", "census_year": 2011},
        metadata={"male_population": 3788051, "female_population": 3426174, "is_state_fallback": is_fallback},
        relevance="unreviewed",
        limitations=["Official Census 2011 benchmark."],
    )


def make_sample_plfs_record(
    indicator: str = "Labour Force Participation Rate (LFPR)",
    value: float = 55.64,
    unit: str = "percent",
) -> EvidenceRecord:
    return EvidenceRecord(
        evidence_id="ev_plfs_sample_101",
        source=SourceType.PLFS,
        evidence_type=EvidenceType.LABOUR_STATISTIC,
        title=f"PLFS 2025: {indicator} (Ahmedabad)",
        content=f"PLFS 2025 LFPR for Ahmedabad (Total, Age 15+): 55.64% (Usual Status ps+ss, survey-weighted).",
        value=value,
        unit=unit,
        geography=GeographyScope(country="India", state="Gujarat", district="Ahmedabad", rural_urban="Total", level="district"),
        time_period="2025 (Annual)",
        retrieved_at=None,
        provenance={"survey": "Periodic Labour Force Survey (PLFS) 2025", "period": "2025", "sample_size_persons": 1420},
        metadata={"survey_weighted": True, "benchmark_population": "Age 15+ (Working Age)", "sample_size": 1420},
        relevance="unreviewed",
        limitations=["Sample survey estimate from MoSPI PLFS 2025 microdata."],
    )


# ------------------------------------------------------------------
# 1. Source-Specific Text Generation Tests
# ------------------------------------------------------------------

def test_reddit_document_generation():
    """Verify Reddit record produces factual text preserving subreddit, text, and limitations."""
    rec = make_sample_reddit_record()
    docs, diag = build_retrieval_documents([rec])

    assert len(docs) == 1
    doc = docs[0]
    assert doc.document_id == f"doc_{rec.evidence_id}"
    assert "r/ahmedabad" in doc.text
    assert "fresh pesticide-free vegetables" in doc.text
    assert "Historical Reddit Discussion Record" in doc.text
    assert "15 upvotes" in doc.text
    assert "does not establish quantified market size" in doc.text
    assert doc.metadata["source"] == "reddit"
    assert doc.metadata["subreddit"] == "ahmedabad"
    assert doc.metadata["post_score"] == 15
    assert doc.metadata["is_retrieval_ready"] is True


def test_trends_document_generation():
    """Verify Google Trends record explicitly states relative search interest (not absolute volume)."""
    rec = make_sample_trends_record()
    docs, diag = build_retrieval_documents([rec])

    assert len(docs) == 1
    doc = docs[0]
    assert "organic vegetables" in doc.text
    assert "52.0/100" in doc.text or "52/100" in doc.text
    assert "rising" in doc.text
    assert "does NOT represent absolute search volume" in doc.text
    assert "Local cache record" in doc.text
    assert doc.metadata["source"] == "google_trends"
    assert doc.metadata["trend_direction"] == "rising"
    assert doc.metadata["is_cached"] is True


def test_census_document_generation():
    """Verify Census record includes reference year 2011, metric, value, unit, and table provenance."""
    rec = make_sample_census_record()
    docs, diag = build_retrieval_documents([rec])

    assert len(docs) == 1
    doc = docs[0]
    assert "Census 2011 Demographic Record" in doc.text
    assert "7,214,225 people" in doc.text
    assert "Reference Benchmark Year: 2011" in doc.text
    assert "Primary Census Abstract (PCA 2011)" in doc.text
    assert "Ahmedabad District, Gujarat" in doc.text
    assert doc.metadata["source"] == "census"
    assert doc.metadata["census_year"] == 2011


def test_census_state_fallback_document_generation():
    """Verify Census record with state fallback explicitly includes fallback caveat in text and metadata."""
    rec = make_sample_census_record(indicator="Graduates in Engineering", value=12400, is_fallback=True)
    rec.metadata["is_state_fallback"] = True
    docs, diag = build_retrieval_documents([rec])

    assert len(docs) == 1
    doc = docs[0]
    assert "Geographic Fallback Notice" in doc.text
    assert "state-level aggregate fallback" in doc.text
    assert doc.metadata["is_state_fallback"] is True


def test_plfs_document_generation():
    """Verify PLFS record includes survey reference period, survey-weighted context, and sample size."""
    rec = make_sample_plfs_record()
    docs, diag = build_retrieval_documents([rec])

    assert len(docs) == 1
    doc = docs[0]
    assert "PLFS 2025 Official Labour Record" in doc.text
    assert "55.64%" in doc.text
    assert "Survey Reference Period: 2025" in doc.text
    assert "Survey-weighted estimate" in doc.text
    assert "1,420 respondents" in doc.text
    assert doc.metadata["source"] == "plfs"
    assert doc.metadata["is_survey_weighted"] is True
    assert doc.metadata["sample_size"] == 1420


# ------------------------------------------------------------------
# 2. Atomic Metrics Separation Tests
# ------------------------------------------------------------------

def test_atomic_metrics_separate_documents():
    """Verify compound statistics decomposed by cleaner yield distinct, self-contained documents."""
    compound_plfs = EvidenceRecord(
        evidence_id="ev_plfs_headline_1",
        source=SourceType.PLFS,
        evidence_type=EvidenceType.LABOUR_STATISTIC,
        title="PLFS 2025 Headline Labour Indicators",
        content="LFPR, WPR, UR indicators",
        value={"lfpr_percent": 55.64, "wpr_percent": 55.03, "unemployment_rate_percent": 1.10},
        unit="percent",
        geography=GeographyScope(country="India", state="Gujarat", district="Ahmedabad", level="district"),
        time_period="2025 (Annual)",
        metadata={"survey_weighted": True},
    )

    # Cleaner decomposes into 3 atomic records
    cleaned_records, clean_diag = clean_evidence([compound_plfs])
    assert len(cleaned_records) == 3

    # Document builder creates 3 separate documents
    docs, doc_diag = build_retrieval_documents(cleaned_records)
    assert len(docs) == 3

    doc_ids = [d.document_id for d in docs]
    assert len(set(doc_ids)) == 3
    assert any("lfpr" in d.document_id for d in docs)
    assert any("wpr" in d.document_id for d in docs)
    assert any("ur" in d.document_id for d in docs)

    # Verify each document contains only its respective statistic
    lfpr_doc = next(d for d in docs if "lfpr" in d.document_id)
    assert "55.64%" in lfpr_doc.text
    assert "Labour Force Participation Rate" in lfpr_doc.text


# ------------------------------------------------------------------
# 3. Stability & Determinism Tests
# ------------------------------------------------------------------

def test_stable_document_id_across_runs():
    """Document IDs and content must remain strictly identical across repeated runs."""
    rec = make_sample_census_record()
    docs_run1, _ = build_retrieval_documents([rec])
    docs_run2, _ = build_retrieval_documents([rec])

    assert docs_run1[0].document_id == docs_run2[0].document_id
    assert docs_run1[0].text == docs_run2[0].text
    assert docs_run1[0].metadata == docs_run2[0].metadata


# ------------------------------------------------------------------
# 4. Metadata Preservation & ChromaDB Serialization Tests
# ------------------------------------------------------------------

def test_metadata_preservation_and_chroma_serialization():
    """Verify structured metadata is preserved and to_chroma_metadata produces strictly primitive types."""
    rec = make_sample_trends_record()
    docs, _ = build_retrieval_documents([rec])
    doc = docs[0]

    assert doc.metadata["keyword"] == "organic vegetables"
    assert doc.metadata["geo_code"] == "IN-GJ"
    assert doc.metadata["formatted_geography"] == "Gujarat, India (state level)"
    assert doc.metadata["latest_value"] == 52.0
    assert doc.metadata["is_cached"] is True
    assert isinstance(doc.metadata["limitations"], list)

    # Test Chroma serialization
    chroma_meta = doc.to_chroma_metadata()
    for k, v in chroma_meta.items():
        assert isinstance(v, (str, int, float, bool)), f"Key {k} has unsupported Chroma type: {type(v)}"

    # Check limitations was serialized as JSON string
    limits_parsed = json.loads(str(chroma_meta["limitations"]))
    assert isinstance(limits_parsed, list)
    assert "Relative search interest" in limits_parsed[0]


# ------------------------------------------------------------------
# 5. Missing Optional Fields Handling
# ------------------------------------------------------------------

def test_missing_optional_fields_handled_gracefully():
    """Records with missing geography, dates, scores, or units convert smoothly without crashing or fabricating None."""
    sparse_rec = EvidenceRecord(
        evidence_id="ev_sparse_001",
        source=SourceType.REDDIT,
        evidence_type=EvidenceType.DISCUSSION,
        title="Anonymous discussion",
        content="General comment without geo or date.",
        value=None,
        unit=None,
        geography=None,
        time_period=None,
        retrieved_at=None,
        provenance=None,
        metadata={},
        relevance="unreviewed",
        limitations=[],
    )

    docs, diag = build_retrieval_documents([sparse_rec])
    assert len(docs) == 1
    doc = docs[0]
    assert "None" not in doc.text
    assert doc.metadata["country"] is None
    assert doc.metadata["formatted_geography"] is None
    assert doc.metadata["unit"] is None


# ------------------------------------------------------------------
# 6. Relevance Filtering & False-Positive Handling
# ------------------------------------------------------------------

def test_reddit_irrelevant_records_excluded_by_default():
    """Off-topic records flagged as irrelevant (e.g. warehouse job post) are excluded from retrieval collection."""
    irrelevant_rec = make_sample_reddit_record(
        title="Laid off yesterday from warehouse job, returning laptop",
        text="My manager told me to return the badge and laptop today.",
        subreddit="jobs",
        score=45,
        relevance="irrelevant",
    )
    relevant_rec = make_sample_reddit_record(
        title="Organic grocery delivery in Ahmedabad",
        text="Looking for fresh organic farm boxes.",
        subreddit="ahmedabad",
        score=20,
        relevance="potentially_relevant",
    )

    docs, diag = build_retrieval_documents([irrelevant_rec, relevant_rec])

    # Default: irrelevant excluded
    assert len(docs) == 1
    assert docs[0].metadata["title"] == relevant_rec.title
    assert diag["excluded_irrelevant_count"] == 1
    assert diag["retrieval_ready_count"] == 1
    assert len(diag["excluded_irrelevant_documents"]) == 1
    assert diag["excluded_irrelevant_documents"][0]["document_id"] == f"doc_{irrelevant_rec.evidence_id}"


def test_reddit_irrelevant_records_included_when_requested():
    """When include_irrelevant=True, irrelevant records are included with is_retrieval_ready=False."""
    irrelevant_rec = make_sample_reddit_record(relevance="irrelevant")

    docs, diag = build_retrieval_documents([irrelevant_rec], include_irrelevant=True)

    assert len(docs) == 1
    assert docs[0].metadata["is_retrieval_ready"] is False
    assert docs[0].metadata["relevance"] == "irrelevant"
    assert diag["excluded_irrelevant_count"] == 1


# ------------------------------------------------------------------
# 7. No Fabricated Facts or Units
# ------------------------------------------------------------------

def test_no_fabricated_facts_or_units():
    """Verify document builder does not inject customer willingness to pay, market demand, or synthetic units."""
    rec = make_sample_census_record(indicator="Total Literates", value=5200000, unit="people")
    docs, _ = build_retrieval_documents([rec])
    text = docs[0].text

    assert "customer demand" not in text.lower()
    assert "willing to pay" not in text.lower()
    assert "market preference" not in text.lower()
    assert "INR" not in text  # No invented currency for demographic counts


# ------------------------------------------------------------------
# 8. Empty Evidence Collections
# ------------------------------------------------------------------

def test_empty_evidence_collection():
    """Passing empty list or None returns empty docs and empty diagnostics without error."""
    docs, diag = build_retrieval_documents([])
    assert docs == []
    assert diag["input_records_count"] == 0

    docs_none, diag_none = build_retrieval_documents(None)
    assert docs_none == []
    assert diag_none["input_records_count"] == 0


# ------------------------------------------------------------------
# 9. Malformed Records Isolation
# ------------------------------------------------------------------

def test_malformed_records_isolation():
    """A corrupted or invalid record in the collection does not crash or discard valid records."""
    valid_rec = make_sample_census_record()
    malformed_item = "not a valid evidence record or dict"
    corrupt_dict = {"invalid_key_missing_required": 123}

    docs, diag = build_retrieval_documents([valid_rec, malformed_item, corrupt_dict])

    assert len(docs) == 1
    assert docs[0].document_id == f"doc_{valid_rec.evidence_id}"
    assert len(diag["issues"]) >= 2


# ------------------------------------------------------------------
# 10. Research Errors Isolated from Documents
# ------------------------------------------------------------------

def test_research_errors_separate_from_documents():
    """In research node, failed tools log into research_errors and do not fabricate error documents."""
    state = {
        "idea": "online organic vegetable delivery",
        "keywords": ["organic", "vegetables"],
        "location": "Ahmedabad",
        "district": "Ahmedabad",
    }

    # Mock trends to fail while others succeed
    with patch("app.nodes.research.run_trends_search", side_effect=Exception("HTTP 429 Rate limit")):
        res = run_research(state)

        assert "retrieval_documents" in res
        assert "document_diagnostics" in res
        assert "research_errors" in res

        # Trends error is in research_errors
        trends_err = [e for e in res["research_errors"] if "Trends" in e.get("source", "")]
        assert len(trends_err) > 0

        # No document with error text exists in retrieval_documents
        for doc in res["retrieval_documents"]:
            assert "HTTP 429" not in doc["text"]
            assert "Rate limit" not in doc["text"]


# ------------------------------------------------------------------
# 11. Integration: run_research Produces Retrieval Documents
# ------------------------------------------------------------------

def test_integration_run_research_produces_retrieval_documents():
    """End-to-end integration: run_research produces raw, normalized, cleaned, and retrieval_documents."""
    state = {
        "idea": "online organic vegetable delivery for families in Ahmedabad",
        "keywords": ["organic vegetables", "grocery delivery"],
        "target_segment": "families",
        "location": "Ahmedabad",
        "district": "Ahmedabad",
        "research_type": "consumer",
    }

    mock_trends = [{
        "status": "success",
        "keyword": "organic vegetables",
        "geo": "IN-GJ",
        "latest_value": 52.0,
        "average_value": 44.5,
        "peak_value": 85.0,
        "trend_direction": "rising",
        "cache_hit": True,
        "cache_age_seconds": 120,
    }]

    with patch("app.nodes.research.run_trends_search", return_value=mock_trends):
        res = run_research(state)


    assert "normalized_evidence" in res
    assert "cleaned_evidence" in res
    assert "retrieval_documents" in res
    assert "document_diagnostics" in res

    docs = res["retrieval_documents"]
    assert len(docs) > 0

    sources_in_docs = {d["metadata"]["source"] for d in docs}
    # At least census and plfs are guaranteed present from local datasets
    assert "census" in sources_in_docs
    assert "plfs" in sources_in_docs

    # Check document IDs and text validity
    for d in docs:
        assert d["document_id"].startswith("doc_")
        assert len(d["text"]) > 20
        assert d["metadata"]["is_retrieval_ready"] is True
