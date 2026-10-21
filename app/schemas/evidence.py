"""
evidence.py
-----------
Common evidence schema for IndiValidate research layer (Phase 1, Step 2).

Defines validated Pydantic models for representing normalized evidence
across all four research sources:
    1. Reddit (historical Kaggle dataset)
    2. Google Trends (relative search interest index)
    3. Census 2011 (official PCA, C-08, C-08A datasets)
    4. PLFS 2025 (official MoSPI unit-level microdata)
"""

from enum import Enum
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field, ConfigDict


class SourceType(str, Enum):
    """Origin source of the research evidence."""
    REDDIT = "reddit"
    GOOGLE_TRENDS = "google_trends"
    CENSUS = "census"
    PLFS = "plfs"


class EvidenceType(str, Enum):
    """Categorical classification of the evidence record."""
    DISCUSSION = "discussion"
    SEARCH_INTEREST = "search_interest"
    DEMOGRAPHIC_STATISTIC = "demographic_statistic"
    LABOUR_STATISTIC = "labour_statistic"
    EARNINGS_STATISTIC = "earnings_statistic"
    EDUCATION_STATISTIC = "education_statistic"
    HOUSEHOLD_STATISTIC = "household_statistic"
    INDUSTRY_STATISTIC = "industry_statistic"


class GeographyScope(BaseModel):
    """
    Standardized geographic scope of an evidence observation.
    Fields are optional to accommodate sources without localized geography
    (e.g., historical Reddit discussions).
    """
    model_config = ConfigDict(extra="forbid")

    country: Optional[str] = Field(default="India", description="Country name")
    state: Optional[str] = Field(default=None, description="State or Union Territory name")
    district: Optional[str] = Field(default=None, description="District name")
    rural_urban: Optional[str] = Field(default=None, description="Sector context: Total, Rural, or Urban")
    level: Optional[str] = Field(default=None, description="Granularity level: national, state, or district")


class EvidenceRecord(BaseModel):
    """
    Unified common evidence record representing an observation from any source.
    Preserves exact numeric values, provenance, and source-specific semantics
    without prematurely erasing structured fields into plain strings.
    """
    model_config = ConfigDict(extra="forbid")

    evidence_id: str = Field(
        description="Deterministic identifier for this evidence record"
    )
    source: SourceType = Field(
        description="Origin evidence source: reddit, google_trends, census, or plfs"
    )
    evidence_type: EvidenceType = Field(
        description="Categorical type of evidence"
    )
    title: str = Field(
        description="Short human-readable title describing the observation"
    )
    content: str = Field(
        description="Readable factual explanation or text excerpt of the evidence"
    )
    value: Optional[Union[float, int, str, Dict[str, Any], List[Any]]] = Field(
        default=None,
        description="Structured numeric or categorical value (preserved in native format)"
    )
    unit: Optional[str] = Field(
        default=None,
        description="Measurement unit where applicable (e.g. percent, INR/month, people)"
    )
    geography: Optional[GeographyScope] = Field(
        default=None,
        description="Geographic scope of the observation where known"
    )
    time_period: Optional[str] = Field(
        default=None,
        description="Reference period represented by the observation (e.g. '2011', '2025')"
    )
    retrieved_at: Optional[str] = Field(
        default=None,
        description="Timestamp when evidence was retrieved or created"
    )
    provenance: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Original dataset, table, URL, or citation details"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Source-specific fields that cannot be represented adequately by common fields"
    )
    relevance: Optional[str] = Field(
        default=None,
        description="Deterministic relevance status: unreviewed, potentially_relevant, irrelevant, or insufficient_context"
    )
    limitations: List[str] = Field(
        default_factory=list,
        description="Known caveats, granularity limitations, or interpretation constraints"
    )
