"""
app.rag.vector_store
--------------------
Persistent ChromaDB vector storage and indexing for IndiValidate.

Manages persistent client connections, collection lifecycle, metadata
serialization, model and dimensionality consistency, idempotent upserting,
and storage diagnostics.
"""

import hashlib
import json
import math
import os
from pathlib import Path
import re
from typing import Any, Dict, List, Optional, Tuple, Union

from app.rag.embeddings import ChunkEmbeddingRecord

# Default persistence settings
DEFAULT_PERSIST_DIRECTORY = "data/chroma"
DEFAULT_COLLECTION_NAME = "market_evidence_chunks"


# ------------------------------------------------------------------
# Collection Name Isolation
# ------------------------------------------------------------------

def get_collection_name_for_model(
    base_name: str = DEFAULT_COLLECTION_NAME,
    embedding_model: Optional[str] = None,
    embedding_dimensions: Optional[int] = None,
) -> str:
    """
    Generate an isolated, ChromaDB-compliant collection name incorporating the embedding
    model and dimensionality, preventing collision between distinct vector spaces.

    ChromaDB naming constraints:
    - 3-63 characters in length.
    - Starts and ends with an alphanumeric character ([a-zA-Z0-9]).
    - Allowed characters: alphanumeric, underscores, hyphens ([a-zA-Z0-9_-]).
    - No consecutive dots, not an IPv4 address.
    """
    if not embedding_model and not embedding_dimensions:
        return base_name

    clean_base = re.sub(r"[^a-zA-Z0-9_-]+", "_", base_name).strip("._-")
    if not clean_base:
        clean_base = "market_evidence"

    model_slug = ""
    if embedding_model:
        model_slug = re.sub(r"[^a-zA-Z0-9]+", "_", str(embedding_model)).strip("_")

    dim_suffix = f"_{embedding_dimensions}" if embedding_dimensions is not None else ""

    if model_slug:
        candidate = f"{clean_base}_{model_slug}{dim_suffix}"
    else:
        candidate = f"{clean_base}{dim_suffix}"

    # ChromaDB enforces max 63 chars
    if len(candidate) > 63:
        digest = hashlib.sha256(f"{embedding_model}:{embedding_dimensions}".encode("utf-8")).hexdigest()[:8]
        allowed_prefix_len = 63 - len(digest) - 1 - len(dim_suffix)
        candidate = f"{clean_base[:max(10, allowed_prefix_len)]}_{digest}{dim_suffix}"

    candidate = re.sub(r"[^a-zA-Z0-9_-]+", "_", candidate).strip("._-")
    while len(candidate) < 3:
        candidate = candidate + "0"

    return candidate


# ------------------------------------------------------------------
# 1. Metadata Serialization for ChromaDB
# ------------------------------------------------------------------

def serialize_metadata_for_chroma(
    metadata: Dict[str, Any],
) -> Dict[str, Union[str, int, float, bool]]:
    """
    Serialize an arbitrary metadata dictionary into ChromaDB-compatible primitive scalars.
    ChromaDB allows only: str, int, float, bool.
    - None values are omitted.
    - Embedded vectors or keys named 'embedding' are excluded.
    - Nested dictionaries and lists are serialized deterministically via json.dumps(sort_keys=True).
    - If a 'geography' dictionary is present, top-level scalar projections
      (geography_state, geography_district, geography_level) are added to simplify metadata filtering.
    """
    if not isinstance(metadata, dict):
        return {}

    serialized: Dict[str, Union[str, int, float, bool]] = {}

    for key, val in metadata.items():
        # Do not store raw vectors inside metadata
        if key in ("embedding", "vector"):
            continue

        if val is None:
            continue
        elif isinstance(val, bool):
            serialized[key] = val
        elif isinstance(val, int):
            serialized[key] = val
        elif isinstance(val, float):
            if math.isnan(val) or math.isinf(val):
                continue
            serialized[key] = val
        elif isinstance(val, str):
            serialized[key] = val
        elif isinstance(val, (list, dict)):
            serialized[key] = json.dumps(val, sort_keys=True, ensure_ascii=False)
        else:
            serialized[key] = str(val)

    # Geographic scalar projections for convenient ChromaDB filtering
    raw_geo = metadata.get("geography")
    if isinstance(raw_geo, dict):
        for sub_k in ("state", "district", "level"):
            geo_v = raw_geo.get(sub_k)
            if geo_v is not None and isinstance(geo_v, (str, int, float, bool)):
                flat_key = f"geography_{sub_k}"
                if flat_key not in serialized:
                    serialized[flat_key] = geo_v

    return serialized


# ------------------------------------------------------------------
# 2. ChromaVectorStore Class
# ------------------------------------------------------------------

class ChromaVectorStore:
    """
    Persistent ChromaDB vector store manager.

    Features:
    - PersistentClient with configurable directory (defaults to data/chroma).
    - Strict embedding model and dimensionality enforcement across collections.
    - Idempotent upsert by chunk_id.
    - Deterministic metadata serialization and error isolation.
    """

    def __init__(
        self,
        persist_directory: Optional[Union[str, Path]] = None,
        collection_name: str = DEFAULT_COLLECTION_NAME,
        client: Optional[Any] = None,
    ):
        self.persist_directory = Path(
            persist_directory or os.getenv("CHROMA_PERSIST_DIR", DEFAULT_PERSIST_DIRECTORY)
        )
        self.collection_name = collection_name or DEFAULT_COLLECTION_NAME

        if client is not None:
            self._client = client
        else:
            import chromadb
            self.persist_directory.mkdir(parents=True, exist_ok=True)
            self._client = chromadb.PersistentClient(path=str(self.persist_directory))

        self._collection: Optional[Any] = None

    @property
    def client(self) -> Any:
        """The underlying ChromaDB client."""
        return self._client

    def get_or_create_collection(
        self,
        embedding_model: Optional[str] = None,
        embedding_dimensions: Optional[int] = None,
    ) -> Any:
        """
        Get or create the target collection, configuring or validating model metadata.
        """
        if self._collection is not None:
            return self._collection

        col_meta: Dict[str, Any] = {
            "description": "IndiValidate market evidence chunk embeddings",
        }
        if embedding_model:
            col_meta["embedding_model"] = embedding_model
        if embedding_dimensions:
            col_meta["embedding_dimensions"] = embedding_dimensions

        collection = self._client.get_or_create_collection(
            name=self.collection_name,
            metadata=col_meta,
        )

        self._collection = collection
        return collection

    def count(self) -> int:
        """Return the total number of records currently stored in the collection."""
        col = self.get_or_create_collection()
        return col.count()

    def get_collection_info(self) -> Dict[str, Any]:
        """Return metadata, count, and path details for the collection."""
        col = self.get_or_create_collection()
        return {
            "collection_name": self.collection_name,
            "persistence_directory": str(self.persist_directory),
            "count": col.count(),
            "metadata": col.metadata or {},
        }

    def get(
        self,
        ids: Optional[List[str]] = None,
        where: Optional[Dict[str, Any]] = None,
        limit: Optional[int] = None,
        include: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Retrieve stored records from the collection."""
        col = self.get_or_create_collection()
        kwargs: Dict[str, Any] = {}
        if ids is not None:
            kwargs["ids"] = ids
        if where is not None:
            kwargs["where"] = where
        if limit is not None:
            kwargs["limit"] = limit
        if include is not None:
            kwargs["include"] = include

        return col.get(**kwargs)

    def _verify_model_and_dimensions(
        self,
        collection: Any,
        incoming_model: Optional[str],
        incoming_dimensions: Optional[int],
    ) -> None:
        """
        Enforce strict model and dimension consistency between incoming embeddings
        and existing collection configuration.
        """
        existing_meta = collection.metadata or {}
        existing_model = existing_meta.get("embedding_model")
        existing_dims = existing_meta.get("embedding_dimensions")

        # If not in collection metadata but collection has items, inspect the first item
        if (existing_model is None or existing_dims is None) and collection.count() > 0:
            sample = collection.get(limit=1, include=["metadatas", "embeddings"])
            if sample.get("metadatas") and sample["metadatas"]:
                first_meta = sample["metadatas"][0] or {}
                if existing_model is None:
                    existing_model = first_meta.get("embedding_model")
                if existing_dims is None:
                    existing_dims = first_meta.get("embedding_dimensions")
            if existing_dims is None and sample.get("embeddings") is not None and len(sample["embeddings"]) > 0:
                existing_dims = len(sample["embeddings"][0])

        # Validate model compatibility
        if existing_model and incoming_model and existing_model != incoming_model:
            raise ValueError(
                f"Model mismatch for collection '{self.collection_name}': collection contains embeddings from "
                f"'{existing_model}', but received embeddings from '{incoming_model}'. "
                f"Mixing different embedding models in the same collection is prohibited."
            )

        # Validate dimension compatibility
        if existing_dims is not None and incoming_dimensions is not None:
            if int(existing_dims) != int(incoming_dimensions):
                raise ValueError(
                    f"Dimension mismatch for collection '{self.collection_name}': collection expects "
                    f"{existing_dims} dimensions, but received embeddings with {incoming_dimensions} dimensions."
                )

        # Update empty collection metadata if model / dimensions are newly provided
        if (existing_model is None or existing_dims is None) and collection.count() == 0:
            updated_meta = dict(existing_meta)
            if incoming_model and "embedding_model" not in updated_meta:
                updated_meta["embedding_model"] = incoming_model
            if incoming_dimensions and "embedding_dimensions" not in updated_meta:
                updated_meta["embedding_dimensions"] = incoming_dimensions
            try:
                collection.modify(metadata=updated_meta)
            except Exception:
                pass

    def store_embeddings(
        self,
        records: List[Union[ChunkEmbeddingRecord, Dict[str, Any]]],
        batch_size: int = 500,
    ) -> Tuple[int, Dict[str, Any]]:
        """
        Persist validated chunk embeddings into ChromaDB with idempotent upserting.

        Parameters:
        - records: List of ChunkEmbeddingRecord models or compatible dictionaries.
        - batch_size: Number of records per ChromaDB upsert call (default: 500).

        Returns:
        - (successfully_stored_count, diagnostics)
        """
        diagnostics: Dict[str, Any] = {
            "total_records_received": len(records) if records else 0,
            "successfully_stored_count": 0,
            "failed_records_count": 0,
            "collection_name": self.collection_name,
            "persistence_directory": str(self.persist_directory),
            "total_collection_count": 0,
            "embedding_model": None,
            "embedding_dimensions": None,
            "batches_processed": 0,
            "issues": [],
        }

        if not records or not isinstance(records, list):
            diagnostics["total_collection_count"] = self.count()
            return 0, diagnostics

        # 1. Determine common incoming model and dimensions
        incoming_models = set()
        incoming_dims = set()

        for rec in records:
            if isinstance(rec, ChunkEmbeddingRecord):
                incoming_models.add(rec.embedding_model)
                incoming_dims.add(rec.embedding_dimensions)
            elif isinstance(rec, dict):
                model_name = rec.get("embedding_model")
                dims = rec.get("embedding_dimensions")
                if not dims and rec.get("embedding"):
                    dims = len(rec["embedding"])
                if model_name:
                    incoming_models.add(model_name)
                if dims:
                    incoming_dims.add(dims)

        if len(incoming_models) > 1:
            raise ValueError(
                f"Mixed embedding models detected in input records: {sorted(list(incoming_models))}. "
                f"All records in a single batch must originate from the same embedding model."
            )

        if len(incoming_dims) > 1:
            raise ValueError(
                f"Mixed embedding dimensions detected in input records: {sorted(list(incoming_dims))}. "
                f"All vectors must have identical dimensions."
            )

        active_model = next(iter(incoming_models)) if incoming_models else None
        active_dims = next(iter(incoming_dims)) if incoming_dims else None

        diagnostics["embedding_model"] = active_model
        diagnostics["embedding_dimensions"] = active_dims

        # 2. Get or create collection and verify model/dimensions
        collection = self.get_or_create_collection(
            embedding_model=active_model,
            embedding_dimensions=active_dims,
        )
        self._verify_model_and_dimensions(collection, active_model, active_dims)

        # 3. Validate each record and isolate failures
        unique_valid_records: Dict[str, Tuple[str, str, List[float], Dict[str, Any]]] = {}

        for item in records:
            if isinstance(item, ChunkEmbeddingRecord):
                cid = item.chunk_id
                doc_id = item.document_id
                txt = item.text
                vec = item.embedding
                meta = dict(item.metadata)
                model_name = item.embedding_model
                dims = item.embedding_dimensions
            elif isinstance(item, dict):
                cid = item.get("chunk_id")
                doc_id = item.get("document_id") or ""
                txt = item.get("text")
                vec = item.get("embedding")
                meta = dict(item.get("metadata", {}))
                model_name = item.get("embedding_model")
                dims = item.get("embedding_dimensions") or (len(vec) if isinstance(vec, list) else None)
            else:
                diagnostics["failed_records_count"] += 1
                diagnostics["issues"].append(f"Invalid record type: {type(item)}")
                continue

            # Basic validation
            if not cid or not isinstance(cid, str):
                diagnostics["failed_records_count"] += 1
                diagnostics["issues"].append("Record missing valid chunk_id")
                continue

            if not txt or not isinstance(txt, str) or not txt.strip():
                diagnostics["failed_records_count"] += 1
                diagnostics["issues"].append(f"Record '{cid}' has empty or whitespace-only text")
                continue

            if not vec or not isinstance(vec, list):
                diagnostics["failed_records_count"] += 1
                diagnostics["issues"].append(f"Record '{cid}' has missing or non-list embedding vector")
                continue

            # Finite numeric validation
            if not all(isinstance(x, (int, float)) and math.isfinite(x) for x in vec):
                diagnostics["failed_records_count"] += 1
                diagnostics["issues"].append(f"Record '{cid}' contains non-finite or non-numeric vector values")
                continue

            # Dimension matching
            if dims is not None and len(vec) != dims:
                diagnostics["failed_records_count"] += 1
                diagnostics["issues"].append(
                    f"Record '{cid}' vector length ({len(vec)}) does not match declared dimensions ({dims})"
                )
                continue

            # Ensure essential provenance keys are preserved in metadata
            meta["chunk_id"] = cid
            if doc_id and "document_id" not in meta:
                meta["document_id"] = doc_id
            if model_name and "embedding_model" not in meta:
                meta["embedding_model"] = model_name
            if dims and "embedding_dimensions" not in meta:
                meta["embedding_dimensions"] = dims

            chroma_meta = serialize_metadata_for_chroma(meta)

            unique_valid_records[cid] = (
                cid,
                txt,
                [float(x) for x in vec],
                chroma_meta,
            )

        valid_items = list(unique_valid_records.values())
        if not valid_items:
            diagnostics["total_collection_count"] = collection.count()
            return 0, diagnostics

        valid_ids = [item[0] for item in valid_items]
        valid_texts = [item[1] for item in valid_items]
        valid_vectors = [item[2] for item in valid_items]
        valid_metadatas = [item[3] for item in valid_items]

        # 4. Upsert in batches to respect database limits
        successfully_stored = 0
        total_valid = len(valid_ids)

        for batch_start in range(0, total_valid, batch_size):
            batch_end = min(batch_start + batch_size, total_valid)
            b_ids = valid_ids[batch_start:batch_end]
            b_texts = valid_texts[batch_start:batch_end]
            b_vecs = valid_vectors[batch_start:batch_end]
            b_metas = valid_metadatas[batch_start:batch_end]

            try:
                collection.upsert(
                    ids=b_ids,
                    documents=b_texts,
                    embeddings=b_vecs,
                    metadatas=b_metas,
                )
                successfully_stored += len(b_ids)
                diagnostics["batches_processed"] += 1
            except Exception as batch_err:
                diagnostics["failed_records_count"] += len(b_ids)
                diagnostics["issues"].append(
                    f"ChromaDB upsert failure on batch {batch_start // batch_size + 1}: {batch_err}"
                )

        diagnostics["successfully_stored_count"] = successfully_stored
        diagnostics["total_collection_count"] = collection.count()

        return successfully_stored, diagnostics


    @staticmethod
    def get_collection_name_for_model(
        base_name: str = DEFAULT_COLLECTION_NAME,
        embedding_model: Optional[str] = None,
        embedding_dimensions: Optional[int] = None,
    ) -> str:
        """Helper to resolve model-isolated collection names."""
        return get_collection_name_for_model(
            base_name=base_name,
            embedding_model=embedding_model,
            embedding_dimensions=embedding_dimensions,
        )


# ------------------------------------------------------------------
# 3. Top-Level Functional API
# ------------------------------------------------------------------

def store_chunk_embeddings(
    records: List[Union[ChunkEmbeddingRecord, Dict[str, Any]]],
    persist_directory: Optional[Union[str, Path]] = None,
    collection_name: Optional[str] = None,
    store: Optional[ChromaVectorStore] = None,
    batch_size: int = 500,
) -> Tuple[int, Dict[str, Any]]:
    """
    Store chunk embedding records into ChromaDB using a new or provided ChromaVectorStore.
    If collection_name is not provided and store is None, automatically isolates the collection
    by embedding model and dimensions to prevent cross-model vector collisions.

    Returns:
    - (successfully_stored_count, diagnostics)
    """
    if store is None:
        target_col = collection_name
        if target_col is None:
            m_name = None
            d_dim = None
            if records:
                first = records[0]
                if isinstance(first, ChunkEmbeddingRecord):
                    m_name = first.embedding_model
                    d_dim = first.embedding_dimensions
                elif isinstance(first, dict):
                    m_name = first.get("embedding_model")
                    d_dim = first.get("embedding_dimensions")
            target_col = get_collection_name_for_model(DEFAULT_COLLECTION_NAME, m_name, d_dim)

        store = ChromaVectorStore(
            persist_directory=persist_directory,
            collection_name=target_col,
        )

    return store.store_embeddings(records, batch_size=batch_size)
