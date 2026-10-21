"""
rag
---
Retrieval-Augmented Generation (RAG) components for IndiValidate.
"""

from app.rag.document_builder import RetrievalDocument, build_retrieval_documents
from app.rag.chunker import DocumentChunk, ChunkerConfig, ChunkStrategy, chunk_documents
from app.rag.embeddings import (
    ChunkEmbeddingRecord,
    EmbeddingProvider,
    GoogleEmbeddingProvider,
    TestEmbeddingProvider,
    generate_chunk_embeddings,
)
from app.rag.vector_store import (
    DEFAULT_COLLECTION_NAME,
    DEFAULT_PERSIST_DIRECTORY,
    ChromaVectorStore,
    get_collection_name_for_model,
    serialize_metadata_for_chroma,
    store_chunk_embeddings,
)
from app.rag.retriever import (
    EvidenceRetriever,
    RetrievalFilter,
    RetrievalResult,
    RetrievedChunk,
    build_evidence_context,
    retrieve_evidence,
)

__all__ = [
    "RetrievalDocument",
    "build_retrieval_documents",
    "DocumentChunk",
    "ChunkerConfig",
    "ChunkStrategy",
    "chunk_documents",
    "ChunkEmbeddingRecord",
    "EmbeddingProvider",
    "GoogleEmbeddingProvider",
    "TestEmbeddingProvider",
    "generate_chunk_embeddings",
    "DEFAULT_COLLECTION_NAME",
    "DEFAULT_PERSIST_DIRECTORY",
    "ChromaVectorStore",
    "get_collection_name_for_model",
    "serialize_metadata_for_chroma",
    "store_chunk_embeddings",
    "RetrievedChunk",
    "RetrievalFilter",
    "RetrievalResult",
    "EvidenceRetriever",
    "build_evidence_context",
    "retrieve_evidence",
]
