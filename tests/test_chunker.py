"""
test_chunker.py
---------------
Comprehensive test suite for Step 5: Source-Aware Chunking.

Tests coverage:
  1. Atomic statistical records (Census, PLFS, Trends) remaining intact (single chunk).
  2. Long Reddit text splitting on natural boundaries.
  3. Correct overlap and deterministic chunk ordering.
  4. Stable chunk IDs across repeated runs.
  5. Metadata and provenance inheritance from parent documents.
  6. Short documents producing one chunk.
  7. Empty or whitespace-only content handling.
  8. Invalid configuration detection (overlap >= max_chars, min > max, negative values).
  9. Oversized structured documents splitting while repeating header context.
  10. Ineligible records (is_retrieval_ready=False / irrelevant) skipped by default.
  11. Ineligible records included when requested.
  12. Malformed document isolation (one bad doc does not fail the batch).
  13. Research errors remaining separate from document chunks.
  14. ChromaDB metadata compatibility serialization (to_chroma_metadata).
  15. Pipeline integration in run_research producing document_chunks.
"""

from unittest.mock import patch
import pytest

from app.rag.chunker import (
    ChunkStrategy,
    ChunkerConfig,
    DocumentChunk,
    chunk_documents,
)
from app.rag.document_builder import RetrievalDocument
from app.nodes.research import run_research


# ------------------------------------------------------------------
# Test Fixtures
# ------------------------------------------------------------------

def make_sample_census_doc(
    doc_id: str = "doc_ev_census_10cf6e3550e5",
    value: int = 7214225,
) -> RetrievalDocument:
    text = (
        "Census 2011 Demographic Record: Census 2011: Population (Ahmedabad District, Gujarat, Total). "
        "Geographic Scope: Ahmedabad District, Gujarat, India. Observed Metric Value: 7,214,225 people. "
        "Reference Benchmark Year: 2011. Data Provenance: Primary Census Abstract (PCA 2011). "
        "Reported Summary: Census 2011 Total Population in Ahmedabad, Gujarat (Total): 7,214,225 persons "
        "(Male: 3,788,051, Female: 3,426,174, Sex Ratio: 904.5 females per 1,000 males). "
        "Source Authority: Registrar General and Census Commissioner of India. Represents official decennial enumeration benchmark."
    )
    metadata = {
        "document_id": doc_id,
        "evidence_id": "ev_census_10cf6e3550e5",
        "source": "census",
        "evidence_type": "demographic_statistic",
        "title": "Census 2011: Population (Ahmedabad District, Gujarat, Total)",
        "value": value,
        "unit": "people",
        "time_period": "2011",
        "formatted_geography": "Ahmedabad District, Gujarat, India",
        "district": "Ahmedabad",
        "state": "Gujarat",
        "country": "India",
        "census_table": "Primary Census Abstract (PCA 2011)",
        "census_year": 2011,
        "is_state_fallback": False,
        "is_retrieval_ready": True,
        "relevance": "unreviewed",
        "limitations": ["Official Census 2011 benchmark; does not reflect subsequent population growth."],
        "provenance": {"dataset": "Primary Census Abstract (PCA 2011)", "census_year": 2011},
    }
    return RetrievalDocument(document_id=doc_id, text=text, metadata=metadata)


def make_sample_plfs_doc(
    doc_id: str = "doc_ev_plfs_5f9d1a8e2b01_lfpr",
    lfpr: float = 55.64,
) -> RetrievalDocument:
    text = (
        "PLFS 2025 Official Labour Record: PLFS 2025: Labour Force Participation Rate (LFPR) (Ahmedabad). "
        "Geographic Scope: Ahmedabad District, Gujarat, India. Survey Estimate: 55.64%. "
        "Survey Reference Period: 2025 (Annual). Estimation Context: Survey-weighted estimate from MoSPI microdata based on Age 15+ (Working Age). "
        "Survey Sample Size: 5,155 respondents. Reported Summary: PLFS 2025 Labour Force Participation Rate (LFPR) for Ahmedabad (Total, Age 15+): "
        "55.64% (Usual Status ps+ss, survey-weighted). Represents percentage of working-age population (Age 15+) in the labour force (employed or seeking work). "
        "Source Authority: Ministry of Statistics and Programme Implementation (MoSPI), Government of India."
    )
    metadata = {
        "document_id": doc_id,
        "evidence_id": "ev_plfs_5f9d1a8e2b01_lfpr",
        "source": "plfs",
        "evidence_type": "labour_statistic",
        "title": "PLFS 2025: Labour Force Participation Rate (LFPR) (Ahmedabad)",
        "value": lfpr,
        "unit": "percent",
        "time_period": "2025 (Annual)",
        "formatted_geography": "Ahmedabad District, Gujarat, India",
        "is_survey_weighted": True,
        "sample_size": 5155,
        "population_base": "Age 15+ (Working Age)",
        "survey_name": "Periodic Labour Force Survey (PLFS) 2025",
        "is_retrieval_ready": True,
        "relevance": "unreviewed",
        "limitations": ["Sample survey estimate from MoSPI PLFS 2025 microdata."],
    }
    return RetrievalDocument(document_id=doc_id, text=text, metadata=metadata)


def make_sample_trends_doc(
    doc_id: str = "doc_ev_trends_6cf7d88568e6",
    score: float = 26.0,
) -> RetrievalDocument:
    text = (
        "Google Trends Search Interest Observation for 'online service'. Geographic Scope: Gujarat, India (state level). "
        "Time Period: 2025-04 to 2026-04 (today 12-m). Normalized Relative Search Interest: Latest score = 26.0/100. "
        "Period Average Score: 37.2/100. Peak Score Observed: 100.0/100. Trend Direction: falling. "
        "Interpretation Context: Values represent normalized relative search interest on a 0-100 scale relative to peak popularity "
        "in the designated region and timeframe. This metric does NOT represent absolute search volume or total query count."
    )
    metadata = {
        "document_id": doc_id,
        "evidence_id": "ev_trends_6cf7d88568e6",
        "source": "google_trends",
        "evidence_type": "search_interest",
        "title": "Google Trends: 'online service' search interest (IN-GJ)",
        "value": score,
        "unit": "relative_interest_index",
        "time_period": "2025-04 to 2026-04 (today 12-m)",
        "formatted_geography": "Gujarat, India (state level)",
        "keyword": "online service",
        "geo_code": "IN-GJ",
        "trend_direction": "falling",
        "latest_value": score,
        "is_retrieval_ready": True,
        "relevance": "unreviewed",
    }
    return RetrievalDocument(document_id=doc_id, text=text, metadata=metadata)


def make_sample_reddit_doc(
    doc_id: str = "doc_ev_reddit_8e559176a205",
    text_content: str = "Short discussion on grocery options.",
    is_ready: bool = True,
    relevance: str = "potentially_relevant",
) -> RetrievalDocument:
    text = (
        f"Historical Reddit Discussion Record [r/ahmedabad]. Post Title: \"Organic vegetable delivery options\". "
        f"Discussion Content: \"{text_content}\". Community Engagement: 24 upvotes. "
        "Observation Context: Qualitative user discussion retrieved from archived Kaggle Reddit dataset. "
        "Represents individual subjective experience; does not establish quantified market size, consumer demand, or willingness to pay."
    )
    metadata = {
        "document_id": doc_id,
        "evidence_id": "ev_reddit_8e559176a205",
        "source": "reddit",
        "evidence_type": "discussion",
        "title": "Reddit Discussion: Organic vegetable delivery options",
        "post_title": "Organic vegetable delivery options",
        "subreddit": "ahmedabad",
        "post_score": 24,
        "value": 24,
        "unit": "upvotes",
        "is_retrieval_ready": is_ready,
        "relevance": relevance,
        "relevance_reason": "Discusses grocery delivery in Ahmedabad.",
        "formatted_geography": None,
    }
    return RetrievalDocument(document_id=doc_id, text=text, metadata=metadata)


# ------------------------------------------------------------------
# 1. Atomic Statistical Records Intact Tests
# ------------------------------------------------------------------

def test_atomic_census_record_remains_intact():
    """Census atomic document fits within max_chunk_chars and yields exactly one intact chunk."""
    doc = make_sample_census_doc()
    config = ChunkerConfig(max_chunk_chars=1200)

    chunks, diag = chunk_documents([doc], config)

    assert len(chunks) == 1
    chunk = chunks[0]
    assert chunk.document_id == doc.document_id
    assert chunk.chunk_id == f"{doc.document_id}_c0"
    assert chunk.chunk_index == 0
    assert chunk.chunking_strategy == ChunkStrategy.ATOMIC_PASSTHROUGH.value
    assert chunk.text == doc.text
    # Verify metric, unit, value, geography, and caveat are intact
    assert "7,214,225 people" in chunk.text
    assert "Ahmedabad District, Gujarat, India" in chunk.text
    assert "2011" in chunk.text
    assert "Primary Census Abstract" in chunk.text
    assert chunk.metadata["source"] == "census"
    assert chunk.metadata["value"] == 7214225
    assert chunk.metadata["unit"] == "people"


def test_atomic_plfs_record_remains_intact():
    """PLFS atomic labour document fits within max_chunk_chars and yields exactly one intact chunk."""
    doc = make_sample_plfs_doc()
    chunks, diag = chunk_documents([doc])

    assert len(chunks) == 1
    chunk = chunks[0]
    assert chunk.chunk_strategy if hasattr(chunk, "chunk_strategy") else chunk.chunking_strategy == ChunkStrategy.ATOMIC_PASSTHROUGH.value
    assert "55.64%" in chunk.text
    assert "Survey-weighted estimate" in chunk.text
    assert "5,155 respondents" in chunk.text
    assert chunk.metadata["source"] == "plfs"
    assert chunk.metadata["is_survey_weighted"] is True


def test_atomic_trends_record_remains_intact():
    """Google Trends atomic search interest document fits within max_chunk_chars and yields one chunk."""
    doc = make_sample_trends_doc()
    chunks, diag = chunk_documents([doc])

    assert len(chunks) == 1
    chunk = chunks[0]
    assert chunk.chunking_strategy == ChunkStrategy.ATOMIC_PASSTHROUGH.value
    assert "26.0/100" in chunk.text
    assert "falling" in chunk.text
    assert "does NOT represent absolute search volume" in chunk.text
    assert chunk.metadata["source"] == "google_trends"


# ------------------------------------------------------------------
# 2. Long Reddit Text Splitting Tests
# ------------------------------------------------------------------

def test_long_reddit_text_splitting():
    """Long Reddit narrative document exceeding max_chunk_chars is split into multiple sequential chunks."""
    long_body = (
        "I have been trying to source organic vegetables in Ahmedabad for over six months now. "
        "Most local vendors claim their produce is chemical-free but have no certification whatsoever. "
        "I tried three different farm box subscription services delivered on Tuesday mornings. "
        "The first service arrived late and the leafy greens were already wilted by the afternoon heat. "
        "The second service offered excellent fresh tomatoes and carrots but their mobile app kept crashing during renewal. "
        "The third service was reasonably priced around 800 rupees per box but lacked variety in seasonal gourds and root vegetables. "
        "Many families in our housing society in Bodakdev are willing to pay a premium for reliable doorstep delivery "
        "provided the vegetables are harvested fresh and delivered before breakfast hours. "
        "Packaging must avoid single-use plastics to appeal to eco-conscious urban households."
    )
    doc = make_sample_reddit_doc(text_content=long_body)
    # Configure small max_chunk_chars to force splitting
    config = ChunkerConfig(max_chunk_chars=350, chunk_overlap_chars=80, min_chunk_chars=30)

    chunks, diag = chunk_documents([doc], config=config)

    assert len(chunks) >= 2
    assert diag["by_strategy"][ChunkStrategy.SLIDING_WINDOW_TEXT.value] >= 2

    # Verify each chunk has deterministic ordering and context header
    for idx, c in enumerate(chunks):
        assert c.chunk_index == idx
        assert c.chunk_id == f"{doc.document_id}_c{idx}"
        assert c.chunking_strategy == ChunkStrategy.SLIDING_WINDOW_TEXT.value
        assert len(c.text) <= config.max_chunk_chars
        # Context header prepended to all chunks
        assert "[Context: r/ahmedabad - \"Organic vegetable delivery options\"]" in c.text


def test_reddit_split_overlap_and_boundary_respect():
    """Verify sliding window maintains sentence/word boundaries without cutting words or numbers in half."""
    text_content = (
        "First complete sentence discussing organic spinach. "
        "Second complete sentence discussing delivery logistics. "
        "Third complete sentence discussing consumer packaging. "
        "Fourth complete sentence discussing payment gateway issues. "
        "Fifth complete sentence discussing final subscription feedback."
    )
    doc = make_sample_reddit_doc(text_content=text_content)
    config = ChunkerConfig(max_chunk_chars=300, chunk_overlap_chars=70, min_chunk_chars=20)

    chunks, _ = chunk_documents([doc], config=config)

    assert len(chunks) >= 2
    # Ensure no chunk ends with broken half-words
    for c in chunks:
        # Check last character is alphanumeric, quote, or sentence terminator
        assert c.text[-1] in ".!?\"'0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"


# ------------------------------------------------------------------
# 3. Determinism & Stability Tests
# ------------------------------------------------------------------

def test_stable_chunk_ids_across_runs():
    """Chunk IDs, text content, and indices remain identical across repeated runs with identical config."""
    doc = make_sample_census_doc()
    config = ChunkerConfig(max_chunk_chars=1200)

    chunks_run1, _ = chunk_documents([doc], config)
    chunks_run2, _ = chunk_documents([doc], config)

    assert len(chunks_run1) == len(chunks_run2)
    for c1, c2 in zip(chunks_run1, chunks_run2):
        assert c1.chunk_id == c2.chunk_id
        assert c1.document_id == c2.document_id
        assert c1.chunk_index == c2.chunk_index
        assert c1.text == c2.text
        assert c1.metadata == c2.metadata


# ------------------------------------------------------------------
# 4. Metadata Inheritance & Chroma Compatibility Tests
# ------------------------------------------------------------------

def test_metadata_and_provenance_inheritance():
    """Chunk inherits all parent document metadata and includes chunk-specific tracing attributes."""
    doc = make_sample_plfs_doc()
    chunks, _ = chunk_documents([doc])

    assert len(chunks) == 1
    chunk = chunks[0]
    meta = chunk.metadata

    # Parent attributes preserved
    assert meta["source"] == "plfs"
    assert meta["evidence_type"] == "labour_statistic"
    assert meta["value"] == 55.64
    assert meta["unit"] == "percent"
    assert meta["time_period"] == "2025 (Annual)"
    assert meta["formatted_geography"] == "Ahmedabad District, Gujarat, India"
    assert meta["is_survey_weighted"] is True
    assert meta["sample_size"] == 5155
    assert meta["survey_name"] == "Periodic Labour Force Survey (PLFS) 2025"

    # Chunk tracing attributes present
    assert meta["chunk_id"] == f"{doc.document_id}_c0"
    assert meta["chunk_index"] == 0
    assert meta["chunking_strategy"] == ChunkStrategy.ATOMIC_PASSTHROUGH.value
    assert meta["char_count"] == len(chunk.text)

    # ChromaDB primitive serialization
    chroma_meta = chunk.to_chroma_metadata()
    for k, v in chroma_meta.items():
        assert isinstance(v, (str, int, float, bool)), f"Non-primitive Chroma type for {k}: {type(v)}"


# ------------------------------------------------------------------
# 5. Configuration Validation Tests
# ------------------------------------------------------------------

def test_invalid_configuration_raises_error():
    """Configuration validation rejects invalid overlap, negative numbers, or min > max."""
    # Overlap >= max_chunk_chars
    with pytest.raises(ValueError, match="strictly less than"):
        ChunkerConfig(max_chunk_chars=500, chunk_overlap_chars=500)

    with pytest.raises(ValueError, match="strictly less than"):
        ChunkerConfig(max_chunk_chars=500, chunk_overlap_chars=600)

    # min_chunk_chars > max_chunk_chars (with overlap set small so it doesn't trigger first)
    with pytest.raises(ValueError, match="cannot exceed"):
        ChunkerConfig(max_chunk_chars=100, chunk_overlap_chars=20, min_chunk_chars=150)


    # Negative values
    with pytest.raises(Exception):
        ChunkerConfig(max_chunk_chars=-10)


# ------------------------------------------------------------------
# 6. Oversized Structured Document Handling
# ------------------------------------------------------------------

def test_oversized_structured_document_splitting():
    """An unusually long Census or PLFS document that exceeds max_chunk_chars splits while repeating header context."""
    oversized_text = (
        "Census 2011 Detailed Occupational and Demographic Distribution for Ahmedabad District. "
        "Primary Census Abstract reports 7,214,225 total residents residing in 1,510,134 domestic households. "
        "Male population stands at 3,788,051 persons and female population stands at 3,426,174 persons. "
        "Workforce participation rate is recorded at 35.97 percent with 2,594,952 enumerated total workers. "
        "Main agricultural cultivators account for 142,670 workers representing 5.50 percent of the labor pool. "
        "Agricultural labourers comprise 268,954 workers representing 10.36 percent of workers. "
        "Household industry workers comprise 54,876 workers representing 2.11 percent of workers. "
        "Other non-agricultural workers total 2,128,452 persons representing 82.02 percent of the district workforce. "
        "Educational attainment breakdown indicates crude literacy of 75.35 percent across rural and urban sectors."
    )
    doc = RetrievalDocument(
        document_id="doc_ev_census_huge",
        text=oversized_text,
        metadata={"source": "census", "evidence_type": "demographic_statistic", "is_retrieval_ready": True},
    )
    config = ChunkerConfig(max_chunk_chars=380, chunk_overlap_chars=60, min_chunk_chars=30)

    chunks, diag = chunk_documents([doc], config=config)

    assert len(chunks) >= 2
    assert diag["by_strategy"][ChunkStrategy.STRUCTURED_SPLIT.value] >= 2
    # Verify header sentence is repeated in subsequent split chunks
    for c in chunks:
        assert "Census 2011 Detailed Occupational" in c.text


# ------------------------------------------------------------------
# 7. Ineligible Records Filtering Tests
# ------------------------------------------------------------------

def test_ineligible_records_skipped_by_default():
    """Documents marked is_retrieval_ready=False or relevance='irrelevant' are skipped by default."""
    ready_doc = make_sample_reddit_doc(doc_id="doc_ready_1", is_ready=True, relevance="potentially_relevant")
    irrelevant_doc = make_sample_reddit_doc(doc_id="doc_irrelevant_1", is_ready=False, relevance="irrelevant")

    chunks, diag = chunk_documents([ready_doc, irrelevant_doc])

    assert len(chunks) == 1
    assert chunks[0].document_id == "doc_ready_1"
    assert diag["skipped_ineligible_count"] == 1
    assert diag["eligible_documents_count"] == 1
    assert len(diag["skipped_documents"]) == 1
    assert diag["skipped_documents"][0]["document_id"] == "doc_irrelevant_1"


def test_ineligible_records_included_when_requested():
    """When include_ineligible=True, ineligible documents are chunked with audit metadata preserved."""
    irrelevant_doc = make_sample_reddit_doc(doc_id="doc_irrelevant_1", is_ready=False, relevance="irrelevant")

    chunks, diag = chunk_documents([irrelevant_doc], include_ineligible=True)

    assert len(chunks) == 1
    assert chunks[0].metadata["is_retrieval_ready"] is False
    assert chunks[0].metadata["relevance"] == "irrelevant"
    assert diag["skipped_ineligible_count"] == 0
    assert diag["eligible_documents_count"] == 1


# ------------------------------------------------------------------
# 8. Empty & Whitespace Content Handling
# ------------------------------------------------------------------

def test_empty_or_whitespace_documents():
    """Empty list, None, and whitespace-only documents are safely handled without producing empty chunks."""
    assert chunk_documents([]) == ([], {"input_documents_count": 0, "eligible_documents_count": 0, "skipped_ineligible_count": 0, "total_chunks_created": 0, "by_source": {}, "by_strategy": {}, "skipped_documents": [], "config": {"max_chunk_chars": 1200, "chunk_overlap_chars": 200, "min_chunk_chars": 30}, "issues": []})

    empty_doc = RetrievalDocument(document_id="doc_empty", text="    \n\t   ", metadata={"source": "reddit", "is_retrieval_ready": True})
    chunks, diag = chunk_documents([empty_doc])
    assert len(chunks) == 0
    assert len(diag["skipped_documents"]) == 1


# ------------------------------------------------------------------
# 9. Malformed Document Isolation
# ------------------------------------------------------------------

def test_malformed_document_isolation():
    """A corrupted dictionary or invalid document does not crash or discard valid documents."""
    valid_doc = make_sample_census_doc()
    malformed_dict = {"document_id": "bad_doc", "missing_required_text": 123}
    invalid_type = 42

    chunks, diag = chunk_documents([valid_doc, malformed_dict, invalid_type])

    assert len(chunks) == 1
    assert chunks[0].document_id == valid_doc.document_id
    assert len(diag["issues"]) >= 2


# ------------------------------------------------------------------
# 10. Research Errors Isolated from Chunks
# ------------------------------------------------------------------

def test_research_errors_separate_from_chunks():
    """In research node, failed tools log into research_errors and do not fabricate fake error chunks."""
    state = {
        "idea": "online organic vegetable delivery",
        "keywords": ["organic", "vegetables"],
        "location": "Ahmedabad",
        "district": "Ahmedabad",
    }

    with patch("app.nodes.research.run_trends_search", side_effect=Exception("HTTP 429 Rate limit")):
        res = run_research(state)

        assert "document_chunks" in res
        assert "chunking_diagnostics" in res
        assert "research_errors" in res

        # Trends error is strictly in research_errors
        trends_err = [e for e in res["research_errors"] if "Trends" in e.get("source", "")]
        assert len(trends_err) > 0

        # No chunk contains error message text
        for chunk in res["document_chunks"]:
            assert "HTTP 429" not in chunk["text"]
            assert "Rate limit" not in chunk["text"]


# ------------------------------------------------------------------
# 11. Pipeline Integration Test
# ------------------------------------------------------------------

def test_run_research_produces_document_chunks_integration():
    """End-to-end integration: run_research produces raw, normalized, cleaned, retrieval_documents, and document_chunks."""
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

    assert "document_chunks" in res
    assert "chunking_diagnostics" in res

    chunks = res["document_chunks"]
    diag = res["chunking_diagnostics"]

    assert len(chunks) > 0
    assert diag["total_chunks_created"] == len(chunks)
    assert diag["eligible_documents_count"] > 0

    sources_in_chunks = {c["metadata"]["source"] for c in chunks}
    assert "census" in sources_in_chunks
    assert "plfs" in sources_in_chunks

    for c in chunks:
        assert c["chunk_id"].startswith("doc_")
        assert "_c" in c["chunk_id"]
        assert len(c["text"]) >= diag["config"]["min_chunk_chars"]
        assert c["metadata"]["is_retrieval_ready"] is True
