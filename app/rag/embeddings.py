"""
embeddings.py
-------------
Embedding generation and validation layer for IndiValidate RAG pipeline (Step 6).

Generates validated numerical vector embeddings for eligible DocumentChunks:
  1. Provider Interface: Abstract provider protocol supporting pluggable embedding backends.
  2. Google GenAI Provider: Uses GoogleGenerativeAIEmbeddings with models/gemini-embedding-001
     (3072 dimensions) with bounded batching, exponential backoff, and retry logic.
  3. Deterministic Test Provider: Offline deterministic provider for unit tests.
  4. Validated Record: Enforces non-empty, finite numeric vectors with exact dimension matching
     and metadata traceability.
  5. Isolated Failure Handling: Batch and chunk failures are captured in diagnostics without
     fabricating fake or zero-filled vectors.
"""

import math
import os
import time
from hashlib import sha256
from typing import Any, Dict, List, Optional, Protocol, Tuple, Union
from pydantic import BaseModel, Field, ConfigDict, model_validator

from app.rag.chunker import DocumentChunk


# ------------------------------------------------------------------
# 1. Validated Embedding Record Model
# ------------------------------------------------------------------

class ChunkEmbeddingRecord(BaseModel):
    """
    Validated embedding representation for an individual DocumentChunk.
    Preserves exact numeric vector, dimensions, model attribution, and chunk metadata.
    """
    model_config = ConfigDict(extra="forbid")

    chunk_id: str = Field(
        description="Deterministic chunk identifier matching the parent DocumentChunk"
    )
    document_id: str = Field(
        description="Parent retrieval document identifier"
    )
    text: str = Field(
        description="The chunk's textual content that was embedded"
    )
    embedding: List[float] = Field(
        description="Numerical vector representation (floats)"
    )
    embedding_model: str = Field(
        description="Exact model name used to generate the embedding (e.g. models/gemini-embedding-001)"
    )
    embedding_dimensions: int = Field(
        ge=1,
        description="Declared dimensionality of the embedding vector"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Inherited metadata from chunk (source, geography, period, provenance, etc.)"
    )

    @model_validator(mode="after")
    def validate_embedding_vector(self) -> "ChunkEmbeddingRecord":
        if not self.embedding:
            raise ValueError(f"Embedding vector for chunk '{self.chunk_id}' cannot be empty.")

        actual_len = len(self.embedding)
        if actual_len != self.embedding_dimensions:
            raise ValueError(
                f"Declared dimensions ({self.embedding_dimensions}) does not match "
                f"actual vector length ({actual_len}) for chunk '{self.chunk_id}'."
            )

        for i, val in enumerate(self.embedding):
            if not isinstance(val, (int, float)):
                raise ValueError(
                    f"Vector element at index {i} in chunk '{self.chunk_id}' is not numeric: {type(val)}"
                )
            if math.isnan(val) or math.isinf(val):
                raise ValueError(
                    f"Vector element at index {i} in chunk '{self.chunk_id}' is non-finite: {val}"
                )

        return self


# ------------------------------------------------------------------
# 2. Embedding Provider Protocol & Implementations
# ------------------------------------------------------------------

class EmbeddingProvider(Protocol):
    """Protocol defining the embedding provider interface."""

    @property
    def model_name(self) -> str:
        """The canonical model name of this provider."""
        ...

    @property
    def dimensions(self) -> Optional[int]:
        """The declared dimensions of vectors produced by this provider."""
        ...

    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        """Embed a batch of text strings into numerical vectors."""
        ...

    def embed_query(self, text: str) -> List[float]:
        """Embed a single query text string into a numerical vector."""
        ...


class GoogleEmbeddingProvider:
    """
    Google GenAI embedding provider using langchain-google-genai.
    Defaults to models/gemini-embedding-001 (3072 dimensions).
    """

    DEFAULT_MODEL = "models/gemini-embedding-001"

    def __init__(
        self,
        model: str = DEFAULT_MODEL,
        api_key: Optional[str] = None,
        max_retries: int = 3,
        backoff_factor: float = 1.5,
    ):
        # Normalize model name
        if not model.startswith("models/") and not model.startswith("gemini-"):
            self._model = f"models/{model}"
        elif model.startswith("gemini-"):
            self._model = f"models/{model}"
        else:
            self._model = model

        # Check credentials
        resolved_key = api_key or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        if not resolved_key:
            raise ValueError(
                "Google API key not found in environment (GEMINI_API_KEY or GOOGLE_API_KEY). "
                "Provider cannot be initialized without valid credentials."
            )

        self._api_key = resolved_key
        self._max_retries = max_retries
        self._backoff_factor = backoff_factor
        self._client: Optional[Any] = None
        self._dimensions: Optional[int] = 3072 if "gemini-embedding-001" in self._model else None

    def _get_client(self) -> Any:
        if self._client is None:
            from langchain_google_genai import GoogleGenerativeAIEmbeddings
            self._client = GoogleGenerativeAIEmbeddings(
                model=self._model,
                google_api_key=self._api_key,
            )
        return self._client

    @property
    def model_name(self) -> str:
        return self._model

    @property
    def dimensions(self) -> Optional[int]:
        return self._dimensions

    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        """Embed a list of text strings with retry and exponential backoff."""
        if not texts:
            return []

        client = self._get_client()
        last_error = None

        for attempt in range(self._max_retries):
            try:
                embeddings = client.embed_documents(texts)
                if embeddings and self._dimensions is None:
                    self._dimensions = len(embeddings[0])
                return embeddings
            except Exception as e:
                last_error = e
                # Don't retry on non-transient auth/permission errors
                err_str = str(e).lower()
                if "api_key_invalid" in err_str or "unauthenticated" in err_str or "permission" in err_str:
                    raise e
                if attempt < self._max_retries - 1:
                    sleep_time = self._backoff_factor ** attempt
                    time.sleep(sleep_time)

        raise RuntimeError(
            f"Failed to generate embeddings using model '{self._model}' after {self._max_retries} attempts: {last_error}"
        ) from last_error

    def embed_query(self, text: str) -> List[float]:
        """Embed a single query text string."""
        results = self.embed_texts([text])
        if not results:
            raise RuntimeError("Provider returned empty embedding for query.")
        return results[0]


class TestEmbeddingProvider:
    """
    Deterministic offline embedding provider for tests and local development.
    Produces strictly finite, unit-normalized vectors derived from SHA-256 hashes of text.
    Zero external network or API calls.
    """
    __test__ = False  # Prevents pytest from collecting this class as a test suite

    def __init__(
        self,
        model_name: str = "test-deterministic-embedding",
        dimensions: int = 128,
        simulate_failure: bool = False,
        simulate_failure_texts: Optional[List[str]] = None,
        simulate_failure_indices: Optional[List[int]] = None,
    ):
        self._model_name = model_name
        self._dimensions = dimensions
        self._simulate_failure = simulate_failure
        self._simulate_failure_texts = set(simulate_failure_texts or [])
        self._simulate_failure_indices = set(simulate_failure_indices or [])

    @property
    def model_name(self) -> str:
        return self._model_name

    @property
    def dimensions(self) -> int:
        return self._dimensions

    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        if self._simulate_failure:
            raise RuntimeError(f"Simulated provider failure for model '{self._model_name}'")

        results: List[List[float]] = []
        for idx, text in enumerate(texts):
            if text in self._simulate_failure_texts or idx in self._simulate_failure_indices:
                raise RuntimeError(f"Simulated failure on text: '{text[:30]}'")


            # Generate deterministic pseudo-random float vector from text hash
            h = sha256(f"{self._model_name}:{text}".encode("utf-8")).digest()
            raw_floats = []
            for i in range(self._dimensions):
                byte_val = h[i % len(h)]
                # Map byte 0..255 to float in [-1.0, 1.0]
                val = ((byte_val / 255.0) * 2.0) - 1.0
                raw_floats.append(round(val, 6))

            # Normalize vector to unit length
            norm = math.sqrt(sum(x * x for x in raw_floats))
            if norm > 0:
                unit_vec = [round(x / norm, 6) for x in raw_floats]
            else:
                unit_vec = [1.0 / math.sqrt(self._dimensions)] * self._dimensions

            results.append(unit_vec)

        return results

    def embed_query(self, text: str) -> List[float]:
        return self.embed_texts([text])[0]


# ------------------------------------------------------------------
# 3. Master Embedding Generator Function
# ------------------------------------------------------------------

def generate_chunk_embeddings(
    chunks: Optional[List[Union[DocumentChunk, Dict[str, Any]]]],
    provider: Optional[EmbeddingProvider] = None,
    batch_size: int = 16,
) -> Tuple[List[ChunkEmbeddingRecord], Dict[str, Any]]:
    """
    Generate validated ChunkEmbeddingRecords for a collection of DocumentChunks.

    Parameters:
      chunks: List of DocumentChunk instances or equivalent dictionaries.
      provider: Pluggable EmbeddingProvider. If None, initializes GoogleEmbeddingProvider.
      batch_size: Number of texts per provider batch call.

    Returns:
      (embedding_records, diagnostics)
    """
    diagnostics: Dict[str, Any] = {
        "total_chunks_received": 0,
        "eligible_chunks_count": 0,
        "embeddings_generated_count": 0,
        "failed_chunks_count": 0,
        "embedding_model": None,
        "embedding_dimensions": None,
        "batches_processed": 0,
        "issues": [],
    }

    if not chunks or not isinstance(chunks, list):
        return [], diagnostics

    diagnostics["total_chunks_received"] = len(chunks)

    # Filter eligible chunks (exclude is_retrieval_ready=False / whitespace)
    eligible_items: List[DocumentChunk] = []
    for item in chunks:
        if isinstance(item, dict):
            try:
                c = DocumentChunk.model_validate(item)
            except Exception as e:
                diagnostics["issues"].append(f"Failed to parse chunk dict: {e}")
                continue
        elif isinstance(item, DocumentChunk):
            c = item
        else:
            diagnostics["issues"].append(f"Skipped non-chunk item of type {type(item)}")
            continue

        if not c.metadata.get("is_retrieval_ready", True) or c.metadata.get("relevance") == "irrelevant":
            continue

        if not c.text.strip():
            continue

        eligible_items.append(c)

    diagnostics["eligible_chunks_count"] = len(eligible_items)
    if not eligible_items:
        return [], diagnostics

    # Initialize provider if not supplied
    if provider is None:
        try:
            provider = GoogleEmbeddingProvider()
        except Exception as e:
            diagnostics["issues"].append(f"Failed to initialize embedding provider: {e}")
            return [], diagnostics

    diagnostics["embedding_model"] = provider.model_name
    diagnostics["embedding_dimensions"] = provider.dimensions

    embedding_records: List[ChunkEmbeddingRecord] = []

    # Batch execution with per-batch error isolation
    for batch_start in range(0, len(eligible_items), batch_size):
        batch_chunks = eligible_items[batch_start : batch_start + batch_size]
        batch_texts = [c.text for c in batch_chunks]

        try:
            vectors = provider.embed_texts(batch_texts)
            diagnostics["batches_processed"] += 1

            if len(vectors) != len(batch_chunks):
                diagnostics["issues"].append(
                    f"Provider returned {len(vectors)} vectors for {len(batch_chunks)} batch texts."
                )
                continue

            for chunk_obj, vec in zip(batch_chunks, vectors):
                dims = len(vec)
                if diagnostics["embedding_dimensions"] is None:
                    diagnostics["embedding_dimensions"] = dims

                # Model consistency check
                record_meta = dict(chunk_obj.metadata)
                record_meta["embedding_model"] = provider.model_name
                record_meta["embedding_dimensions"] = dims

                try:
                    rec = ChunkEmbeddingRecord(
                        chunk_id=chunk_obj.chunk_id,
                        document_id=chunk_obj.document_id,
                        text=chunk_obj.text,
                        embedding=vec,
                        embedding_model=provider.model_name,
                        embedding_dimensions=dims,
                        metadata=record_meta,
                    )
                    embedding_records.append(rec)
                    diagnostics["embeddings_generated_count"] += 1
                except Exception as val_err:
                    diagnostics["failed_chunks_count"] += 1
                    diagnostics["issues"].append(
                        f"Validation failure for chunk '{chunk_obj.chunk_id}': {val_err}"
                    )

        except Exception as batch_err:
            diagnostics["failed_chunks_count"] += len(batch_chunks)
            diagnostics["issues"].append(
                f"Batch {batch_start // batch_size + 1} embedding failure: {batch_err}"
            )
            continue

    return embedding_records, diagnostics
