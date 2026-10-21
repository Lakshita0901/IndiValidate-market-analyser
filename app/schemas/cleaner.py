"""
cleaner.py
----------
Deterministic cleaning and standardization layer for normalized evidence records (Step 3).

Applies robust data cleaning rules while preserving source semantics:
  1. Text cleaning (whitespace normalization, removal of non-printable control characters).
  2. Multi-metric decomposition (expanding composite statistics into atomic records with individual values and units).
  3. Numeric & unit validation (verifying percentages 0-100, indices 0-100, non-negative counts, reject NaN/Inf).
  4. Geography & time standardization (consistent casing, preserving 2011 and 2025 benchmarks).
  5. Deterministic relevance classification for discussion records (transparently flagging false-positives like r/jobs).
  6. Exact duplicate elimination with stable fingerprinting and diagnostic counts.
"""

import math
import re
from hashlib import sha256
from typing import Any, Dict, List, Optional, Set, Tuple

from app.schemas.evidence import (
    EvidenceRecord,
    EvidenceType,
    GeographyScope,
    SourceType,
)


# ------------------------------------------------------------------
# Off-topic subreddits & terms for heuristic relevance assessment
# ------------------------------------------------------------------

_OFFTOPIC_EMPLOYMENT_SUBREDDITS = {
    "jobs", "resumes", "recruitinghell", "careerguidance",
    "antiwork", "cscareerquestions", "interviewing",
}

_OFFTOPIC_ACADEMIC_SUBREDDITS = {
    "college", "professors", "homeworkhelp", "studentloandefault",
}

_EMPLOYMENT_GRIEVANCE_PATTERNS = [
    r"\bunemployment\b", r"\bfurloughed\b", r"\bgot fired\b",
    r"\blaid off\b", r"\bseverance\b", r"\bcover letter\b",
    r"\bresume review\b", r"\bjob offer\b", r"\bmy manager\b",
]

_ACADEMIC_GRIEVANCE_PATTERNS = [
    r"\bonline classes\b", r"\bexam cheating\b", r"\bmultiple choice question\b",
    r"\btakehome exam\b", r"\bdorm roommate\b", r"\bprofessors?\b",
]

_COMMERCIAL_CONSUMER_PATTERNS = [
    r"\borganic\b", r"\bvegetables?\b", r"\bgrocery\b", r"\bfresh produce\b",
    r"\bdelivery service\b", r"\bordering online\b", r"\bfarm box\b",
    r"\bdoorstep delivery\b", r"\bcustomer experience\b", r"\bpricing\b",
]


# ------------------------------------------------------------------
# 1. Text Cleaning
# ------------------------------------------------------------------

def clean_text(text: Optional[str]) -> str:
    """
    Normalize text:
      - Replace non-printable ASCII control characters with a space.
      - Collapse multiple horizontal spaces and tabs into a single space.
      - Normalize multiple consecutive newlines to at most two.
      - Preserve numbers, meaningful punctuation, negation, quotes, names, and URLs.
    """
    if not text:
        return ""

    # Replace non-printable control characters (\x00-\x08, \x0b, \x0c, \x0e-\x1f, \x7f) with space
    cleaned = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]+", " ", text)

    # Collapse multiple spaces or tabs into a single space
    cleaned = re.sub(r"[^\S\r\n]+", " ", cleaned)

    # Collapse 3+ consecutive newlines into 2
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)

    return cleaned.strip()


# ------------------------------------------------------------------
# 2. Geography Standardization
# ------------------------------------------------------------------

def standardize_geography(geo: Optional[GeographyScope]) -> Optional[GeographyScope]:
    """
    Standardize geography casing and sector naming if present.
    Never invents missing locations or dates.
    """
    if geo is None:
        return None

    state_clean = clean_text(geo.state).title() if geo.state else None
    district_clean = clean_text(geo.district).title() if geo.district else None

    # Known Census spelling standardizations (e.g., 'Ahmadabad' -> 'Ahmedabad')
    if district_clean == "Ahmadabad":
        district_clean = "Ahmedabad"

    sector_clean = None
    if geo.rural_urban:
        s_lower = geo.rural_urban.strip().lower()
        if "rural" in s_lower:
            sector_clean = "Rural"
        elif "urban" in s_lower:
            sector_clean = "Urban"
        else:
            sector_clean = "Total"

    level_clean = geo.level.lower().strip() if geo.level else None

    return GeographyScope(
        country=geo.country or "India",
        state=state_clean,
        district=district_clean,
        rural_urban=sector_clean,
        level=level_clean,
    )


# ------------------------------------------------------------------
# 3. Numeric & Unit Validation
# ------------------------------------------------------------------

def validate_numeric_value(
    value: Any,
    unit: Optional[str],
    evidence_type: EvidenceType,
    metadata: Dict[str, Any],
) -> Tuple[bool, Optional[str]]:
    """
    Validate that numeric values conform to their declared unit and evidence type:
      - Rejects NaN, Inf, -Inf.
      - Verifies percentages are strictly within [0.0, 100.0].
      - Verifies relative_interest_index is within [0.0, 100.0].
      - Verifies headcount counts (people, households, upvotes) are >= 0.
      - Verifies earnings are >= 0 unless explicitly marked as reporting business loss.
    Returns:
      (is_valid, error_reason)
    """
    # None value is allowed for qualitative discussions
    if value is None:
        return True, None

    # Handle float / int
    if isinstance(value, (int, float)):
        val_f = float(value)

        # NaN / Inf check
        if math.isnan(val_f) or math.isinf(val_f):
            return False, f"Value {value} is NaN or Infinity."

        # Percentage check
        if unit == "percent":
            if not (0.0 <= val_f <= 100.0):
                return False, f"Percentage value {val_f}% is outside the valid range [0, 100]."

        # Relative interest index check (0-100)
        elif unit == "relative_interest_index":
            if not (0.0 <= val_f <= 100.0):
                return False, f"Relative interest index {val_f} is outside the valid range [0, 100]."

        # Non-negative count checks
        elif unit in ("people", "households", "upvotes", "persons_per_household"):
            if val_f < 0:
                return False, f"Count for unit '{unit}' cannot be negative (got {val_f})."

        # Monthly earnings check
        elif unit == "INR/month":
            # Self-employed earnings may be negative if net loss is documented
            is_self_employed_loss = bool(
                metadata.get("reporting_net_loss_count", 0) > 0 or
                metadata.get("net_loss_count", 0) > 0 or
                "loss" in metadata.get("earnings_type", "").lower()
            )
            if val_f < 0 and not is_self_employed_loss:
                return False, f"Earnings value INR {val_f} is negative without reported business loss."

        return True, None

    # If value is a dict or list (composite), it should be checked by decomposition
    if isinstance(value, (dict, list)):
        return True, None

    # Reject malformed strings if unit suggests numeric value
    if isinstance(value, str) and unit in ("percent", "INR/month", "people", "households", "relative_interest_index"):
        try:
            float(value)
            return True, None
        except ValueError:
            return False, f"Value '{value}' is not a valid number for unit '{unit}'."

    return True, None


# ------------------------------------------------------------------
# 4. Deterministic Relevance Assessment for Discussions
# ------------------------------------------------------------------

def assess_reddit_relevance(
    rec: EvidenceRecord,
    query: str = "",
    keywords: Optional[List[str]] = None,
) -> Tuple[str, str]:
    """
    Deterministically assess relevance of Reddit discussion posts:
      - 'irrelevant': Off-topic subreddit (e.g. r/jobs, r/college) discussing personal employment
        grievances, layoffs, student homework, exam cheating, etc.
      - 'insufficient_context': Body or excerpt is empty or under 25 chars.
      - 'potentially_relevant': Discusses consumer delivery, grocery, organic produce, customer service.
      - 'unreviewed': General discussion mentioning query terms without decisive match.
    Does NOT discard records; returns flag and explainable rationale.
    """
    if rec.source != SourceType.REDDIT:
        return "unreviewed", "Relevance assessment applies primarily to discussion sources."

    subreddit = str(rec.metadata.get("subreddit", "")).lower().strip()
    title = str(rec.metadata.get("post_title", "")).lower()
    text = str(rec.metadata.get("post_text", "")).lower()
    full_text = f"{title} {text}".strip()

    # 1. Insufficient context check
    if len(full_text) < 25:
        return (
            "insufficient_context",
            "Post title and text are too brief (< 25 chars) to determine market relevance.",
        )

    # 2. Check for employment grievance in r/jobs or similar
    if subreddit in _OFFTOPIC_EMPLOYMENT_SUBREDDITS:
        for pat in _EMPLOYMENT_GRIEVANCE_PATTERNS:
            if re.search(pat, full_text):
                return (
                    "irrelevant",
                    f"Post is from job-seeking community (r/{subreddit}) discussing employment/layoff issues ({pat}), not consumer market demand.",
                )

    # 3. Check for student / academic cheating / dorm issues in r/college
    if subreddit in _OFFTOPIC_ACADEMIC_SUBREDDITS:
        for pat in _ACADEMIC_GRIEVANCE_PATTERNS:
            if re.search(pat, full_text):
                return (
                    "irrelevant",
                    f"Post is from academic community (r/{subreddit}) discussing campus/student issues ({pat}), not market demand.",
                )

    # 4. Check for commercial / grocery / vegetable / delivery relevance
    commercial_matches = [
        pat for pat in _COMMERCIAL_CONSUMER_PATTERNS
        if re.search(pat, full_text)
    ]
    if len(commercial_matches) >= 2:
        return (
            "potentially_relevant",
            f"Post directly discusses commercial consumer delivery or food topics (matched patterns: {', '.join(commercial_matches[:3])}).",
        )
    elif len(commercial_matches) == 1:
        return (
            "potentially_relevant",
            f"Post mentions relevant consumer market topic ({commercial_matches[0]}).",
        )

    # 5. Default
    return (
        "unreviewed",
        "Keyword match in general community; requires qualitative evaluation.",
    )


# ------------------------------------------------------------------
# 5. Multi-Metric Record Decomposition
# ------------------------------------------------------------------

def decompose_multi_metric_record(rec: EvidenceRecord) -> List[EvidenceRecord]:
    """
    If a record encapsulates multiple distinct statistics inside a dictionary value,
    decompose it into atomic EvidenceRecords so each metric has its own distinct
    title, value, unit, geography, time_period, and metadata.
    """
    val = rec.value

    # Case A: PLFS Headline Labour Indicators
    # value = {"lfpr_percent": 55.64, "wpr_percent": 55.03, "unemployment_rate_percent": 1.10}
    if (
        rec.source == SourceType.PLFS and
        rec.evidence_type == EvidenceType.LABOUR_STATISTIC and
        isinstance(val, dict) and
        "lfpr_percent" in val and "wpr_percent" in val
    ):
        atomic_records = []
        loc_str = rec.geography.district or rec.geography.state or "Location" if rec.geography else "Location"
        sector_str = rec.geography.rural_urban or "Total" if rec.geography else "Total"

        metrics_map = [
            (
                "LFPR",
                "Labour Force Participation Rate (LFPR)",
                val.get("lfpr_percent"),
                "percent",
                "percentage of working-age population (Age 15+) in the labour force (employed or seeking work)",
            ),
            (
                "WPR",
                "Worker Population Ratio (WPR)",
                val.get("wpr_percent"),
                "percent",
                "percentage of working-age population (Age 15+) currently employed",
            ),
            (
                "UR",
                "Unemployment Rate (UR)",
                val.get("unemployment_rate_percent"),
                "percent",
                "percentage of persons in the labour force who are unemployed",
            ),
        ]

        for code, label, metric_val, unit_str, explanation in metrics_map:
            if metric_val is None:
                continue
            ev_id = f"{rec.evidence_id}_{code.lower()}"
            content = (
                f"PLFS 2025 {label} for {loc_str} ({sector_str}, Age 15+): {metric_val}% "
                f"(Usual Status ps+ss, survey-weighted). Represents {explanation}."
            )
            meta = dict(rec.metadata)
            meta["metric_code"] = code
            meta["indicator_name"] = label

            atomic_records.append(
                EvidenceRecord(
                    evidence_id=ev_id,
                    source=rec.source,
                    evidence_type=EvidenceType.LABOUR_STATISTIC,
                    title=f"PLFS 2025: {label} ({loc_str})",
                    content=clean_text(content),
                    value=metric_val,
                    unit=unit_str,
                    geography=rec.geography,
                    time_period=rec.time_period,
                    retrieved_at=rec.retrieved_at,
                    provenance=rec.provenance,
                    metadata=meta,
                    relevance=rec.relevance,
                    limitations=rec.limitations,
                )
            )
        return atomic_records

    # Case B: Census Table C-08A Higher Education Disciplines
    # value = {"engineering_and_technology": eng, "medicine": med, "teaching": teach, ...}
    if (
        rec.source == SourceType.CENSUS and
        isinstance(val, dict) and
        ("engineering_and_technology" in val or "medicine" in val)
    ):
        atomic_records = []
        loc_str = rec.geography.district or rec.geography.state or "Location" if rec.geography else "Location"
        is_fallback = bool(rec.metadata.get("is_state_fallback", False))
        fallback_str = " (State-level fallback)" if is_fallback else ""

        disciplines = [
            ("Engineering & Technology", "engineering_and_technology", val.get("engineering_and_technology")),
            ("Medicine", "medicine", val.get("medicine")),
            ("Teaching", "teaching", val.get("teaching")),
            ("Agriculture & Dairying", "agriculture_and_dairying", val.get("agriculture_and_dairying")),
        ]

        for disp_title, disp_key, disp_count in disciplines:
            if disp_count is None or disp_count <= 0:
                continue
            ev_id = f"{rec.evidence_id}_{disp_key[:8]}"
            content = (
                f"Census 2011 Table C-08A Graduate Education in {disp_title} for {loc_str}{fallback_str}: "
                f"{disp_count:,} persons."
            )
            meta = dict(rec.metadata)
            meta["discipline"] = disp_key
            meta["discipline_name"] = disp_title

            atomic_records.append(
                EvidenceRecord(
                    evidence_id=ev_id,
                    source=rec.source,
                    evidence_type=EvidenceType.EDUCATION_STATISTIC,
                    title=f"Census 2011: Graduates in {disp_title} ({loc_str}{fallback_str})",
                    content=clean_text(content),
                    value=disp_count,
                    unit="people",
                    geography=rec.geography,
                    time_period=rec.time_period,
                    retrieved_at=rec.retrieved_at,
                    provenance=rec.provenance,
                    metadata=meta,
                    relevance=rec.relevance,
                    limitations=rec.limitations,
                )
            )
        return atomic_records if atomic_records else [rec]

    # Case C: PLFS Household Size & Consumer Expenditure
    # value = {"avg_household_size": size, "avg_monthly_consumer_expenditure_inr": hce}
    if (
        rec.source == SourceType.PLFS and
        rec.evidence_type == EvidenceType.HOUSEHOLD_STATISTIC and
        isinstance(val, dict) and
        ("avg_household_size" in val or "avg_monthly_consumer_expenditure_inr" in val)
    ):
        atomic_records = []
        loc_str = rec.geography.district or rec.geography.state or "Location" if rec.geography else "Location"
        sector_str = rec.geography.rural_urban or "Total" if rec.geography else "Total"

        avg_size = val.get("avg_household_size")
        avg_hce = val.get("avg_monthly_consumer_expenditure_inr")

        if avg_size is not None:
            ev_id = f"{rec.evidence_id}_size"
            content = f"PLFS 2025 Average Household Size in {loc_str} ({sector_str}): {avg_size} persons per household."
            meta = dict(rec.metadata)
            meta["indicator"] = "avg_household_size"
            atomic_records.append(
                EvidenceRecord(
                    evidence_id=ev_id,
                    source=rec.source,
                    evidence_type=EvidenceType.HOUSEHOLD_STATISTIC,
                    title=f"PLFS 2025: Average Household Size ({loc_str})",
                    content=clean_text(content),
                    value=avg_size,
                    unit="persons_per_household",
                    geography=rec.geography,
                    time_period=rec.time_period,
                    retrieved_at=rec.retrieved_at,
                    provenance=rec.provenance,
                    metadata=meta,
                    relevance=rec.relevance,
                    limitations=rec.limitations,
                )
            )

        if avg_hce is not None:
            ev_id = f"{rec.evidence_id}_hce"
            content = (
                f"PLFS 2025 Average Monthly Household Consumer Expenditure in {loc_str} ({sector_str}): "
                f"INR {avg_hce:,.2f} per month."
            )
            meta = dict(rec.metadata)
            meta["indicator"] = "avg_monthly_consumer_expenditure_inr"
            atomic_records.append(
                EvidenceRecord(
                    evidence_id=ev_id,
                    source=rec.source,
                    evidence_type=EvidenceType.HOUSEHOLD_STATISTIC,
                    title=f"PLFS 2025: Average Monthly Consumer Expenditure ({loc_str})",
                    content=clean_text(content),
                    value=avg_hce,
                    unit="INR/month",
                    geography=rec.geography,
                    time_period=rec.time_period,
                    retrieved_at=rec.retrieved_at,
                    provenance=rec.provenance,
                    metadata=meta,
                    relevance=rec.relevance,
                    limitations=rec.limitations,
                )
            )

        return atomic_records if atomic_records else [rec]

    # Return as-is if no decomposition rule applies
    return [rec]


# ------------------------------------------------------------------
# 6. Deduplication Fingerprint
# ------------------------------------------------------------------

def _compute_record_fingerprint(rec: EvidenceRecord) -> str:
    """
    Compute a stable fingerprint for exact deduplication.
    Distinguishes distinct records while merging true duplicates.
    """
    geo_key = ""
    if rec.geography:
        geo_key = f"{rec.geography.state}:{rec.geography.district}:{rec.geography.rural_urban}"

    val_key = str(rec.value)
    raw = f"{rec.source.value}|{rec.evidence_type.value}|{rec.title.strip().lower()}|{rec.unit or ''}|{val_key}|{rec.time_period or ''}|{geo_key}"
    return sha256(raw.encode("utf-8")).hexdigest()


# ------------------------------------------------------------------
# 7. Master Cleaning Function
# ------------------------------------------------------------------

def clean_evidence(
    records: Optional[List[EvidenceRecord]],
    query: str = "",
    keywords: Optional[List[str]] = None,
) -> Tuple[List[EvidenceRecord], Dict[str, Any]]:
    """
    Master entrypoint for Step 3: Evidence Cleaning and Standardization.

    Parameters:
      records: List of normalized EvidenceRecord instances.
      query: The original business idea query (used for relevance assessment).
      keywords: Extracted keyword list.

    Returns:
      (cleaned_records, diagnostics)
    """
    diagnostics: Dict[str, Any] = {
        "input_records_count": 0,
        "cleaned_records_count": 0,
        "duplicates_removed_count": 0,
        "atomic_metrics_expanded_count": 0,
        "text_cleanups_count": 0,
        "numeric_valid_count": 0,
        "numeric_issues_flagged_count": 0,
        "relevance_breakdown": {
            "potentially_relevant": 0,
            "irrelevant": 0,
            "insufficient_context": 0,
            "unreviewed": 0,
        },
        "issues": [],
    }

    if not records or not isinstance(records, list):
        return [], diagnostics

    diagnostics["input_records_count"] = len(records)

    # Step 1: Multi-metric decomposition
    expanded_records: List[EvidenceRecord] = []
    for rec in records:
        if not isinstance(rec, EvidenceRecord):
            diagnostics["issues"].append(f"Skipped non-EvidenceRecord item of type {type(rec)}")
            continue

        atomic_items = decompose_multi_metric_record(rec)
        if len(atomic_items) > 1:
            diagnostics["atomic_metrics_expanded_count"] += (len(atomic_items) - 1)
        expanded_records.extend(atomic_items)

    cleaned_candidates: List[EvidenceRecord] = []
    seen_fingerprints: Set[str] = set()

    # Step 2: Clean, standardize, and validate each atomic record
    for rec in expanded_records:
        # A. Clean text
        orig_title = rec.title
        orig_content = rec.content
        new_title = clean_text(orig_title)
        new_content = clean_text(orig_content)

        if new_title != orig_title or new_content != orig_content:
            diagnostics["text_cleanups_count"] += 1

        # B. Standardize geography
        std_geo = standardize_geography(rec.geography)

        # C. Validate numeric value & unit
        is_valid_num, num_err = validate_numeric_value(
            rec.value,
            rec.unit,
            rec.evidence_type,
            rec.metadata,
        )

        if not is_valid_num:
            diagnostics["numeric_issues_flagged_count"] += 1
            diagnostics["issues"].append(f"Rejected invalid numeric record '{rec.title}': {num_err}")
            # Skip record with corrupted/impossible numeric value (e.g. NaN or 150% percent)
            continue
        else:
            diagnostics["numeric_valid_count"] += 1

        # D. Assess discussion relevance (Reddit)
        relevance_status = rec.relevance
        meta = dict(rec.metadata)
        if rec.source == SourceType.REDDIT:
            relevance_status, rel_reason = assess_reddit_relevance(
                rec,
                query=query,
                keywords=keywords,
            )
            meta["relevance_reason"] = rel_reason
            diagnostics["relevance_breakdown"][relevance_status] = (
                diagnostics["relevance_breakdown"].get(relevance_status, 0) + 1
            )
        else:
            if not relevance_status:
                relevance_status = "unreviewed"
            diagnostics["relevance_breakdown"][relevance_status] = (
                diagnostics["relevance_breakdown"].get(relevance_status, 0) + 1
            )

        # Build cleaned record
        cleaned_rec = EvidenceRecord(
            evidence_id=rec.evidence_id,
            source=rec.source,
            evidence_type=rec.evidence_type,
            title=new_title,
            content=new_content,
            value=rec.value,
            unit=rec.unit,
            geography=std_geo,
            time_period=rec.time_period,
            retrieved_at=rec.retrieved_at,
            provenance=rec.provenance,
            metadata=meta,
            relevance=relevance_status,
            limitations=rec.limitations,
        )

        # E. Deduplication
        fp = _compute_record_fingerprint(cleaned_rec)
        if fp in seen_fingerprints:
            diagnostics["duplicates_removed_count"] += 1
            continue

        seen_fingerprints.add(fp)
        cleaned_candidates.append(cleaned_rec)

    diagnostics["cleaned_records_count"] = len(cleaned_candidates)
    return cleaned_candidates, diagnostics
