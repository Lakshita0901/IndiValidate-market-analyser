"""
tests/test_retriever.py
-----------------------
Unit and integration tests for semantic evidence retrieval and context construction (Step 8).

Verifies:
1. Retrieval from persistent ChromaDB collection.
2. Query embedding and model compatibility.
3. Dimension mismatch handling.
4. Empty collection and empty-result handling.
5. top_k behavior.
6. Source and geography metadata filtering.
7. Evidence metadata and provenance preservation.
8. Correct interpretation of retrieval distance.
9. Context construction and size limits.
10. Context duplicate-chunk handling.
11. Missing credentials or provider failures.
12. Deterministic retrieval with injected test embeddings.
13. No unintended writes to the production ChromaDB collection.
14. Persistence across disk reopen.
"""

import os
from pathlib import Path
import pytest

from app.rag.embeddings import (
    ChunkEmbeddingRecord,
    TestEmbeddingProvider,
)
from app.rag.vector_store import ChromaVectorStore
from app.rag.retriever import (
    EvidenceRetriever,
    RetrievalFilter,
    RetrievalResult,
    RetrievedChunk,
    build_evidence_context,
    retrieve_evidence,
)


# ------------------------------------------------------------------
# Test Helpers
# ------------------------------------------------------------------

def make_test_record(
    chunk_id: str,
    text: str,
    source: str = "census_2011",
    model: str = "test-model-v1",
    dimensions: int = 64,
    state: str = "Gujarat",
    district: str = "Ahmedabad",
    evidence_type: str = "statistical_observation",
) -> ChunkEmbeddingRecord:
    """Helper to create a deterministic embedding record for testing retrieval."""
    provider = TestEmbeddingProvider(model_name=model, dimensions=dimensions)
    vec = provider.embed_query(text)
    meta = {
        "source": source,
        "evidence_type": evidence_type,
        "geography": {"state": state, "district": district, "level": "district"},
        "time_period": "2011-2025",
        "provenance": {"dataset": f"{source}_sample", "record_id": chunk_id},
        "limitations": [f"Benchmark survey caveat for {source}"],
        "is_retrieval_ready": True,
    }
    return ChunkEmbeddingRecord(
        chunk_id=chunk_id,
        document_id=f"doc_{chunk_id}",
        text=text,
        embedding=vec,
        embedding_model=model,
        embedding_dimensions=dimensions,
        metadata=meta,
    )


# ------------------------------------------------------------------
# 1. Retrieval from Persistent Collection
# ------------------------------------------------------------------

def test_retrieval_from_persistent_collection(tmp_path):
    """Verify retriever can query an indexed persistent collection and return ranked chunks."""
    store = ChromaVectorStore(persist_directory=tmp_path / "chroma", collection_name="test_retrieval")
    provider = TestEmbeddingProvider(model_name="test-model-v1", dimensions=64)

    r1 = make_test_record("c1", "Ahmedabad factory worker employment statistics", source="census_2011")
    r2 = make_test_record("c2", "Consumer demand for electric vehicles in Pune", source="reddit", state="Maharashtra", district="Pune")
    store.store_embeddings([r1, r2])

    retriever = EvidenceRetriever(vector_store=store, provider=provider)
    result = retriever.retrieve("factory worker employment", top_k=2)

    assert isinstance(result, RetrievalResult)
    assert result.total_retrieved == 2
    assert len(result.chunks) == 2
    assert result.collection_name == "test_retrieval"
    assert result.embedding_model == "test-model-v1"
    assert result.embedding_dimensions == 64

    # Distance must be non-negative
    for c in result.chunks:
        assert isinstance(c, RetrievedChunk)
        assert c.distance >= 0.0
        assert c.text in ["Ahmedabad factory worker employment statistics", "Consumer demand for electric vehicles in Pune"]


# ------------------------------------------------------------------
# 2. Model Compatibility Enforcement
# ------------------------------------------------------------------

def test_model_compatibility_enforcement(tmp_path):
    """Querying with a model different from the collection's model raises ValueError."""
    store = ChromaVectorStore(persist_directory=tmp_path / "chroma", collection_name="model_col")
    provider_a = TestEmbeddingProvider(model_name="test-model-v1", dimensions=64)
    r1 = make_test_record("c1", "Sample text", model="test-model-v1", dimensions=64)
    store.store_embeddings([r1])

    # Query with provider configured for a different model
    provider_b = TestEmbeddingProvider(model_name="other-model-v2", dimensions=64)
    retriever = EvidenceRetriever(vector_store=store, provider=provider_b)

    with pytest.raises(ValueError, match="Embedding model mismatch"):
        retriever.retrieve("sample query")


# ------------------------------------------------------------------
# 3. Dimension Mismatch Handling
# ------------------------------------------------------------------

def test_dimension_mismatch_handling(tmp_path):
    """Querying with an embedding dimension that does not match collection raises ValueError."""
    store = ChromaVectorStore(persist_directory=tmp_path / "chroma", collection_name="dim_col")
    provider_64 = TestEmbeddingProvider(model_name="test-model-v1", dimensions=64)
    r1 = make_test_record("c1", "Sample text", model="test-model-v1", dimensions=64)
    store.store_embeddings([r1])

    # Attempt to query with 128 dimensions
    provider_128 = TestEmbeddingProvider(model_name="test-model-v1", dimensions=128)
    retriever = EvidenceRetriever(vector_store=store, provider=provider_128)

    with pytest.raises(ValueError, match="Dimension mismatch"):
        retriever.retrieve("sample query")


# ------------------------------------------------------------------
# 4. Empty Collection & Empty Result Handling
# ------------------------------------------------------------------

def test_empty_collection_and_empty_result(tmp_path):
    """Retrieval on an empty collection or un-matched filter returns 0 chunks cleanly."""
    store = ChromaVectorStore(persist_directory=tmp_path / "chroma", collection_name="empty_col")
    provider = TestEmbeddingProvider(model_name="test-model-v1", dimensions=64)
    retriever = EvidenceRetriever(vector_store=store, provider=provider)

    # Empty collection query
    res = retriever.retrieve("any query", top_k=5)
    assert res.total_retrieved == 0
    assert res.chunks == []

    # Non-empty collection, but non-matching filter
    r1 = make_test_record("c1", "Ahmedabad labour observation", state="Gujarat")
    store.store_embeddings([r1])

    res_filtered = retriever.retrieve(
        "labour",
        top_k=5,
        filters=RetrievalFilter(state="NonExistentState"),
    )
    assert res_filtered.total_retrieved == 0
    assert res_filtered.chunks == []


# ------------------------------------------------------------------
# 5. top_k Behavior
# ------------------------------------------------------------------

def test_top_k_behavior(tmp_path):
    """The number of returned chunks strictly honors the top_k parameter."""
    store = ChromaVectorStore(persist_directory=tmp_path / "chroma", collection_name="topk_col")
    provider = TestEmbeddingProvider(model_name="test-model-v1", dimensions=64)

    records = [
        make_test_record(f"c_{i}", f"Market observation chunk number {i}")
        for i in range(10)
    ]
    store.store_embeddings(records)

    retriever = EvidenceRetriever(vector_store=store, provider=provider)

    res_3 = retriever.retrieve("market observation", top_k=3)
    assert len(res_3.chunks) == 3

    res_7 = retriever.retrieve("market observation", top_k=7)
    assert len(res_7.chunks) == 7

    res_all = retriever.retrieve("market observation", top_k=20)
    assert len(res_all.chunks) == 10  # Maximum available in collection


# ------------------------------------------------------------------
# 6. Source and Geography Metadata Filtering
# ------------------------------------------------------------------

def test_source_and_geography_filtering(tmp_path):
    """Metadata filters properly restrict retrieved records to matching criteria."""
    store = ChromaVectorStore(persist_directory=tmp_path / "chroma", collection_name="filter_col")
    provider = TestEmbeddingProvider(model_name="test-model-v1", dimensions=64)

    r_census_gj = make_test_record("c_cen_gj", "Census literacy in Gujarat", source="census_2011", state="Gujarat")
    r_plfs_gj = make_test_record("c_plfs_gj", "PLFS salary in Gujarat", source="plfs_2025", state="Gujarat")
    r_plfs_mh = make_test_record("c_plfs_mh", "PLFS salary in Maharashtra", source="plfs_2025", state="Maharashtra")
    r_reddit = make_test_record("c_red", "Reddit discussion about jobs", source="reddit", state="Delhi")

    store.store_embeddings([r_census_gj, r_plfs_gj, r_plfs_mh, r_reddit])
    retriever = EvidenceRetriever(vector_store=store, provider=provider)

    # 1. Source filter
    res_source = retriever.retrieve("data", top_k=5, filters=RetrievalFilter(source="census_2011"))
    assert res_source.total_retrieved == 1
    assert res_source.chunks[0].chunk_id == "c_cen_gj"

    # 2. State filter
    res_state = retriever.retrieve("data", top_k=5, filters=RetrievalFilter(state="Gujarat"))
    assert res_state.total_retrieved == 2
    assert set(c.chunk_id for c in res_state.chunks) == {"c_cen_gj", "c_plfs_gj"}

    # 3. Combined source list + state filter
    res_multi = retriever.retrieve(
        "data",
        top_k=5,
        filters=RetrievalFilter(source=["plfs_2025", "reddit"], state="Maharashtra"),
    )
    assert res_multi.total_retrieved == 1
    assert res_multi.chunks[0].chunk_id == "c_plfs_mh"


# ------------------------------------------------------------------
# 7. Metadata and Provenance Preservation
# ------------------------------------------------------------------

def test_evidence_metadata_and_provenance_preservation(tmp_path):
    """RetrievedChunk deserializes JSON strings back into structured dictionaries/lists."""
    store = ChromaVectorStore(persist_directory=tmp_path / "chroma")
    provider = TestEmbeddingProvider(model_name="test-model-v1", dimensions=64)

    r1 = make_test_record(
        chunk_id="census_provenance_chunk",
        text="Ahmedabad population literacy benchmark",
        source="census_2011",
        state="Gujarat",
        district="Ahmedabad",
    )
    store.store_embeddings([r1])

    retriever = EvidenceRetriever(vector_store=store, provider=provider)
    res = retriever.retrieve("literacy benchmark", top_k=1)

    assert res.total_retrieved == 1
    chunk = res.chunks[0]

    assert chunk.chunk_id == "census_provenance_chunk"
    assert chunk.document_id == "doc_census_provenance_chunk"
    assert chunk.source == "census_2011"
    assert isinstance(chunk.geography, dict)
    assert chunk.geography["state"] == "Gujarat"
    assert chunk.geography["district"] == "Ahmedabad"
    assert isinstance(chunk.limitations, list)
    assert "Benchmark survey caveat for census_2011" in chunk.limitations[0]
    assert isinstance(chunk.provenance, dict)
    assert chunk.provenance["record_id"] == "census_provenance_chunk"


# ------------------------------------------------------------------
# 8. Interpretation of Retrieval Distance
# ------------------------------------------------------------------

def test_correct_interpretation_of_retrieval_distance(tmp_path):
    """Exact matched query has near-zero distance; distant queries have strictly higher distance."""
    store = ChromaVectorStore(persist_directory=tmp_path / "chroma")
    provider = TestEmbeddingProvider(model_name="test-model-v1", dimensions=64)

    exact_text = "Ahmedabad solar rooftop installation subsidy"
    diff_text = "Coffee shop beverage consumption in South India"

    r1 = make_test_record("exact_c", exact_text)
    r2 = make_test_record("diff_c", diff_text)
    store.store_embeddings([r1, r2])

    retriever = EvidenceRetriever(vector_store=store, provider=provider)
    res = retriever.retrieve(exact_text, top_k=2)

    assert res.total_retrieved == 2
    top_chunk = res.chunks[0]
    second_chunk = res.chunks[1]

    # Deterministic test vectors will have identical embedding for identical text -> distance near 0
    assert top_chunk.chunk_id == "exact_c"
    assert top_chunk.distance < 1e-4
    assert second_chunk.distance > top_chunk.distance


# ------------------------------------------------------------------
# 9. Context Construction and Size Limits
# ------------------------------------------------------------------

def test_context_construction_and_size_limits():
    """build_evidence_context preserves key headers and respects max_chars budget."""
    c1 = RetrievedChunk(
        chunk_id="c1",
        document_id="doc_1",
        text="First evidence observation about market potential",
        distance=0.12,
        source="census_2011",
        geography={"state": "Gujarat", "district": "Ahmedabad", "level": "district"},
        time_period="2011",
        limitations=["Official census caveat"],
    )
    c2 = RetrievedChunk(
        chunk_id="c2",
        document_id="doc_2",
        text="Second evidence observation about labour earnings",
        distance=0.34,
        source="plfs_2025",
        geography={"state": "Gujarat", "district": "Ahmedabad", "level": "district"},
        time_period="2024 to 2025",
        limitations=["Survey sampling error"],
    )

    full_context = build_evidence_context([c1, c2], max_chars=4000)

    assert "RETRIEVED MARKET EVIDENCE CONTEXT" in full_context
    assert "[c1]" in full_context
    assert "[c2]" in full_context
    assert "CENSUS_2011" in full_context
    assert "PLFS_2025" in full_context
    assert "Ahmedabad, Gujarat" in full_context
    assert "Official census caveat" in full_context

    # Test size constraint
    bounded_context = build_evidence_context([c1, c2], max_chars=350)
    assert len(bounded_context) <= 350


# ------------------------------------------------------------------
# 10. Context Duplicate Chunk Handling
# ------------------------------------------------------------------

def test_context_duplicate_chunk_handling():
    """build_evidence_context deduplicates repeated chunks with the same chunk_id."""
    c1 = RetrievedChunk(
        chunk_id="shared_chunk_id",
        document_id="doc_1",
        text="Shared observation text",
        distance=0.05,
        source="reddit",
    )
    c1_dupe = RetrievedChunk(
        chunk_id="shared_chunk_id",
        document_id="doc_1",
        text="Shared observation text",
        distance=0.05,
        source="reddit",
    )

    context = build_evidence_context([c1, c1_dupe], max_chars=2000)

    # Must only appear once
    assert context.count("[shared_chunk_id]") == 1


# ------------------------------------------------------------------
# 11. Missing Credentials & Provider Failures
# ------------------------------------------------------------------

def test_missing_credentials_or_provider_failures(tmp_path, monkeypatch):
    """When no provider is supplied and environment lacks API keys, retriever raises RuntimeError."""
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)

    store = ChromaVectorStore(persist_directory=tmp_path / "chroma")
    retriever = EvidenceRetriever(vector_store=store, provider=None)

    with pytest.raises(RuntimeError, match="No embedding provider supplied and default Google provider failed"):
        retriever.retrieve("market query")


# ------------------------------------------------------------------
# 12. Deterministic Retrieval with Injected Test Embeddings
# ------------------------------------------------------------------

def test_deterministic_retrieval_with_injected_provider(tmp_path):
    """Injected TestEmbeddingProvider produces consistent rankings and distances across calls."""
    store = ChromaVectorStore(persist_directory=tmp_path / "chroma")
    provider = TestEmbeddingProvider(model_name="test-model-v1", dimensions=64)

    r1 = make_test_record("chunk_a", "Solar manufacturing supply chain")
    r2 = make_test_record("chunk_b", "Wind turbine manufacturing supply chain")
    store.store_embeddings([r1, r2])

    retriever = EvidenceRetriever(vector_store=store, provider=provider)

    res_1 = retriever.retrieve("Solar manufacturing", top_k=2)
    res_2 = retriever.retrieve("Solar manufacturing", top_k=2)

    assert [c.chunk_id for c in res_1.chunks] == [c.chunk_id for c in res_2.chunks]
    assert [c.distance for c in res_1.chunks] == [c.distance for c in res_2.chunks]


# ------------------------------------------------------------------
# 13. No Unintended Writes to Production Database
# ------------------------------------------------------------------

def test_no_writes_to_production_database(tmp_path):
    """Querying an isolated store does not create or modify production data/chroma directory."""
    prod_path = Path("data/chroma")
    initial_mtime = prod_path.stat().st_mtime if prod_path.exists() else None

    store = ChromaVectorStore(persist_directory=tmp_path / "chroma")
    provider = TestEmbeddingProvider(model_name="test-model-v1", dimensions=64)
    r1 = make_test_record("c1", "Test chunk")
    store.store_embeddings([r1])

    retriever = EvidenceRetriever(vector_store=store, provider=provider)
    retriever.retrieve("Test query", top_k=1)

    if initial_mtime is not None:
        assert prod_path.stat().st_mtime == initial_mtime


# ------------------------------------------------------------------
# 14. Persistence Across Disk Reopen
# ------------------------------------------------------------------

def test_persistence_across_disk_reopen(tmp_path):
    """Evidence stored in session 1 can be retrieved by an EvidenceRetriever opened in session 2."""
    db_path = tmp_path / "reopen_chroma"
    provider = TestEmbeddingProvider(model_name="test-model-v1", dimensions=64)

    # Session 1: Store evidence
    store1 = ChromaVectorStore(persist_directory=db_path, collection_name="reopen_col")
    rec = make_test_record("persistent_reopen_chunk", "Persistent observation across restarts")
    store1.store_embeddings([rec])
    del store1

    # Session 2: Fresh store and retriever instance
    store2 = ChromaVectorStore(persist_directory=db_path, collection_name="reopen_col")
    retriever = EvidenceRetriever(vector_store=store2, provider=provider)

    res = retriever.retrieve("restarts observation", top_k=1)
    assert res.total_retrieved == 1
    assert res.chunks[0].chunk_id == "persistent_reopen_chunk"
    assert res.chunks[0].text == "Persistent observation across restarts"


# ------------------------------------------------------------------
# 15. Unavailable Vector Storage Handling
# ------------------------------------------------------------------

def test_retriever_handles_unavailable_vector_store():
    """When vector_store is None or unavailable, retrieve returns clean empty result with diagnostics."""
    retriever = EvidenceRetriever(vector_store=None)
    assert retriever.is_available() is False
    assert retriever.collection_name == ""

    res = retriever.retrieve("any query terms", top_k=3)
    assert res.total_retrieved == 0
    assert res.chunks == []
    assert len(res.diagnostics["issues"]) > 0
    assert "unavailable" in res.diagnostics["issues"][0].lower()


def test_retriever_is_available_with_valid_store(tmp_path):
    """is_available returns True when a valid vector store is attached."""
    store = ChromaVectorStore(persist_directory=tmp_path / "valid_store")
    retriever = EvidenceRetriever(vector_store=store)
    assert retriever.is_available() is True
