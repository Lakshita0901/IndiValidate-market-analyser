"""
document_builder.py
-------------------
Converts cleaned evidence records into retrieval-ready documents (Step 4).

Transforms validated, standardized, and atomic EvidenceRecords into structured
RetrievalDocument instances suitable for downstream chunking, embeddings, and ChromaDB:
  1. Generates readable, factual, self-contained text tailored to each evidence source.
  2. Preserves all structured metadata required for source attribution, filtering, and citation.
  3. Enforces deterministic, stable document identifiers.
  4. Manages relevance flags (transparently excluding off-topic records from the default
     retrieval set while preserving audit records).
  5. Provides serialization helpers compatible with vector databases (e.g., ChromaDB).
"""

import json
from hashlib import sha256
from typing import Any, Dict, List, Optional, Tuple, Union
from pydantic import BaseModel, Field, ConfigDict

from app.schemas.evidence import (
    EvidenceRecord,
    EvidenceType,
    GeographyScope,
    SourceType,
)


# ------------------------------------------------------------------
# 1. Document Representation
# ------------------------------------------------------------------

class RetrievalDocument(BaseModel):
    """
    Retrieval-ready document representation prepared for vector search and RAG.
    Contains readable, self-contained factual text and structured metadata
    for attribution, filtering, and citations.
    """
    model_config = ConfigDict(extra="forbid")

    document_id: str = Field(
        description="Stable deterministic document identifier"
    )
    text: str = Field(
        description="Readable, factual, self-contained textual content derived from evidence"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Structured attributes for retrieval filtering, source attribution, and citation"
    )

    def to_chroma_metadata(self) -> Dict[str, Union[str, int, float, bool]]:
        """
        Export metadata formatted strictly for vector databases such as ChromaDB.
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
# 2. Formatting Helpers
# ------------------------------------------------------------------

def format_geography(geo: Optional[GeographyScope]) -> str:
    """
    Format GeographyScope into a standardized descriptive string.
    Never guesses missing fields.
    """
    if geo is None:
        return "National (India)"

    parts: List[str] = []
    if geo.district:
        parts.append(f"{geo.district} District")
    if geo.state:
        parts.append(geo.state)
    if geo.country:
        parts.append(geo.country)

    base = ", ".join(parts) if parts else "India"

    extras: List[str] = []
    if geo.rural_urban and geo.rural_urban != "Total":
        extras.append(f"{geo.rural_urban} sector")
    if geo.level and geo.level.lower() != "national":
        extras.append(f"{geo.level} level")

    if extras:
        return f"{base} ({', '.join(extras)})"
    return base



def format_value(value: Any, unit: Optional[str]) -> str:
    """
    Format numeric or categorical values with proper units and formatting.
    Never invents missing values or units.
    """
    if value is None:
        return "Not reported"

    if isinstance(value, int):
        val_str = f"{value:,}"
    elif isinstance(value, float):
        # Clean display: no trailing zeroes if whole number, else 2 decimal places
        val_str = f"{value:,.2f}" if value % 1 != 0 else f"{int(value):,}"
    elif isinstance(value, str):
        val_str = value
    else:
        val_str = str(value)

    if not unit:
        return val_str

    if unit == "percent":
        return f"{val_str}%"
    elif unit == "INR/month":
        return f"INR {val_str}/month"
    elif unit == "relative_interest_index":
        return f"{val_str}/100 index"
    elif unit == "upvotes":
        return f"{val_str} upvotes"
    elif unit == "persons_per_household":
        return f"{val_str} persons per household"
    elif unit in ("people", "households"):
        return f"{val_str} {unit}"
    else:
        return f"{val_str} {unit}"


# ------------------------------------------------------------------
# 3. Source-Aware Text Generation
# ------------------------------------------------------------------

def _build_reddit_text(rec: EvidenceRecord) -> str:
    """
    Build self-contained, factual text for a Reddit discussion observation.
    Preserves discussion content, subreddit, post title, score, and limitations.
    Does not invent market demand or extrapolate customer preferences.
    """
    sub = rec.metadata.get("subreddit")
    post_title = rec.metadata.get("post_title") or rec.title
    post_text = rec.metadata.get("post_text") or ""
    score = rec.metadata.get("score") if rec.metadata.get("score") is not None else rec.value
    kw_matched = rec.metadata.get("keywords_matched", [])
    created_at = rec.time_period or rec.metadata.get("created_at")

    sub_str = f"r/{sub}" if sub else "Reddit discussion forum"

    parts: List[str] = [
        f"Historical Reddit Discussion Record [{sub_str}].",
        f"Post Title: \"{post_title}\".",
    ]

    if post_text:
        parts.append(f"Discussion Content: \"{post_text}\".")
    elif rec.content and rec.content != post_title:
        parts.append(f"Discussion Excerpt: \"{rec.content}\".")

    if score is not None:
        parts.append(f"Community Engagement: {score} upvotes.")
    if created_at:
        parts.append(f"Observation Timestamp: {created_at}.")
    if kw_matched:
        kw_str = ", ".join(str(k) for k in kw_matched)
        parts.append(f"Keywords Matched: {kw_str}.")

    parts.append(
        "Observation Context: Qualitative user discussion retrieved from archived Kaggle Reddit dataset. "
        "Represents individual subjective experience; does not establish quantified market size, consumer demand, or willingness to pay."
    )

    return " ".join(parts)


def _build_trends_text(rec: EvidenceRecord) -> str:
    """
    Build self-contained, factual text for a Google Trends observation.
    Explicitly states relative search interest (0-100), timeframe, geo, and trend direction.
    Never presents relative interest scores as absolute search volumes.
    """
    keyword = rec.metadata.get("keyword") or rec.title
    geo_str = format_geography(rec.geography) or rec.metadata.get("geo_code") or "India"
    timeframe = rec.time_period or rec.metadata.get("timeframe") or "Observation period"
    latest_val = rec.metadata.get("latest_value", rec.value)
    avg_val = rec.metadata.get("average_value")
    peak_val = rec.metadata.get("peak_value")
    trend_dir = rec.metadata.get("trend_direction", "unknown")
    cache_hit = rec.metadata.get("cache_hit", False)
    cache_age = rec.metadata.get("cache_age_seconds")

    parts: List[str] = [
        f"Google Trends Search Interest Observation for '{keyword}'.",
        f"Geographic Scope: {geo_str}.",
        f"Time Period: {timeframe}.",
        f"Normalized Relative Search Interest: Latest score = {latest_val}/100.",
    ]

    if avg_val is not None:
        parts.append(f"Period Average Score: {avg_val}/100.")
    if peak_val is not None:
        parts.append(f"Peak Score Observed: {peak_val}/100.")

    parts.append(f"Trend Direction: {trend_dir}.")

    if cache_hit:
        parts.append(f"Data Origin: Local cache record (age: {cache_age} seconds).")

    parts.append(
        "Interpretation Context: Values represent normalized relative search interest on a 0-100 scale "
        "relative to peak popularity in the designated region and timeframe. "
        "This metric does NOT represent absolute search volume or total query count."
    )

    return " ".join(parts)


def _build_census_text(rec: EvidenceRecord) -> str:
    """
    Build self-contained, factual text for an official Census 2011 record.
    Includes reference benchmark year (2011), geographic scope, metric, value, unit,
    and state-level fallback notice where applicable.
    """
    indicator = rec.title
    geo_str = format_geography(rec.geography)
    val_str = format_value(rec.value, rec.unit)
    ref_year = rec.time_period or "2011"
    table_prov = (rec.provenance or {}).get("dataset") or rec.metadata.get("table") or "Census 2011 Official Table"
    is_fallback = bool(rec.metadata.get("is_state_fallback", False))

    parts: List[str] = [
        f"Census 2011 Demographic Record: {indicator}.",
        f"Geographic Scope: {geo_str}.",
        f"Observed Metric Value: {val_str}.",
        f"Reference Benchmark Year: {ref_year}.",
        f"Data Provenance: {table_prov}.",
    ]

    if is_fallback:
        parts.append(
            "Geographic Fallback Notice: District-level data was not available for this table; "
            "observation reflects state-level aggregate fallback data."
        )

    if rec.content and val_str not in rec.content:
        parts.append(f"Reported Summary: {rec.content}.")

    parts.append(
        "Source Authority: Registrar General and Census Commissioner of India. "
        "Represents official decennial enumeration benchmark; does not reflect subsequent population growth."
    )

    return " ".join(parts)


def _build_plfs_text(rec: EvidenceRecord) -> str:
    """
    Build self-contained, factual text for an official PLFS 2025 record.
    Includes survey reference period, geographic scope, metric, value, unit,
    survey-weighted estimate context, and sample-size metadata where available.
    """
    indicator = rec.title
    geo_str = format_geography(rec.geography)
    val_str = format_value(rec.value, rec.unit)
    ref_period = rec.time_period or "2025 (Annual)"
    prov = rec.provenance or {}
    survey_name = prov.get("survey", "Periodic Labour Force Survey (PLFS) 2025")
    sample_size = rec.metadata.get("sample_size") or prov.get("sample_size_persons")
    pop_base = rec.metadata.get("benchmark_population", "Age 15+ (Working Age population)")
    is_weighted = rec.metadata.get("survey_weighted", True)

    parts: List[str] = [
        f"PLFS 2025 Official Labour Record: {indicator}.",
        f"Geographic Scope: {geo_str}.",
        f"Survey Estimate: {val_str}.",
        f"Survey Reference Period: {ref_period}.",
        f"Estimation Context: {'Survey-weighted' if is_weighted else 'Unweighted'} estimate from MoSPI microdata based on {pop_base}.",
    ]

    if sample_size:
        parts.append(f"Survey Sample Size: {sample_size:,} respondents.")

    if rec.content and val_str not in rec.content:
        parts.append(f"Reported Summary: {rec.content}.")

    parts.append(
        "Source Authority: Ministry of Statistics and Programme Implementation (MoSPI), Government of India. "
        "Represents sample survey estimates, not a full census enumeration."
    )

    return " ".join(parts)


# ------------------------------------------------------------------
# 4. Structured Metadata Builder
# ------------------------------------------------------------------

def _build_document_metadata(rec: EvidenceRecord, doc_id: str) -> Dict[str, Any]:
    """
    Build a comprehensive structured metadata dictionary preserving all fields
    required for source attribution, filtering, and citation.
    Never invents missing metadata or converts missing values to zero.
    """
    source_val = rec.source.value if hasattr(rec.source, "value") else str(rec.source)
    type_val = rec.evidence_type.value if hasattr(rec.evidence_type, "value") else str(rec.evidence_type)
    relevance_val = rec.relevance or "unreviewed"
    is_ready = relevance_val != "irrelevant"

    meta: Dict[str, Any] = {
        "document_id": doc_id,
        "evidence_id": rec.evidence_id,
        "source": source_val,
        "evidence_type": type_val,
        "title": rec.title,
        "value": rec.value,
        "unit": rec.unit,
        "time_period": rec.time_period,
        "retrieved_at": rec.retrieved_at,
        "relevance": relevance_val,
        "relevance_reason": rec.metadata.get("relevance_reason"),
        "is_retrieval_ready": is_ready,
    }

    # Geography fields
    if rec.geography:
        meta["country"] = rec.geography.country
        meta["state"] = rec.geography.state
        meta["district"] = rec.geography.district
        meta["rural_urban"] = rec.geography.rural_urban
        meta["geo_level"] = rec.geography.level
        meta["formatted_geography"] = format_geography(rec.geography)
    else:
        meta["country"] = None
        meta["state"] = None
        meta["district"] = None
        meta["rural_urban"] = None
        meta["geo_level"] = None
        meta["formatted_geography"] = None

    # Source-specific attributes
    if rec.source == SourceType.REDDIT:
        meta["subreddit"] = rec.metadata.get("subreddit")
        meta["post_url"] = (rec.provenance or {}).get("url")
        meta["post_score"] = rec.metadata.get("score")
        meta["keywords_matched"] = rec.metadata.get("keywords_matched", [])

    elif rec.source == SourceType.GOOGLE_TRENDS:
        meta["keyword"] = rec.metadata.get("keyword")
        meta["geo_code"] = rec.metadata.get("geo_code")
        meta["trend_direction"] = rec.metadata.get("trend_direction")
        meta["latest_value"] = rec.metadata.get("latest_value")
        meta["average_value"] = rec.metadata.get("average_value")
        meta["peak_value"] = rec.metadata.get("peak_value")
        meta["is_cached"] = rec.metadata.get("cache_hit", False)
        meta["cache_age_seconds"] = rec.metadata.get("cache_age_seconds")

    elif rec.source == SourceType.CENSUS:
        meta["census_table"] = (rec.provenance or {}).get("dataset") or rec.metadata.get("table")
        meta["is_state_fallback"] = bool(rec.metadata.get("is_state_fallback", False))
        meta["census_year"] = (rec.provenance or {}).get("census_year", 2011)

    elif rec.source == SourceType.PLFS:
        meta["is_survey_weighted"] = bool(rec.metadata.get("survey_weighted", True))
        meta["sample_size"] = rec.metadata.get("sample_size") or (rec.provenance or {}).get("sample_size_persons")
        meta["population_base"] = rec.metadata.get("benchmark_population", "Age 15+")
        meta["survey_name"] = (rec.provenance or {}).get("survey", "PLFS 2025")

    # Limitations & Provenance
    meta["limitations"] = rec.limitations or []
    meta["provenance"] = rec.provenance or {}
    meta["raw_metadata"] = rec.metadata or {}

    return meta


# ------------------------------------------------------------------
# 5. Master Document Builder
# ------------------------------------------------------------------

def build_retrieval_documents(
    records: Optional[List[Union[EvidenceRecord, Dict[str, Any]]]],
    include_irrelevant: bool = False,
) -> Tuple[List[RetrievalDocument], Dict[str, Any]]:
    """
    Master entrypoint for Step 4: Convert Cleaned Evidence into Retrieval-Ready Documents.

    Converts atomic EvidenceRecords into RetrievalDocuments.
    Preserves readable factual text and structured metadata suitable for vector retrieval,
    filtering, and source citation.

    Parameters:
      records: List of cleaned EvidenceRecord instances or equivalent dictionaries.
      include_irrelevant: If False (default), records flagged with relevance='irrelevant'
                          are excluded from the returned collection to prevent RAG index
                          contamination, but are preserved in diagnostics. If True,
                          they are included with is_retrieval_ready=False.

    Returns:
      (documents, diagnostics)
    """
    diagnostics: Dict[str, Any] = {
        "input_records_count": 0,
        "total_documents_created": 0,
        "retrieval_ready_count": 0,
        "excluded_irrelevant_count": 0,
        "by_source": {},
        "by_evidence_type": {},
        "excluded_irrelevant_documents": [],
        "issues": [],
    }

    if not records or not isinstance(records, list):
        return [], diagnostics

    diagnostics["input_records_count"] = len(records)
    documents: List[RetrievalDocument] = []

    for item in records:
        # Validate or parse into EvidenceRecord
        if isinstance(item, dict):
            try:
                rec = EvidenceRecord.model_validate(item)
            except Exception as e:
                diagnostics["issues"].append(f"Failed to validate dict record into EvidenceRecord: {e}")
                continue
        elif isinstance(item, EvidenceRecord):
            rec = item
        else:
            diagnostics["issues"].append(f"Skipped non-record item of type {type(item)}")
            continue

        try:
            # Deterministic stable document ID
            if rec.evidence_id:
                doc_id = f"doc_{rec.evidence_id}"
            else:
                digest = sha256(f"{rec.source}|{rec.title}|{rec.content}".encode("utf-8")).hexdigest()[:16]
                doc_id = f"doc_{digest}"

            # Source-specific factual text generation
            if rec.source == SourceType.REDDIT:
                doc_text = _build_reddit_text(rec)
            elif rec.source == SourceType.GOOGLE_TRENDS:
                doc_text = _build_trends_text(rec)
            elif rec.source == SourceType.CENSUS:
                doc_text = _build_census_text(rec)
            elif rec.source == SourceType.PLFS:
                doc_text = _build_plfs_text(rec)
            else:
                # Fallback for generic or custom sources
                doc_text = f"Observation: {rec.title}. Content: {rec.content}."

            # Structured metadata
            doc_meta = _build_document_metadata(rec, doc_id)

            doc = RetrievalDocument(
                document_id=doc_id,
                text=doc_text,
                metadata=doc_meta,
            )

            # Update metrics
            src_key = str(rec.source.value if hasattr(rec.source, "value") else rec.source)
            type_key = str(rec.evidence_type.value if hasattr(rec.evidence_type, "value") else rec.evidence_type)
            diagnostics["by_source"][src_key] = diagnostics["by_source"].get(src_key, 0) + 1
            diagnostics["by_evidence_type"][type_key] = diagnostics["by_evidence_type"].get(type_key, 0) + 1
            diagnostics["total_documents_created"] += 1

            # Relevance handling
            is_irrelevant = (rec.relevance == "irrelevant")
            if is_irrelevant:
                diagnostics["excluded_irrelevant_count"] += 1
                diagnostics["excluded_irrelevant_documents"].append({
                    "document_id": doc_id,
                    "title": rec.title,
                    "relevance_reason": doc_meta.get("relevance_reason"),
                })
                if not include_irrelevant:
                    # Exclude from default retrieval set
                    continue

            diagnostics["retrieval_ready_count"] += 1
            documents.append(doc)

        except Exception as e:
            diagnostics["issues"].append(f"Error converting record '{rec.title}' to document: {e}")
            continue

    return documents, diagnostics
