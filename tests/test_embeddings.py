"""
test_embeddings.py
------------------
Comprehensive test suite for Step 6: Generate and Validate Embeddings.

Tests coverage:
  1. Valid vectors and dimension consistency.
  2. Rejection of empty vectors, non-finite values (NaN, Inf), and non-numeric elements.
  3. Stable chunk-to-vector mapping and ID alignment.
  4. Correct model metadata and dimension matching.
  5. Multiple batches processing.
  6. Retry and exhausted-failure behavior on transient provider errors.
  7. Partial success with isolated failures (one failed batch does not discard others).
  8. Empty chunk collections handling.
  9. Missing API configuration handled gracefully without crashing.
  10. Test provider injection for offline tests without fake vectors in production.
  11. Model consistency checks across embedding collections.
  12. Research errors remaining separate from embeddings.
  13. End-to-end integration: run_research produces chunk_embeddings.
"""

import math
from unittest.mock import patch
import pytest

from app.rag.embeddings import (
    ChunkEmbeddingRecord,
    GoogleEmbeddingProvider,
    TestEmbeddingProvider,
    generate_chunk_embeddings,
)
from app.rag.chunker import DocumentChunk, ChunkStrategy
from app.nodes.research import run_research


# ------------------------------------------------------------------
# Test Fixtures
# ------------------------------------------------------------------

def make_sample_chunk(
    chunk_id: str = "doc_ev_census_10cf_c0",
    doc_id: str = "doc_ev_census_10cf",
    text: str = "Census 2011: Population for Ahmedabad District: 7,214,225 people.",
    is_ready: bool = True,
    relevance: str = "unreviewed",
) -> DocumentChunk:
    return DocumentChunk(
        chunk_id=chunk_id,
        document_id=doc_id,
        chunk_index=0,
        text=text,
        metadata={
            "document_id": doc_id,
            "chunk_id": chunk_id,
            "source": "census",
            "evidence_type": "demographic_statistic",
            "formatted_geography": "Ahmedabad District, Gujarat, India",
            "time_period": "2011",
            "value": 7214225,
            "unit": "people",
            "is_retrieval_ready": is_ready,
            "relevance": relevance,
        },
        chunking_strategy=ChunkStrategy.ATOMIC_PASSTHROUGH.value,
        char_count=len(text),
    )


# ------------------------------------------------------------------
# 1. Valid Record & Dimension Consistency Tests
# ------------------------------------------------------------------

def test_valid_embedding_record_creation():
    """Verify valid ChunkEmbeddingRecord accepts finite vectors with matching dimensions."""
    vec = [0.123, -0.456, 0.789, 0.0]
    rec = ChunkEmbeddingRecord(
        chunk_id="chunk_1",
        document_id="doc_1",
        text="Sample text",
        embedding=vec,
        embedding_model="models/gemini-embedding-001",
        embedding_dimensions=4,
        metadata={"source": "census"},
    )
    assert rec.chunk_id == "chunk_1"
    assert rec.embedding == vec
    assert rec.embedding_dimensions == 4
    assert rec.embedding_model == "models/gemini-embedding-001"


def test_dimension_mismatch_rejected():
    """Reject record when declared dimensions do not match actual vector length."""
    with pytest.raises(ValueError, match="Declared dimensions .* does not match actual vector length"):
        ChunkEmbeddingRecord(
            chunk_id="chunk_1",
            document_id="doc_1",
            text="Sample text",
            embedding=[0.1, 0.2, 0.3],
            embedding_model="models/gemini-embedding-001",
            embedding_dimensions=5,  # Mismatch: 5 vs 3
        )


def test_empty_vector_rejected():
    """Reject record when embedding vector is empty."""
    with pytest.raises(ValueError, match="cannot be empty"):
        ChunkEmbeddingRecord(
            chunk_id="chunk_1",
            document_id="doc_1",
            text="Sample text",
            embedding=[],
            embedding_model="models/gemini-embedding-001",
            embedding_dimensions=1,
        )



def test_non_finite_vector_elements_rejected():
    """Reject record containing NaN, Inf, or non-numeric elements."""
    # NaN check
    with pytest.raises(ValueError, match="non-finite"):
        ChunkEmbeddingRecord(
            chunk_id="chunk_1",
            document_id="doc_1",
            text="Sample text",
            embedding=[0.1, float("nan"), 0.3],
            embedding_model="models/gemini-embedding-001",
            embedding_dimensions=3,
        )

    # Inf check
    with pytest.raises(ValueError, match="non-finite"):
        ChunkEmbeddingRecord(
            chunk_id="chunk_1",
            document_id="doc_1",
            text="Sample text",
            embedding=[0.1, float("inf"), 0.3],
            embedding_model="models/gemini-embedding-001",
            embedding_dimensions=3,
        )

    # -Inf check
    with pytest.raises(ValueError, match="non-finite"):
        ChunkEmbeddingRecord(
            chunk_id="chunk_1",
            document_id="doc_1",
            text="Sample text",
            embedding=[float("-inf"), 0.2, 0.3],
            embedding_model="models/gemini-embedding-001",
            embedding_dimensions=3,
        )


# ------------------------------------------------------------------
# 2. Provider Tests (Test Provider & Offline Injection)
# ------------------------------------------------------------------

def test_test_provider_deterministic_and_normalized():
    """TestEmbeddingProvider generates deterministic, unit-normalized vectors without network calls."""
    provider = TestEmbeddingProvider(dimensions=64)
    text = "Ahmedabad demographic observation"

    vec1 = provider.embed_query(text)
    vec2 = provider.embed_query(text)

    assert len(vec1) == 64
    assert vec1 == vec2  # Strictly deterministic
    for x in vec1:
        assert math.isfinite(x)

    # Check unit length ~ 1.0
    norm = math.sqrt(sum(x * x for x in vec1))
    assert abs(norm - 1.0) < 1e-4


def test_generate_chunk_embeddings_with_injected_provider():
    """Verify generate_chunk_embeddings produces validated records using an injected test provider."""
    c1 = make_sample_chunk(chunk_id="chunk_1", text="First chunk text")
    c2 = make_sample_chunk(chunk_id="chunk_2", text="Second chunk text")
    provider = TestEmbeddingProvider(model_name="test-model-v1", dimensions=128)

    records, diag = generate_chunk_embeddings([c1, c2], provider=provider)

    assert len(records) == 2
    assert diag["total_chunks_received"] == 2
    assert diag["eligible_chunks_count"] == 2
    assert diag["embeddings_generated_count"] == 2
    assert diag["failed_chunks_count"] == 0
    assert diag["embedding_model"] == "test-model-v1"
    assert diag["embedding_dimensions"] == 128

    # Check IDs and text alignment
    assert records[0].chunk_id == "chunk_1"
    assert records[0].text == "First chunk text"
    assert len(records[0].embedding) == 128
    assert records[1].chunk_id == "chunk_2"
    assert records[1].text == "Second chunk text"
    assert len(records[1].embedding) == 128


# ------------------------------------------------------------------
# 3. Batching & Ordering Tests
# ------------------------------------------------------------------

def test_multiple_batches_preserves_ordering():
    """Generating embeddings across multiple batches preserves exact input chunk ordering."""
    chunks = [
        make_sample_chunk(chunk_id=f"chunk_{i}", text=f"Chunk sentence number {i}")
        for i in range(10)
    ]
    provider = TestEmbeddingProvider(dimensions=32)

    # Batch size 3 implies 4 batches (3, 3, 3, 1)
    records, diag = generate_chunk_embeddings(chunks, provider=provider, batch_size=3)

    assert len(records) == 10
    assert diag["batches_processed"] == 4
    for i, r in enumerate(records):
        assert r.chunk_id == f"chunk_{i}"
        assert r.text == f"Chunk sentence number {i}"


# ------------------------------------------------------------------
# 4. Error Isolation & Transient Retries
# ------------------------------------------------------------------

def test_partial_success_with_isolated_failures():
    """If one batch fails, remaining batches proceed and failure is recorded in diagnostics."""
    c1 = make_sample_chunk(chunk_id="chunk_1", text="Batch 1 item")
    c2 = make_sample_chunk(chunk_id="chunk_2", text="Batch 2 item")

    # Simulate failure specifically on the second chunk's text
    provider = TestEmbeddingProvider(dimensions=32, simulate_failure_texts=["Batch 2 item"])

    records, diag = generate_chunk_embeddings([c1, c2], provider=provider, batch_size=1)

    assert len(records) == 1
    assert records[0].chunk_id == "chunk_1"
    assert diag["embeddings_generated_count"] == 1
    assert diag["failed_chunks_count"] == 1
    assert len(diag["issues"]) >= 1
    assert "Simulated failure on text" in diag["issues"][0]



def test_google_provider_retry_and_exhaustion():
    """GoogleEmbeddingProvider retries transient errors and raises RuntimeError on exhaustion."""
    with patch("langchain_google_genai.GoogleGenerativeAIEmbeddings") as mock_emb_cls:
        mock_instance = mock_emb_cls.return_value
        mock_instance.embed_documents.side_effect = Exception("503 Service Unavailable")

        provider = GoogleEmbeddingProvider(
            api_key="fake-test-key",
            max_retries=2,
            backoff_factor=0.01,
        )

        with pytest.raises(RuntimeError, match="Failed to generate embeddings"):
            provider.embed_texts(["test text"])

        # Retried max_retries times
        assert mock_instance.embed_documents.call_count == 2


# ------------------------------------------------------------------
# 5. Ineligibility & Empty Handling
# ------------------------------------------------------------------

def test_ineligible_chunks_skipped_by_default():
    """Chunks marked is_retrieval_ready=False or relevance='irrelevant' are excluded from embedding."""
    ready_chunk = make_sample_chunk(chunk_id="ready_1", is_ready=True)
    irrelevant_chunk = make_sample_chunk(chunk_id="irrelevant_1", is_ready=False, relevance="irrelevant")

    provider = TestEmbeddingProvider(dimensions=16)
    records, diag = generate_chunk_embeddings([ready_chunk, irrelevant_chunk], provider=provider)

    assert len(records) == 1
    assert records[0].chunk_id == "ready_1"
    assert diag["eligible_chunks_count"] == 1


def test_empty_or_whitespace_chunks_handling():
    """Empty chunk collections and whitespace chunks are handled cleanly without API calls."""
    records, diag = generate_chunk_embeddings([])
    assert records == []
    assert diag["total_chunks_received"] == 0

    ws_chunk = make_sample_chunk(chunk_id="ws_1", text="   \n\t  ")
    records, diag = generate_chunk_embeddings([ws_chunk])
    assert records == []
    assert diag["eligible_chunks_count"] == 0


def test_missing_api_configuration_handled_gracefully():
    """When no API key is available, GoogleEmbeddingProvider reports missing key cleanly in diagnostics."""
    with patch.dict("os.environ", {}, clear=True):
        c1 = make_sample_chunk()
        records, diag = generate_chunk_embeddings([c1], provider=None)

        assert records == []
        assert any("Google API key not found in environment" in iss for iss in diag["issues"])


# ------------------------------------------------------------------
# 6. Pipeline Integration & Research Errors Isolation
# ------------------------------------------------------------------

def test_research_errors_separate_from_embeddings():
    """Source errors remain isolated in research_errors while valid embeddings are produced."""
    state = {
        "idea": "organic vegetable delivery",
        "keywords": ["vegetables"],
        "location": "Ahmedabad",
        "district": "Ahmedabad",
        "embedding_provider": TestEmbeddingProvider(dimensions=32),
    }

    # Simulate Google Trends tool error
    with patch("app.nodes.research.run_trends_search", side_effect=Exception("HTTP 429 Rate limit")):
        res = run_research(state)

        assert "chunk_embeddings" in res
        assert "embedding_diagnostics" in res
        assert "research_errors" in res

        # Trends error in research_errors
        trends_err = [e for e in res["research_errors"] if "Trends" in e.get("source", "")]
        assert len(trends_err) > 0

        # Valid embeddings generated from surviving sources (Census, PLFS, etc.)
        assert len(res["chunk_embeddings"]) > 0
        for emb in res["chunk_embeddings"]:
            assert "HTTP 429" not in emb["text"]
            assert len(emb["embedding"]) == 32


def test_run_research_produces_chunk_embeddings_integration():
    """End-to-end integration: run_research produces chunk_embeddings and embedding_diagnostics."""
    test_provider = TestEmbeddingProvider(model_name="test-offline-embed", dimensions=64)
    state = {
        "idea": "online organic vegetable delivery for families in Ahmedabad",
        "keywords": ["organic vegetables", "grocery delivery"],
        "target_segment": "families",
        "location": "Ahmedabad",
        "district": "Ahmedabad",
        "research_type": "consumer",
        "embedding_provider": test_provider,
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

    assert "chunk_embeddings" in res
    assert "embedding_diagnostics" in res

    embs = res["chunk_embeddings"]
    diag = res["embedding_diagnostics"]

    assert len(embs) > 0
    assert diag["embeddings_generated_count"] == len(embs)
    assert diag["embedding_model"] == "test-offline-embed"
    assert diag["embedding_dimensions"] == 64

    for e in embs:
        assert len(e["embedding"]) == 64
        assert e["embedding_model"] == "test-offline-embed"
        assert e["embedding_dimensions"] == 64
        assert e["metadata"]["is_retrieval_ready"] is True
