"""
schemas package
---------------
Unified schemas and normalizers for market analyzer evidence layer.
"""

from app.schemas.evidence import (
    EvidenceRecord,
    EvidenceType,
    GeographyScope,
    SourceType,
)
from app.schemas.normalizer import (
    normalize_all_evidence,
    normalize_census_records,
    normalize_plfs_records,
    normalize_reddit_records,
    normalize_trends_records,
)
from app.schemas.cleaner import (
    clean_evidence,
    clean_text,
    decompose_multi_metric_record,
    standardize_geography,
    validate_numeric_value,
)

__all__ = [
    "EvidenceRecord",
    "EvidenceType",
    "GeographyScope",
    "SourceType",
    "normalize_all_evidence",
    "normalize_census_records",
    "normalize_plfs_records",
    "normalize_reddit_records",
    "normalize_trends_records",
    "clean_evidence",
    "clean_text",
    "decompose_multi_metric_record",
    "standardize_geography",
    "validate_numeric_value",
]
