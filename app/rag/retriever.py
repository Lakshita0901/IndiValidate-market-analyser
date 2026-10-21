"""
app.rag.retriever
-----------------
Semantic evidence retrieval and context construction for IndiValidate.

Provides:
1. Typed retrieval schemas (RetrievedChunk, RetrievalResult, RetrievalFilter).
2. EvidenceRetriever for querying ChromaDB collections using compatible embedding providers.
3. Strict model and dimension compatibility validation.
4. Metadata filtering across sources, geography, evidence types, and time periods.
5. Evidence context builder for LLM persona evaluation.
"""

import json
import math
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, ConfigDict, Field

from app.rag.embeddings import EmbeddingProvider, GoogleEmbeddingProvider, TestEmbeddingProvider
from app.rag.vector_store import ChromaVectorStore, DEFAULT_COLLECTION_NAME


# ------------------------------------------------------------------
# 1. Structured Retrieval Schemas
# ------------------------------------------------------------------

class RetrievedChunk(BaseModel):
    """
    Structured representation of an individual retrieved evidence chunk.
    Preserves chunk ID, parent document ID, text, distance, and full provenance.
    """
    model_config = ConfigDict(extra="forbid")

    chunk_id: str = Field(description="Unique stable chunk identifier")
    document_id: str = Field(description="Parent retrieval document identifier")
    text: str = Field(description="Original textual content of the chunk")
    distance: float = Field(
        ge=0.0,
        description="Raw vector distance from query (lower distance indicates higher similarity)"
    )
    source: str = Field(description="Source identifier (e.g. census_2011, plfs_2025, google_trends, reddit)")
    evidence_type: Optional[str] = Field(default=None, description="Category of evidence")
    geography: Optional[Dict[str, Any]] = Field(default=None, description="Structured geographic scope")
    time_period: Optional[Union[str, Dict[str, Any]]] = Field(default=None, description="Time period or date range")
    provenance: Optional[Dict[str, Any]] = Field(default=None, description="Source provenance details")
    limitations: Optional[List[str]] = Field(default=None, description="Documented caveats or limitations")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Complete raw and deserialized metadata")


class RetrievalFilter(BaseModel):
    """
    Structured filter parameters for metadata-constrained retrieval queries.
    """
    model_config = ConfigDict(extra="forbid")

    source: Optional[Union[str, List[str]]] = Field(default=None, description="Filter by source(s)")
    state: Optional[str] = Field(default=None, description="Filter by geographic state")
    district: Optional[str] = Field(default=None, description="Filter by geographic district")
    evidence_type: Optional[str] = Field(default=None, description="Filter by evidence type")
    time_period: Optional[str] = Field(default=None, description="Filter by time period")
    extra: Optional[Dict[str, Any]] = Field(default=None, description="Additional custom metadata criteria")

    def to_chroma_where(self) -> Optional[Dict[str, Any]]:
        """
        Convert filter parameters into ChromaDB-compatible 'where' expression.
        Supports single criteria and composite $and expressions.
        """
        conditions: List[Dict[str, Any]] = []

        if self.source:
            if isinstance(self.source, list):
                if len(self.source) == 1:
                    conditions.append({"source": self.source[0]})
                elif len(self.source) > 1:
                    conditions.append({"source": {"$in": self.source}})
            else:
                conditions.append({"source": self.source})

        if self.state:
            conditions.append({"geography_state": self.state})

        if self.district:
            conditions.append({"geography_district": self.district})

        if self.evidence_type:
            conditions.append({"evidence_type": self.evidence_type})

        if self.time_period:
            conditions.append({"time_period": str(self.time_period)})

        if self.extra:
            for k, v in self.extra.items():
                conditions.append({k: v})

        if not conditions:
            return None
        elif len(conditions) == 1:
            return conditions[0]
        else:
            return {"$and": conditions}


class RetrievalResult(BaseModel):
    """
    Complete structured response for a semantic evidence retrieval query.
    """
    model_config = ConfigDict(extra="forbid")

    query: str = Field(description="The input query string")
    chunks: List[RetrievedChunk] = Field(default_factory=list, description="Ranked retrieved chunks")
    total_retrieved: int = Field(ge=0, description="Count of retrieved chunks")
    collection_name: str = Field(description="Target ChromaDB collection name")
    embedding_model: str = Field(description="Model used for query embedding")
    embedding_dimensions: int = Field(default=0, ge=0, description="Dimensionality of query vector")
    filters_applied: Optional[Dict[str, Any]] = Field(default=None, description="Filters used for query")
    diagnostics: Dict[str, Any] = Field(default_factory=dict, description="Execution diagnostics and stats")


# ------------------------------------------------------------------
# 2. Deserialization Helpers
# ------------------------------------------------------------------

def _parse_metadata_field(val: Any) -> Any:
    """Safely parse a potentially JSON-serialized metadata string back to dict/list."""
    if isinstance(val, str) and (val.startswith("{") or val.startswith("[")):
        try:
            return json.loads(val)
        except Exception:
            return val
    return val


def _construct_retrieved_chunk(
    chunk_id: str,
    text: str,
    distance: float,
    raw_meta: Dict[str, Any],
) -> RetrievedChunk:
    """Reconstruct a RetrievedChunk from raw ChromaDB query outputs."""
    parsed_meta: Dict[str, Any] = {}
    for k, v in raw_meta.items():
        parsed_meta[k] = _parse_metadata_field(v)

    doc_id = str(parsed_meta.get("document_id") or "")
    src = str(parsed_meta.get("source") or "unknown")
    ev_type = parsed_meta.get("evidence_type")

    # Geography resolution
    geo = parsed_meta.get("geography")
    if not isinstance(geo, dict):
        # Fall back to flat scalar helpers
        geo_dict = {}
        if "geography_state" in parsed_meta:
            geo_dict["state"] = parsed_meta["geography_state"]
        if "geography_district" in parsed_meta:
            geo_dict["district"] = parsed_meta["geography_district"]
        if "geography_level" in parsed_meta:
            geo_dict["level"] = parsed_meta["geography_level"]
        geo = geo_dict if geo_dict else None

    # Time period resolution
    tp = parsed_meta.get("time_period")

    # Provenance and limitations
    prov = parsed_meta.get("provenance")
    if not isinstance(prov, dict):
        prov = None

    limits = parsed_meta.get("limitations")
    if not isinstance(limits, list):
        if isinstance(limits, str):
            limits = [limits]
        else:
            limits = None

    return RetrievedChunk(
        chunk_id=chunk_id,
        document_id=doc_id,
        text=text,
        distance=float(distance),
        source=src,
        evidence_type=str(ev_type) if ev_type else None,
        geography=geo,
        time_period=tp,
        provenance=prov,
        limitations=limits,
        metadata=parsed_meta,
    )


# ------------------------------------------------------------------
# 3. EvidenceRetriever Class
# ------------------------------------------------------------------

class EvidenceRetriever:
    """
    Semantic evidence retriever operating over a persistent ChromaVectorStore.
    """

    def __init__(
        self,
        vector_store: Optional[ChromaVectorStore] = None,
        provider: Optional[EmbeddingProvider] = None,
    ):
        self.vector_store = vector_store
        self._provider = provider

    @property
    def collection_name(self) -> str:
        return self.vector_store.collection_name if self.vector_store else ""

    def is_available(self) -> bool:
        """Check if vector store is initialized and reachable."""
        if self.vector_store is None:
            return False
        try:
            return self.vector_store.count() >= 0
        except Exception:
            return False

    def _resolve_provider(self, collection_info: Dict[str, Any]) -> EmbeddingProvider:
        """Resolve and validate the appropriate embedding provider."""
        if self._provider is not None:
            return self._provider

        col_meta = collection_info.get("metadata") or {}
        expected_model = col_meta.get("embedding_model")

        # In offline test scenarios without live credentials, caller should inject provider
        try:
            return GoogleEmbeddingProvider(model=expected_model or GoogleEmbeddingProvider.DEFAULT_MODEL)
        except Exception as e:
            raise RuntimeError(
                f"No embedding provider supplied and default Google provider failed to initialize: {e}. "
                f"Please provide an explicit or injected EmbeddingProvider."
            ) from e

    def _validate_compatibility(
        self,
        provider: EmbeddingProvider,
        collection_info: Dict[str, Any],
    ) -> None:
        """Enforce strict model and dimension compatibility before querying."""
        col_meta = collection_info.get("metadata") or {}
        expected_model = col_meta.get("embedding_model")
        expected_dims = col_meta.get("embedding_dimensions")

        # Model check
        if expected_model and provider.model_name != expected_model:
            raise ValueError(
                f"Embedding model mismatch for retrieval: collection '{self.collection_name}' "
                f"requires model '{expected_model}', but provider uses '{provider.model_name}'. "
                f"Mixing models in retrieval produces invalid vector distances."
            )

        # Dimension check
        if expected_dims is not None and provider.dimensions is not None:
            if int(provider.dimensions) != int(expected_dims):
                raise ValueError(
                    f"Dimension mismatch for retrieval: collection '{self.collection_name}' expects "
                    f"{expected_dims} dimensions, but provider declared {provider.dimensions} dimensions."
                )

    def retrieve(
        self,
        query: str,
        top_k: int = 5,
        filters: Optional[Union[RetrievalFilter, Dict[str, Any]]] = None,
    ) -> RetrievalResult:
        """
        Execute semantic retrieval for a natural-language query.

        Parameters:
        - query: The query string to embed and match.
        - top_k: Maximum number of chunks to return (must be >= 1).
        - filters: Optional RetrievalFilter or raw filter dictionary.

        Returns:
        - RetrievalResult containing validated chunks and diagnostics.
        """
        if not query or not query.strip():
            raise ValueError("Query string cannot be empty or whitespace-only.")

        if top_k < 1:
            raise ValueError(f"top_k must be at least 1, got {top_k}.")

        # Handle unavailable vector storage gracefully
        if self.vector_store is None:
            return RetrievalResult(
                query=query.strip(),
                chunks=[],
                total_retrieved=0,
                collection_name="",
                embedding_model=self._provider.model_name if self._provider else "",
                embedding_dimensions=self._provider.dimensions if self._provider and self._provider.dimensions else 0,
                filters_applied=filters.model_dump() if isinstance(filters, RetrievalFilter) else filters,
                diagnostics={
                    "query_length": len(query) if query else 0,
                    "top_k_requested": top_k,
                    "collection_count": 0,
                    "issues": ["Vector store is unavailable or uninitialized."],
                },
            )

        try:
            col_count = self.vector_store.count()
        except Exception as e:
            return RetrievalResult(
                query=query.strip(),
                chunks=[],
                total_retrieved=0,
                collection_name=self.collection_name,
                embedding_model=self._provider.model_name if self._provider else "",
                embedding_dimensions=self._provider.dimensions if self._provider and self._provider.dimensions else 0,
                filters_applied=filters.model_dump() if isinstance(filters, RetrievalFilter) else filters,
                diagnostics={
                    "query_length": len(query) if query else 0,
                    "top_k_requested": top_k,
                    "collection_count": 0,
                    "issues": [f"Vector store access error: {e}"],
                },
            )

        diagnostics: Dict[str, Any] = {
            "query_length": len(query) if query else 0,
            "top_k_requested": top_k,
            "collection_count": col_count,
            "issues": [],
        }

        col_info = self.vector_store.get_collection_info()
        provider = self._resolve_provider(col_info)
        self._validate_compatibility(provider, col_info)

        # If collection is empty, return clean empty result
        if col_info["count"] == 0:
            return RetrievalResult(
                query=query.strip(),
                chunks=[],
                total_retrieved=0,
                collection_name=self.collection_name,
                embedding_model=provider.model_name,
                embedding_dimensions=provider.dimensions or 0,
                filters_applied=filters.model_dump() if isinstance(filters, RetrievalFilter) else filters,
                diagnostics=diagnostics,
            )

        # Generate query vector
        query_vector = provider.embed_query(query.strip())
        if not query_vector or not all(isinstance(x, (int, float)) and math.isfinite(x) for x in query_vector):
            raise ValueError("Query embedding returned empty or non-finite values.")

        # Re-check actual vector dimension against collection
        expected_dims = col_info.get("metadata", {}).get("embedding_dimensions")
        if expected_dims is not None and len(query_vector) != int(expected_dims):
            raise ValueError(
                f"Generated query vector dimension ({len(query_vector)}) does not match "
                f"collection dimension ({expected_dims})."
            )

        # Resolve where clause
        where_clause: Optional[Dict[str, Any]] = None
        filters_dict: Optional[Dict[str, Any]] = None

        if isinstance(filters, RetrievalFilter):
            where_clause = filters.to_chroma_where()
            filters_dict = filters.model_dump()
        elif isinstance(filters, dict):
            # Check if it's already a ChromaDB where dict or a filter dict
            if any(k.startswith("$") or k.startswith("geography_") for k in filters):
                where_clause = filters
            else:
                rf = RetrievalFilter(**filters)
                where_clause = rf.to_chroma_where()
            filters_dict = filters

        # Query collection
        col = self.vector_store.get_or_create_collection()
        n_res = min(top_k, col_info["count"])

        query_kwargs: Dict[str, Any] = {
            "query_embeddings": [query_vector],
            "n_results": n_res,
            "include": ["documents", "metadatas", "distances"],
        }
        if where_clause:
            query_kwargs["where"] = where_clause

        try:
            raw_res = col.query(**query_kwargs)
        except Exception as e:
            diagnostics["issues"].append(f"ChromaDB query execution error: {e}")
            raise RuntimeError(f"ChromaDB retrieval error: {e}") from e

        # Parse query response
        retrieved_chunks: List[RetrievedChunk] = []

        ids_list = raw_res.get("ids", [[]])[0]
        docs_list = raw_res.get("documents", [[]])[0]
        metas_list = raw_res.get("metadatas", [[]])[0]
        dists_list = raw_res.get("distances", [[]])[0]

        for cid, doc_text, meta, dist in zip(ids_list, docs_list, metas_list, dists_list):
            chunk_obj = _construct_retrieved_chunk(
                chunk_id=cid,
                text=doc_text,
                distance=dist,
                raw_meta=meta or {},
            )
            retrieved_chunks.append(chunk_obj)

        return RetrievalResult(
            query=query.strip(),
            chunks=retrieved_chunks,
            total_retrieved=len(retrieved_chunks),
            collection_name=self.collection_name,
            embedding_model=provider.model_name,
            embedding_dimensions=len(query_vector),
            filters_applied=filters_dict,
            diagnostics=diagnostics,
        )


# ------------------------------------------------------------------
# 4. Context Construction for LLM Agents
# ------------------------------------------------------------------

def build_evidence_context(
    retrieval_input: Union[RetrievalResult, List[RetrievedChunk]],
    max_chars: int = 4000,
) -> str:
    """
    Format retrieved evidence into a structured, traceable markdown context
    suitable for downstream LLM evaluation.

    Features:
    - Maintains source, geographic scope, and time period attribution.
    - Preserves explicit chunk traceability and limitations.
    - Deduplicates identical chunk text/IDs.
    - Strictly enforces max_chars budget without cutting off mid-tag.
    """
    if isinstance(retrieval_input, RetrievalResult):
        chunks = retrieval_input.chunks
    elif isinstance(retrieval_input, list):
        chunks = retrieval_input
    else:
        return "No evidence available."

    if not chunks:
        return "No relevant evidence found for this query."

    header = "### RETRIEVED MARKET EVIDENCE CONTEXT\n\n"
    sections: List[str] = []
    seen_chunk_ids = set()
    current_chars = len(header)

    for i, chunk in enumerate(chunks, 1):
        cid = getattr(chunk, "chunk_id", None) or (chunk.get("chunk_id") if isinstance(chunk, dict) else None)
        if not cid:
            cid = f"chunk_{i}"
        if cid in seen_chunk_ids:
            continue
        seen_chunk_ids.add(cid)

        # Geographic descriptor
        geo = getattr(chunk, "geography", None) or (chunk.get("geography") if isinstance(chunk, dict) else None)
        geo_str = "Not specified"
        if isinstance(geo, dict):
            state = geo.get("state")
            dist = geo.get("district")
            level = geo.get("level")
            parts = [p for p in (dist, state) if p]
            geo_str = ", ".join(parts) if parts else "India"
            if level:
                geo_str += f" ({level})"

        # Time period descriptor
        tp = getattr(chunk, "time_period", None) or (chunk.get("time_period") if isinstance(chunk, dict) else None)
        time_str = "Not reported"
        if isinstance(tp, str):
            time_str = tp
        elif isinstance(tp, dict):
            time_str = f"{tp.get('start', '')} to {tp.get('end', '')}".strip()

        # Distance & source & text
        src = getattr(chunk, "source", None) or (chunk.get("source") if isinstance(chunk, dict) else "UNKNOWN")
        txt = getattr(chunk, "text", None) or (chunk.get("text") if isinstance(chunk, dict) else "")
        dist = getattr(chunk, "distance", None) or (chunk.get("distance") if isinstance(chunk, dict) else None)
        dist_str = f"{dist:.4f} (ChromaDB vector distance)" if dist is not None else "N/A (Pre-retrieved fallback evidence)"

        limits = getattr(chunk, "limitations", None) or (chunk.get("limitations") if isinstance(chunk, dict) else None)

        block_lines = [
            f"#### Evidence Item {i}: [{cid}]",
            f"- **Source**: {str(src).upper()}",
            f"- **Geography**: {geo_str}",
            f"- **Time Period**: {time_str}",
            f"- **Distance**: {dist_str}",
            f"- **Observation**: {txt}",
        ]

        if limits and isinstance(limits, (list, tuple)):
            limit_str = "; ".join(str(x) for x in limits)
            block_lines.append(f"- **Caveats / Limitations**: {limit_str}")

        block_str = "\n".join(block_lines) + "\n\n"

        if current_chars + len(block_str) > max_chars:
            if not sections:
                # Truncate single oversized first block to fit
                allowed = max_chars - current_chars - 20
                if allowed > 100:
                    sections.append(block_str[:allowed] + "\n... [Truncated]")
            break

        sections.append(block_str)
        current_chars += len(block_str)

    return header + "".join(sections).strip()


# ------------------------------------------------------------------
# 5. Functional Convenience API
# ------------------------------------------------------------------

def retrieve_evidence(
    query: str,
    vector_store: Optional[ChromaVectorStore] = None,
    provider: Optional[EmbeddingProvider] = None,
    top_k: int = 5,
    filters: Optional[Union[RetrievalFilter, Dict[str, Any]]] = None,
) -> RetrievalResult:
    """
    Functional entrypoint for semantic evidence retrieval.
    """
    retriever = EvidenceRetriever(vector_store=vector_store, provider=provider)
    return retriever.retrieve(query=query, top_k=top_k, filters=filters)
