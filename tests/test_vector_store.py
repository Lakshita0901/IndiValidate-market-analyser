"""
tests/test_vector_store.py
--------------------------
Unit and integration tests for ChromaDB vector storage and indexing (Step 7).

Verifies:
1. Collection initialization with configurable persistence paths.
2. Successful insertion of multiple embedding records.
3. Correct association between IDs, text, vectors, and metadata.
4. Persistence across client/store reinitialization.
5. Idempotent upsert behavior (no duplicate IDs).
6. Nested metadata serialization (dicts, lists to valid primitives).
7. Empty-input handling (graceful 0 count, clean diagnostics).
8. Invalid vector and dimension handling (rejection of non-finite/mismatched).
9. Incompatible embedding model and dimension detection (rejection of mixed/incompatible).
10. Partial failure diagnostics and isolation.
11. No writes to production database during unit tests (tmp_path enforcement).
12. Pipeline integration with run_research using temporary storage.
"""

import json
import math
import os
from pathlib import Path
import pytest

from app.rag.embeddings import (
    ChunkEmbeddingRecord,
    TestEmbeddingProvider,
)
from app.rag.vector_store import (
    ChromaVectorStore,
    DEFAULT_COLLECTION_NAME,
    get_collection_name_for_model,
    serialize_metadata_for_chroma,
    store_chunk_embeddings,
)
from app.nodes.research import run_research


# ------------------------------------------------------------------
# Test Helpers
# ------------------------------------------------------------------

def make_sample_record(
    chunk_id: str = "chunk_1",
    document_id: str = "doc_1",
    text: str = "Ahmedabad Census 2011 literacy observation text",
    model: str = "test-model-v1",
    dimensions: int = 64,
    metadata: dict = None,
) -> ChunkEmbeddingRecord:
    """Helper to create a deterministic ChunkEmbeddingRecord using TestEmbeddingProvider."""
    provider = TestEmbeddingProvider(model_name=model, dimensions=dimensions)
    vec = provider.embed_query(text)
    meta = metadata or {
        "source": "census_2011",
        "evidence_type": "statistical_observation",
        "geography": {"state": "Gujarat", "district": "Ahmedabad", "level": "district"},
        "time_period": "2011",
        "limitations": ["Official Census 2011 data"],
        "is_retrieval_ready": True,
    }
    return ChunkEmbeddingRecord(
        chunk_id=chunk_id,
        document_id=document_id,
        text=text,
        embedding=vec,
        embedding_model=model,
        embedding_dimensions=dimensions,
        metadata=meta,
    )


# ------------------------------------------------------------------
# 1. Collection Initialization & Directory Configuration
# ------------------------------------------------------------------

def test_collection_initialization_with_custom_path(tmp_path):
    """Verify ChromaVectorStore initializes with custom path and collection name."""
    custom_dir = tmp_path / "custom_chroma"
    store = ChromaVectorStore(
        persist_directory=custom_dir,
        collection_name="test_custom_collection",
    )

    info = store.get_collection_info()
    assert info["collection_name"] == "test_custom_collection"
    assert info["persistence_directory"] == str(custom_dir)
    assert info["count"] == 0
    assert custom_dir.exists()


# ------------------------------------------------------------------
# 2. Insertion & Record Association Tests
# ------------------------------------------------------------------

def test_successful_insertion_of_multiple_records(tmp_path):
    """Verify multiple records can be stored and count matches exactly."""
    store = ChromaVectorStore(persist_directory=tmp_path / "chroma")
    r1 = make_sample_record(chunk_id="c_1", text="First chunk content")
    r2 = make_sample_record(chunk_id="c_2", text="Second chunk content")
    r3 = make_sample_record(chunk_id="c_3", text="Third chunk content")

    count_stored, diag = store.store_embeddings([r1, r2, r3])

    assert count_stored == 3
    assert diag["successfully_stored_count"] == 3
    assert diag["failed_records_count"] == 0
    assert diag["total_collection_count"] == 3
    assert store.count() == 3


def test_correct_association_of_id_text_vector_and_metadata(tmp_path):
    """Verify IDs, texts, vectors, and metadatas match precisely when retrieved."""
    store = ChromaVectorStore(persist_directory=tmp_path / "chroma")
    r1 = make_sample_record(
        chunk_id="census_chunk_1",
        text="Ahmedabad population literacy rate was 85.31%",
        dimensions=64,
        metadata={"source": "census_2011", "indicator": "literacy_rate"},
    )
    store.store_embeddings([r1])

    result = store.get(
        ids=["census_chunk_1"],
        include=["documents", "metadatas", "embeddings"],
    )

    assert result["ids"] == ["census_chunk_1"]
    assert result["documents"] == ["Ahmedabad population literacy rate was 85.31%"]

    meta = result["metadatas"][0]
    assert meta["source"] == "census_2011"
    assert meta["indicator"] == "literacy_rate"
    assert meta["chunk_id"] == "census_chunk_1"

    # Verify vector elements
    retrieved_vec = result["embeddings"][0]
    assert len(retrieved_vec) == 64
    for orig, ret in zip(r1.embedding, retrieved_vec):
        assert abs(orig - ret) < 1e-5


# ------------------------------------------------------------------
# 3. Persistence & Reinitialization
# ------------------------------------------------------------------

def test_persistence_across_client_reinitialization(tmp_path):
    """Verify records persist to disk and can be retrieved after reopening store."""
    db_path = tmp_path / "persistent_chroma"

    # Session 1: Store records
    store1 = ChromaVectorStore(persist_directory=db_path, collection_name="persistent_coll")
    r1 = make_sample_record(chunk_id="p_1", text="Persistent chunk 1")
    r2 = make_sample_record(chunk_id="p_2", text="Persistent chunk 2")
    store1.store_embeddings([r1, r2])
    assert store1.count() == 2

    # Deliberately discard session 1 client reference
    del store1

    # Session 2: Open new store pointing to same directory
    store2 = ChromaVectorStore(persist_directory=db_path, collection_name="persistent_coll")
    assert store2.count() == 2

    res = store2.get(ids=["p_1", "p_2"], include=["documents"])
    assert set(res["ids"]) == {"p_1", "p_2"}
    assert set(res["documents"]) == {"Persistent chunk 1", "Persistent chunk 2"}


# ------------------------------------------------------------------
# 4. Idempotency & Upsert Behavior
# ------------------------------------------------------------------

def test_idempotent_upsert_behavior(tmp_path):
    """Repeatedly upserting the same chunk ID updates in place without duplicating."""
    store = ChromaVectorStore(persist_directory=tmp_path / "chroma")
    r1_initial = make_sample_record(chunk_id="unique_chunk_42", text="Initial observation")
    store.store_embeddings([r1_initial])
    assert store.count() == 1

    # Upsert identical chunk again
    store.store_embeddings([r1_initial])
    assert store.count() == 1

    # Upsert with updated text for same chunk_id
    r1_updated = make_sample_record(chunk_id="unique_chunk_42", text="Updated observation content")
    store.store_embeddings([r1_updated])
    assert store.count() == 1

    res = store.get(ids=["unique_chunk_42"], include=["documents"])
    assert res["documents"] == ["Updated observation content"]


# ------------------------------------------------------------------
# 5. Metadata Serialization & Schema Preservation
# ------------------------------------------------------------------

def test_nested_metadata_serialization_for_chroma():
    """Verify serialize_metadata_for_chroma produces strictly primitive scalar types."""
    complex_meta = {
        "source": "census_2011",
        "sample_size": 1500,
        "rate": 85.3,
        "is_valid": True,
        "empty_field": None,
        "embedding": [0.1, 0.2, 0.3],  # Must be stripped
        "geography": {"state": "Gujarat", "district": "Ahmedabad", "level": "district"},
        "limitations": ["Preliminary survey", "Non-census fallback"],
        "lineage": ["raw", "norm", "clean"],
    }

    serialized = serialize_metadata_for_chroma(complex_meta)

    # Embedding vector must NEVER be in metadata
    assert "embedding" not in serialized

    # None values omitted
    assert "empty_field" not in serialized

    # All values must be str, int, float, or bool
    for k, v in serialized.items():
        assert isinstance(v, (str, int, float, bool)), f"Non-primitive type for {k}: {type(v)}"

    # Check flattened geography helpers
    assert serialized["geography_state"] == "Gujarat"
    assert serialized["geography_district"] == "Ahmedabad"
    assert serialized["geography_level"] == "district"

    # Nested structures preserved as valid JSON
    geo_parsed = json.loads(str(serialized["geography"]))
    assert geo_parsed["state"] == "Gujarat"

    limits_parsed = json.loads(str(serialized["limitations"]))
    assert "Non-census fallback" in limits_parsed


# ------------------------------------------------------------------
# 6. Empty Input Handling
# ------------------------------------------------------------------

def test_empty_input_handled_cleanly(tmp_path):
    """Passing empty list returns 0 count and clean diagnostics without error."""
    store = ChromaVectorStore(persist_directory=tmp_path / "chroma")
    stored_count, diag = store.store_embeddings([])

    assert stored_count == 0
    assert diag["total_records_received"] == 0
    assert diag["successfully_stored_count"] == 0
    assert diag["failed_records_count"] == 0
    assert len(diag["issues"]) == 0


# ------------------------------------------------------------------
# 7. Model and Dimension Consistency Enforcement
# ------------------------------------------------------------------

def test_incompatible_embedding_model_rejected(tmp_path):
    """Storing embeddings from a different model than the collection raises ValueError."""
    store = ChromaVectorStore(persist_directory=tmp_path / "chroma", collection_name="model_test_col")

    # Create collection with model A
    r_model_a = make_sample_record(chunk_id="chunk_a", model="test-model-v1", dimensions=64)
    store.store_embeddings([r_model_a])

    # Attempt to insert record with model B
    r_model_b = make_sample_record(chunk_id="chunk_b", model="models/gemini-embedding-001", dimensions=64)

    with pytest.raises(ValueError, match="Model mismatch"):
        store.store_embeddings([r_model_b])


def test_incompatible_dimension_rejected(tmp_path):
    """Storing embeddings with different dimensionality than the collection raises ValueError."""
    store = ChromaVectorStore(persist_directory=tmp_path / "chroma", collection_name="dim_test_col")

    # Insert 64-dimensional record
    r_64 = make_sample_record(chunk_id="chunk_64", model="test-model-v1", dimensions=64)
    store.store_embeddings([r_64])

    # Attempt to insert 128-dimensional record
    r_128 = make_sample_record(chunk_id="chunk_128", model="test-model-v1", dimensions=128)

    with pytest.raises(ValueError, match="Dimension mismatch"):
        store.store_embeddings([r_128])


# ------------------------------------------------------------------
# 8. Partial Failure Isolation & Invalid Vector Handling
# ------------------------------------------------------------------

def test_partial_failure_isolation_and_invalid_vector_handling(tmp_path):
    """Invalid records (e.g. non-finite values) fail safely without discarding valid records."""
    store = ChromaVectorStore(persist_directory=tmp_path / "chroma")

    # Valid record
    valid_rec = make_sample_record(chunk_id="valid_chunk", text="Valid text content")

    # Malformed record dict with NaN value
    invalid_rec_dict = {
        "chunk_id": "invalid_chunk",
        "document_id": "doc_inv",
        "text": "Malformed chunk with NaN",
        "embedding": [float("nan")] * 64,
        "embedding_model": "test-model-v1",
        "embedding_dimensions": 64,
    }

    # Record with empty text
    empty_txt_rec = {
        "chunk_id": "empty_txt_chunk",
        "document_id": "doc_empty",
        "text": "   ",
        "embedding": [0.1] * 64,
        "embedding_model": "test-model-v1",
        "embedding_dimensions": 64,
    }

    stored_count, diag = store.store_embeddings([valid_rec, invalid_rec_dict, empty_txt_rec])

    assert stored_count == 1
    assert diag["successfully_stored_count"] == 1
    assert diag["failed_records_count"] == 2
    assert store.count() == 1
    assert len(diag["issues"]) == 2


# ------------------------------------------------------------------
# 9. No Writes to Production Database During Unit Tests
# ------------------------------------------------------------------

def test_no_writes_to_production_database(tmp_path):
    """Ensure tests run strictly inside tmp_path without touching default data/chroma."""
    prod_path = Path("data/chroma")
    initial_mtime = prod_path.stat().st_mtime if prod_path.exists() else None

    # Run isolated store in temporary directory
    store = ChromaVectorStore(persist_directory=tmp_path / "isolated")
    rec = make_sample_record(chunk_id="iso_chunk", text="Isolated chunk")
    store.store_embeddings([rec])

    # Assert prod_path was not modified
    if initial_mtime is not None:
        assert prod_path.stat().st_mtime == initial_mtime


# ------------------------------------------------------------------
# 10. Pipeline Integration with run_research
# ------------------------------------------------------------------

def test_run_research_produces_vector_store_persistence(tmp_path):
    """
    End-to-end integration: run_research generates chunks, embeddings,
    and stores them into a configured temporary ChromaDB vector store.
    """
    test_db = tmp_path / "pipeline_chroma"
    test_provider = TestEmbeddingProvider(model_name="test-model-v1", dimensions=64)

    state = {
        "idea": "B2B SaaS manufacturing ERP in Ahmedabad",
        "location": "Ahmedabad",
        "district": "Ahmedabad",
        "keywords": ["erp", "manufacturing"],
        "target_segment": "Factory owners",
        "research_type": "location_based",
        # Configured injections for offline test execution
        "embedding_provider": test_provider,
        "chroma_persist_dir": str(test_db),
        "chroma_collection_name": "test_pipeline_collection",
        "store_embeddings": True,
    }

    result = run_research(state)

    # State validation
    assert "vector_store_diagnostics" in result
    assert "vector_store_count" in result
    vs_diag = result["vector_store_diagnostics"]
    vs_count = result["vector_store_count"]

    assert vs_count > 0
    assert vs_diag["successfully_stored_count"] == vs_count
    assert vs_diag["collection_name"] == "test_pipeline_collection"
    assert vs_diag["persistence_directory"] == str(test_db)

    # Verify database directly
    store = ChromaVectorStore(
        persist_directory=test_db,
        collection_name="test_pipeline_collection",
    )
    assert store.count() == vs_count

    # Check that research errors and embeddings remain preserved
    assert "chunk_embeddings" in result
    assert "research_errors" in result
    assert result["research_complete"] is True


# ------------------------------------------------------------------
# 13. Embedding Model Isolation Tests
# ------------------------------------------------------------------

def test_get_collection_name_for_model_rules():
    """Verify get_collection_name_for_model generates valid, isolated collection names."""
    # Production Gemini model
    gemini_col = get_collection_name_for_model("market_evidence_chunks", "models/gemini-embedding-001", 3072)
    assert gemini_col.startswith("market_evidence_chunks_models_gemini_embedding_001_3072")
    assert len(gemini_col) <= 63
    assert gemini_col[0].isalnum() and gemini_col[-1].isalnum()

    # Deterministic test model
    test_col = get_collection_name_for_model("market_evidence_chunks", "test-deterministic-embedding", 384)
    assert "test-deterministic-embedding" in test_col or "test_deterministic_embedding" in test_col
    assert test_col.endswith("_384")
    assert len(test_col) <= 63

    # None model and dims returns base
    assert get_collection_name_for_model("market_evidence_chunks", None, None) == "market_evidence_chunks"

    # Extremely long model name is truncated and stays <= 63 chars
    long_model = "very_long_organization_prefix/" + ("submodule_a_" * 10) + "model_v1"
    long_col = get_collection_name_for_model("market_evidence_chunks", long_model, 1536)
    assert len(long_col) <= 63
    assert long_col[0].isalnum() and long_col[-1].isalnum()


def test_collection_isolation_across_different_embedding_models(tmp_path):
    """
    Store records with different embedding models and dimensions in the same persist directory.
    They must be isolated into distinct collections without error or data loss.
    """
    db_path = tmp_path / "multi_model_chroma"

    # Store model Alpha (64 dims)
    rec_a = make_sample_record(chunk_id="chunk_a", model="model-alpha", dimensions=64)
    count_a, diag_a = store_chunk_embeddings([rec_a], persist_directory=db_path)
    assert count_a == 1
    col_a_name = diag_a["collection_name"]
    assert "model_alpha_64" in col_a_name or "model-alpha_64" in col_a_name

    # Store model Beta (128 dims) in same directory without specifying collection_name
    rec_b = make_sample_record(chunk_id="chunk_b", model="model-beta", dimensions=128)
    count_b, diag_b = store_chunk_embeddings([rec_b], persist_directory=db_path)
    assert count_b == 1
    col_b_name = diag_b["collection_name"]
    assert "model_beta_128" in col_b_name or "model-beta_128" in col_b_name

    # Verify both collections co-exist without collision
    assert col_a_name != col_b_name

    store_a = ChromaVectorStore(persist_directory=db_path, collection_name=col_a_name)
    store_b = ChromaVectorStore(persist_directory=db_path, collection_name=col_b_name)

    assert store_a.count() == 1
    assert store_b.count() == 1

    got_a = store_a.get(ids=["chunk_a"])
    assert got_a["ids"] == ["chunk_a"]

    got_b = store_b.get(ids=["chunk_b"])
    assert got_b["ids"] == ["chunk_b"]


def test_run_research_auto_isolates_collection_name_when_not_provided(tmp_path):
    """
    When chroma_collection_name is not explicitly passed in state, run_research
    isolates the collection by embedding model and dimensions.
    """
    test_db = tmp_path / "auto_isolate_chroma"
    test_provider = TestEmbeddingProvider(model_name="test-isolated-model", dimensions=64)

    state = {
        "idea": "Electric scooter rental network in Pune",
        "location": "Pune",
        "district": "Pune",
        "keywords": ["scooter", "electric"],
        "target_segment": "Students and workers",
        "research_type": "location_based",
        "embedding_provider": test_provider,
        "chroma_persist_dir": str(test_db),
        # chroma_collection_name omitted to test auto-isolation
        "store_embeddings": True,
    }

    result = run_research(state)
    assert result["research_complete"] is True
    assert "chroma_collection_name" in result
    isolated_col = result["chroma_collection_name"]
    assert "test_isolated_model_64" in isolated_col or "test-isolated-model_64" in isolated_col

    # Verify collection exists in ChromaDB with chunks
    store = ChromaVectorStore(persist_directory=test_db, collection_name=isolated_col)
    assert store.count() > 0
