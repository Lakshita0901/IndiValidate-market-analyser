"""
chunker.py
----------
Source-aware chunking layer for IndiValidate research pipeline (Step 5).

Converts RetrievalDocuments into retrieval-friendly DocumentChunks:
  1. Atomic statistical preservation: Keeps structured Census, PLFS, and Google Trends
     observations intact whenever they fit within the configured character threshold.
  2. Narrative boundary-aware splitting: Splits long Reddit discussions along paragraph,
     sentence, and word boundaries with configurable overlap, prepending thread context.
  3. Strict provenance & metadata inheritance: Every chunk inherits source, geography,
     period, units, and limitations with stable deterministic IDs.
  4. Eligibility enforcement: Skips records flagged as is_retrieval_ready=False by default,
     maintaining explicit diagnostic audit trails.
  5. Local & deterministic: Zero external API or LLM dependencies.
"""

import json
import re
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, Union
from pydantic import BaseModel, Field, ConfigDict, model_validator

from app.rag.document_builder import RetrievalDocument


# ------------------------------------------------------------------
# 1. Chunking Strategy Enum & Configuration
# ------------------------------------------------------------------

class ChunkStrategy(str, Enum):
    """Strategy employed to generate a chunk from a retrieval document."""
    ATOMIC_PASSTHROUGH = "atomic_passthrough"
    STRUCTURED_SPLIT = "structured_split"
    SLIDING_WINDOW_TEXT = "sliding_window_text"
    FALLBACK_SPLIT = "fallback_split"


class ChunkerConfig(BaseModel):
    """
    Configuration settings for source-aware chunking.
    All size units are explicitly in characters (not tokens).
    """
    model_config = ConfigDict(extra="forbid")

    max_chunk_chars: int = Field(
        default=1200,
        gt=0,
        description="Maximum character length per chunk (e.g. 1200 chars ~ 250-300 words)"
    )
    chunk_overlap_chars: int = Field(
        default=200,
        ge=0,
        description="Character overlap between consecutive chunks for long narrative text (must be < max_chunk_chars)"
    )
    min_chunk_chars: int = Field(
        default=30,
        ge=0,
        description="Minimum character length for a chunk to be considered useful; prevents tiny orphaned fragments"
    )

    @model_validator(mode="after")
    def validate_overlap(self) -> "ChunkerConfig":
        if self.chunk_overlap_chars >= self.max_chunk_chars:
            raise ValueError(
                f"chunk_overlap_chars ({self.chunk_overlap_chars}) must be strictly less than "
                f"max_chunk_chars ({self.max_chunk_chars})"
            )
        if self.min_chunk_chars > self.max_chunk_chars:
            raise ValueError(
                f"min_chunk_chars ({self.min_chunk_chars}) cannot exceed max_chunk_chars ({self.max_chunk_chars})"
            )
        return self


# ------------------------------------------------------------------
# 2. DocumentChunk Model
# ------------------------------------------------------------------

class DocumentChunk(BaseModel):
    """
    Typed chunk model ready for downstream embedding, retrieval, and vector storage.
    Preserves parent document traceability, index, strategy, and full structured metadata.
    """
    model_config = ConfigDict(extra="forbid")

    chunk_id: str = Field(
        description="Deterministic stable chunk identifier (e.g. {document_id}_c{chunk_index})"
    )
    document_id: str = Field(
        description="Parent retrieval document identifier"
    )
    chunk_index: int = Field(
        ge=0,
        description="Zero-based index of this chunk within its parent document"
    )
    text: str = Field(
        description="Self-contained textual content of the chunk"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Inherited source, provenance, and chunk-specific attributes"
    )
    chunking_strategy: str = Field(
        description="Chunking policy used to produce this chunk"
    )
    char_count: int = Field(
        ge=0,
        description="Length of the chunk text in characters"
    )

    def to_chroma_metadata(self) -> Dict[str, Union[str, int, float, bool]]:
        """
        Export chunk metadata formatted strictly for vector databases such as ChromaDB.
        ChromaDB requires metadata values to be primitive types: str, int, float, or bool.
        Complex structures (lists, dicts) are converted to JSON strings.
        None values are omitted.
        """
        chroma_meta: Dict[str, Union[str, int, float, bool]] = {}
        for key, val in self.metadata.items():
            if val is None:
                continue
            elif isinstance(val, (int, float, str, bool)):
                chroma_meta[key] = val
            elif isinstance(val, (list, dict)):
                chroma_meta[key] = json.dumps(val)
            else:
                chroma_meta[key] = str(val)
        return chroma_meta


# ------------------------------------------------------------------
# 3. Text Splitting Utilities
# ------------------------------------------------------------------

_SPLIT_REGEX = re.compile(r"(\n\n|\n|[.!?]\s+)")


def _split_into_sentences(text: str) -> List[str]:
    """Split text into sentences or major grammatical units, preserving non-empty segments."""
    raw_segments = re.split(r"(?<=[.!?])\s+", text.strip())
    return [s.strip() for s in raw_segments if s.strip()]


def _split_text_with_overlap(
    text: str,
    max_chars: int,
    overlap_chars: int,
    min_chars: int,
    prefix_context: str = "",
) -> List[str]:
    """
    Split text into chunks not exceeding max_chars, incorporating prefix_context in every chunk.
    Tries to split along paragraph and sentence boundaries, avoiding intra-word or intra-number cuts.
    """
    available_chars = max_chars - len(prefix_context)
    if available_chars <= 50:
        # If prefix is unusually large, reduce prefix or fallback
        available_chars = max(50, max_chars // 2)
        prefix_context = prefix_context[:max_chars - available_chars]

    sentences = _split_into_sentences(text)
    if not sentences:
        return []

    chunks: List[str] = []
    current_sentences: List[str] = []
    current_len = 0

    for sent in sentences:
        sent_len = len(sent)

        # If a single sentence exceeds available_chars, break it at word boundaries
        if sent_len > available_chars:
            if current_sentences:
                chunk_body = " ".join(current_sentences).strip()
                if len(chunk_body) >= min_chars:
                    full_chunk = f"{prefix_context}{chunk_body}".strip()
                    chunks.append(full_chunk)
                current_sentences = []
                current_len = 0

            # Word-level split
            words = sent.split()
            word_buf: List[str] = []
            word_buf_len = 0
            for w in words:
                if word_buf_len + len(w) + 1 > available_chars and word_buf:
                    wb_text = " ".join(word_buf).strip()
                    if len(wb_text) >= min_chars:
                        chunks.append(f"{prefix_context}{wb_text}".strip())
                    word_buf = [w]
                    word_buf_len = len(w)
                else:
                    word_buf.append(w)
                    word_buf_len += len(w) + 1
            if word_buf:
                wb_text = " ".join(word_buf).strip()
                if len(wb_text) >= min_chars:
                    chunks.append(f"{prefix_context}{wb_text}".strip())
            continue

        # Check if adding this sentence exceeds capacity
        new_len = current_len + (sent_len + 1 if current_sentences else sent_len)
        if new_len > available_chars and current_sentences:
            chunk_body = " ".join(current_sentences).strip()
            if len(chunk_body) >= min_chars:
                full_chunk = f"{prefix_context}{chunk_body}".strip()
                chunks.append(full_chunk)

            # Implement overlap by keeping trailing sentences
            overlap_sentences: List[str] = []
            overlap_len = 0
            for prev_sent in reversed(current_sentences):
                if overlap_len + len(prev_sent) + 1 <= overlap_chars:
                    overlap_sentences.insert(0, prev_sent)
                    overlap_len += len(prev_sent) + 1
                else:
                    break

            current_sentences = overlap_sentences + [sent]
            current_len = sum(len(s) for s in current_sentences) + (len(current_sentences) - 1)
        else:
            current_sentences.append(sent)
            current_len = new_len

    if current_sentences:
        chunk_body = " ".join(current_sentences).strip()
        if len(chunk_body) >= min_chars:
            full_chunk = f"{prefix_context}{chunk_body}".strip()
            chunks.append(full_chunk)

    return chunks


# ------------------------------------------------------------------
# 4. Source-Aware Chunking Policies
# ------------------------------------------------------------------

def _chunk_structured_document(
    doc: RetrievalDocument,
    config: ChunkerConfig,
) -> List[Tuple[str, ChunkStrategy]]:
    """
    Policy for Census, PLFS, and Google Trends structured statistics.
    Preserves the entire atomic observation together whenever it fits within max_chunk_chars.
    If unusually long, splits on sentence boundaries and prepends the key identifier header.
    """
    text = doc.text.strip()
    if not text:
        return []

    # Fits entirely in configured maximum size: atomic passthrough
    if len(text) <= config.max_chunk_chars:
        return [(text, ChunkStrategy.ATOMIC_PASSTHROUGH)]

    # Oversized structured document: repeat essential header context
    # Extract indicator and geographic scope if present in first sentence
    sentences = _split_into_sentences(text)
    header = ""
    body_sentences = sentences
    if len(sentences) >= 2:
        # Use first sentence as standard header context
        header = f"{sentences[0]} "
        body_sentences = sentences[1:]

    body_text = " ".join(body_sentences).strip()
    split_chunks = _split_text_with_overlap(
        text=body_text,
        max_chars=config.max_chunk_chars,
        overlap_chars=config.chunk_overlap_chars,
        min_chars=config.min_chunk_chars,
        prefix_context=header,
    )

    if not split_chunks:
        return [(text, ChunkStrategy.STRUCTURED_SPLIT)]

    return [(c, ChunkStrategy.STRUCTURED_SPLIT) for c in split_chunks]


def _chunk_reddit_document(
    doc: RetrievalDocument,
    config: ChunkerConfig,
) -> List[Tuple[str, ChunkStrategy]]:
    """
    Policy for Reddit discussion records.
    If within size, keeps as single chunk.
    If long discussion text, extracts thread context (subreddit & post title)
    and splits body using sliding window with configurable overlap.
    """
    text = doc.text.strip()
    if not text:
        return []

    if len(text) <= config.max_chunk_chars:
        return [(text, ChunkStrategy.ATOMIC_PASSTHROUGH)]

    # Extract subreddit and title context to prefix each split chunk
    sub = doc.metadata.get("subreddit")
    post_title = doc.metadata.get("post_title") or doc.metadata.get("title", "")
    sub_str = f"r/{sub}" if sub else "Reddit"
    header_context = f"[Context: {sub_str} - \"{post_title}\"] "

    split_chunks = _split_text_with_overlap(
        text=text,
        max_chars=config.max_chunk_chars,
        overlap_chars=config.chunk_overlap_chars,
        min_chars=config.min_chunk_chars,
        prefix_context=header_context,
    )

    if not split_chunks:
        return [(text, ChunkStrategy.SLIDING_WINDOW_TEXT)]

    return [(c, ChunkStrategy.SLIDING_WINDOW_TEXT) for c in split_chunks]


def _chunk_generic_document(
    doc: RetrievalDocument,
    config: ChunkerConfig,
) -> List[Tuple[str, ChunkStrategy]]:
    """General fallback for other evidence types."""
    text = doc.text.strip()
    if not text:
        return []

    if len(text) <= config.max_chunk_chars:
        return [(text, ChunkStrategy.ATOMIC_PASSTHROUGH)]

    split_chunks = _split_text_with_overlap(
        text=text,
        max_chars=config.max_chunk_chars,
        overlap_chars=config.chunk_overlap_chars,
        min_chars=config.min_chunk_chars,
        prefix_context="",
    )

    if not split_chunks:
        return [(text, ChunkStrategy.FALLBACK_SPLIT)]

    return [(c, ChunkStrategy.FALLBACK_SPLIT) for c in split_chunks]


# ------------------------------------------------------------------
# 5. Master Chunking Function
# ------------------------------------------------------------------

def chunk_documents(
    documents: Optional[List[Union[RetrievalDocument, Dict[str, Any]]]],
    config: Optional[ChunkerConfig] = None,
    include_ineligible: bool = False,
) -> Tuple[List[DocumentChunk], Dict[str, Any]]:
    """
    Master entrypoint for Step 5: Source-Aware Chunking.

    Processes RetrievalDocuments and generates typed DocumentChunks adhering to
    source-aware policies and strict metadata inheritance.

    Parameters:
      documents: List of RetrievalDocument instances or serialized document dictionaries.
      config: ChunkerConfig specifying max_chunk_chars, overlap, and min_chars.
      include_ineligible: If False (default), skips records where is_retrieval_ready=False.
                          If True, chunks them while preserving is_retrieval_ready=False.

    Returns:
      (document_chunks, diagnostics)
    """
    if config is None:
        config = ChunkerConfig()

    diagnostics: Dict[str, Any] = {
        "input_documents_count": 0,
        "eligible_documents_count": 0,
        "skipped_ineligible_count": 0,
        "total_chunks_created": 0,
        "by_source": {},
        "by_strategy": {},
        "skipped_documents": [],
        "config": {
            "max_chunk_chars": config.max_chunk_chars,
            "chunk_overlap_chars": config.chunk_overlap_chars,
            "min_chunk_chars": config.min_chunk_chars,
        },
        "issues": [],
    }

    if not documents or not isinstance(documents, list):
        return [], diagnostics

    diagnostics["input_documents_count"] = len(documents)
    chunks: List[DocumentChunk] = []

    for item in documents:
        # 1. Parse into RetrievalDocument safely
        if isinstance(item, dict):
            try:
                doc = RetrievalDocument.model_validate(item)
            except Exception as e:
                diagnostics["issues"].append(f"Failed to parse document dict: {e}")
                continue
        elif isinstance(item, RetrievalDocument):
            doc = item
        else:
            diagnostics["issues"].append(f"Skipped non-document item of type {type(item)}")
            continue

        # 2. Check eligibility (relevance / retrieval_ready)
        is_ready = doc.metadata.get("is_retrieval_ready", True)
        is_irrelevant = (doc.metadata.get("relevance") == "irrelevant")

        if (not is_ready or is_irrelevant) and not include_ineligible:
            diagnostics["skipped_ineligible_count"] += 1
            diagnostics["skipped_documents"].append({
                "document_id": doc.document_id,
                "reason": "is_retrieval_ready is False or relevance is irrelevant",
                "relevance_reason": doc.metadata.get("relevance_reason"),
            })
            continue

        diagnostics["eligible_documents_count"] += 1

        # 3. Discard empty or whitespace-only documents
        clean_text = doc.text.strip()
        if not clean_text or len(clean_text) < config.min_chunk_chars:
            diagnostics["skipped_documents"].append({
                "document_id": doc.document_id,
                "reason": f"Text length ({len(clean_text)}) is below min_chunk_chars ({config.min_chunk_chars})",
            })
            continue

        try:
            source = doc.metadata.get("source", "").lower()

            # 4. Dispatch to source-aware policy
            if source in ("census", "plfs", "google_trends"):
                chunk_tuples = _chunk_structured_document(doc, config)
            elif source == "reddit":
                chunk_tuples = _chunk_reddit_document(doc, config)
            else:
                chunk_tuples = _chunk_generic_document(doc, config)

            # 5. Create DocumentChunk instances
            for idx, (chunk_text, strategy) in enumerate(chunk_tuples):
                stripped = chunk_text.strip()
                if not stripped:
                    continue

                chunk_id = f"{doc.document_id}_c{idx}"

                # Inherit all metadata from parent document
                chunk_meta = dict(doc.metadata)
                chunk_meta["document_id"] = doc.document_id
                chunk_meta["chunk_id"] = chunk_id
                chunk_meta["chunk_index"] = idx
                chunk_meta["chunking_strategy"] = strategy.value
                chunk_meta["char_count"] = len(stripped)

                chunk_obj = DocumentChunk(
                    chunk_id=chunk_id,
                    document_id=doc.document_id,
                    chunk_index=idx,
                    text=stripped,
                    metadata=chunk_meta,
                    chunking_strategy=strategy.value,
                    char_count=len(stripped),
                )

                chunks.append(chunk_obj)

                # Diagnostics updates
                src_key = source or "unknown"
                strat_key = strategy.value
                diagnostics["by_source"][src_key] = diagnostics["by_source"].get(src_key, 0) + 1
                diagnostics["by_strategy"][strat_key] = diagnostics["by_strategy"].get(strat_key, 0) + 1
                diagnostics["total_chunks_created"] += 1

        except Exception as e:
            diagnostics["issues"].append(f"Error chunking document '{doc.document_id}': {e}")
            continue

    return chunks, diagnostics
