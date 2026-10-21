"""
app.nodes.market_analysis
-------------------------
Persona aggregation and evidence cross-validation node (Step 11).

Aggregates individual simulated customer evaluations into interpretable market findings,
computes deterministic score distributions, normalizes qualitative feedback, and
cross-checks findings against empirical evidence from Census, PLFS, Trends, and Reddit.

STRICT BOUNDARIES:
1. No startup success probabilities or go/no-go recommendations.
2. Synthetic persona frequencies are NOT presented as real-world customer percentages.
3. Numerical aggregation is strictly deterministic.
4. Failed evaluations are isolated and not treated as negative customer reactions.
5. External evidence status (supported/contradicted/mixed/insufficient) is applied rigorously;
   population statistics do not validate purchase intent on their own.
"""

import math
import re
import statistics
from collections import defaultdict
from typing import Any, Dict, List, Optional, Set, Tuple, Union

from app.schemas.persona import Persona
from app.schemas.persona_evaluation import PersonaEvaluation
from app.schemas.market_analysis import (
    AggregatedConcern,
    AggregatedFeature,
    DisagreementArea,
    EvidenceCoverageMetrics,
    EvidenceStatus,
    EvidenceValidationItem,
    MarketAnalysis,
    MetricStatistics,
    OverallEvaluationStatistics,
    SegmentAnalysis,
)
from app.state import MarketState


# ------------------------------------------------------------------
# 1. Deterministic Numerical Aggregation Helpers
# ------------------------------------------------------------------

def compute_metric_statistics(metric_name: str, raw_values: List[Optional[int]]) -> MetricStatistics:
    """
    Compute rigorous descriptive statistics for a list of integer scores (1-10).
    Safely handles empty lists, single values, and missing/None entries.
    """
    valid_scores = [v for v in raw_values if v is not None and isinstance(v, (int, float))]
    missing_count = len(raw_values) - len(valid_scores)
    count = len(valid_scores)

    if count == 0:
        return MetricStatistics(
            metric_name=metric_name,
            count=0,
            mean=None,
            median=None,
            min_val=None,
            max_val=None,
            std_dev=None,
            distribution={i: 0 for i in range(1, 11)},
            missing_count=missing_count,
        )

    # Integer distribution histogram (1 to 10)
    dist = {i: 0 for i in range(1, 11)}
    for s in valid_scores:
        int_s = int(round(s))
        if 1 <= int_s <= 10:
            dist[int_s] += 1

    mean_val = round(sum(valid_scores) / count, 2)
    med_val = round(float(statistics.median(valid_scores)), 2)
    min_val = int(min(valid_scores))
    max_val = int(max(valid_scores))

    if count >= 2:
        std_val = round(float(statistics.stdev(valid_scores)), 2)
    else:
        std_val = 0.0

    return MetricStatistics(
        metric_name=metric_name,
        count=count,
        mean=mean_val,
        median=med_val,
        min_val=min_val,
        max_val=max_val,
        std_dev=std_val,
        distribution=dist,
        missing_count=missing_count,
    )


# ------------------------------------------------------------------
# 2. Evidence Metadata Extraction Helper
# ------------------------------------------------------------------

def _extract_chunk_source(chk: Any, chunk_id: str = "") -> str:
    """
    Extract the source string from a chunk, checking top-level keys then nested
    'metadata' dict.  Falls back to deterministic prefix inference from chunk_id
    (e.g. 'doc_ev_census_...' -> 'census_2011') and finally returns 'unknown'.
    Does NOT invent or fabricate source values.
    """
    if hasattr(chk, "source"):
        src = getattr(chk, "source", None)
    elif isinstance(chk, dict):
        src = chk.get("source") or chk.get("source_type")
        if not src:
            meta = chk.get("metadata", {})
            if isinstance(meta, dict):
                src = meta.get("source") or meta.get("source_type")
    else:
        src = None

    if src and str(src).strip() and str(src).strip().lower() != "unknown":
        return str(src).strip()

    # Deterministic prefix inference from chunk_id only
    cid = chunk_id or (getattr(chk, "chunk_id", "") or (chk.get("chunk_id", "") if isinstance(chk, dict) else ""))
    cid_lower = str(cid).lower()
    if "_census_" in cid_lower or cid_lower.startswith("census"):
        return "census_2011"
    if "_plfs_" in cid_lower or cid_lower.startswith("plfs"):
        return "plfs_2025"
    if "_reddit_" in cid_lower or cid_lower.startswith("reddit"):
        return "reddit"
    if "_trends_" in cid_lower or cid_lower.startswith("trends"):
        return "google_trends"
    return "unknown"


def _extract_chunk_metadata_field(chk: Any, field: str) -> Any:
    """
    Extract a metadata field (e.g. 'geography', 'time_period', 'limitations')
    from a chunk, checking top-level keys first then nested 'metadata' dict.
    Returns None when the field is absent in both locations.
    """
    if hasattr(chk, field):
        val = getattr(chk, field, None)
    elif isinstance(chk, dict):
        val = chk.get(field)
        if val is None:
            meta = chk.get("metadata", {})
            if isinstance(meta, dict):
                val = meta.get(field)
    else:
        val = None
    return val


# ------------------------------------------------------------------
# 3. Qualitative Text Normalization & Clustering
# ------------------------------------------------------------------

# Synonym groups: tokens in each group are treated as equivalent during overlap
_SYNONYM_GROUPS: List[List[str]] = [
    ["booking", "reservation", "reserving", "prebooking", "pre-booking", "book"],
    ["charging", "charge", "recharging"],
    ["reliable", "reliability", "dependable", "dependability"],
    ["availability", "available"],
    ["infrastructure", "network"],
    ["integration", "integrate", "integrated"],
    ["payment", "payments", "paying", "pay"],
    ["feature", "features", "functionality", "function"],
    ["uptime", "downtime"],
]

# Build a token -> canonical token map
_TOKEN_CANONICAL: Dict[str, str] = {}
for group in _SYNONYM_GROUPS:
    canon = group[0]
    for tok in group:
        _TOKEN_CANONICAL[tok] = canon


def _normalize_phrase(text: str) -> str:
    """Normalize a phrase for fuzzy clustering: lowercase, strip punctuation, apply synonym map."""
    t = text.lower().strip()
    t = re.sub(r"[^\w\s]", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    # Apply synonym normalization token-by-token
    tokens = [_TOKEN_CANONICAL.get(w, w) for w in t.split()]
    return " ".join(tokens)


def _categorize_concern(text: str) -> str:
    """Categorize a concern into documented barrier categories."""
    t = text.lower()
    if any(k in t for k in ["price", "cost", "afford", "expensive", "fee", "budget", "subscription", "inr", "cashflow", "rupee"]):
        return "pricing_and_affordability"
    if any(k in t for k in ["switch", "habit", "inertia", "replace", "workflow", "transition", "existing"]):
        return "switching_costs"
    if any(k in t for k in ["trust", "brand", "cancel", "reliability", "uptime", "security", "fraud", "safe", "credibility"]):
        return "trust_and_reliability"
    if any(k in t for k in ["app", "digital", "tech", "learning", "complex", "difficult", "confusing", "offline"]):
        return "usability_and_adoption"
    if any(k in t for k in ["schedule", "timing", "delay", "route", "distance", "capacity", "inventory", "bandwidth"]):
        return "operational_constraints"
    if any(k in t for k in ["lack", "missing", "feature", "custom", "integration", "flexibility", "support"]):
        return "missing_functionality"
    return "general"


def _cluster_items(raw_items_with_meta: List[Tuple[str, str, str, List[str]]]) -> Dict[str, Dict[str, Any]]:
    """
    Cluster text items by keyword similarity while preserving provenance and cited evidence IDs.
    raw_items_with_meta: List of (statement, persona_id, segment, evidence_ids)
    Returns: Dict[cluster_name, cluster_data]
    """
    clusters: Dict[str, Dict[str, Any]] = {}

    for statement, pid, seg, ev_ids in raw_items_with_meta:
        norm = _normalize_phrase(statement)
        if not norm:
            continue

        # Look for existing cluster with significant token overlap
        words = set(w for w in norm.split() if len(w) > 3)
        matched_cluster = None

        for c_name, c_data in clusters.items():
            c_norm = _normalize_phrase(c_name)
            c_words = set(w for w in c_norm.split() if len(w) > 3)
            # Overlap condition
            if words and c_words and len(words.intersection(c_words)) >= min(2, len(words), len(c_words)):
                matched_cluster = c_name
                break
            elif norm in c_norm or c_norm in norm:
                matched_cluster = c_name
                break

        target_name = matched_cluster if matched_cluster else statement.strip()
        if target_name not in clusters:
            clusters[target_name] = {
                "persona_ids": set(),
                "segments": set(),
                "statements": [],
                "evidence_ids": set(),
            }

        clusters[target_name]["persona_ids"].add(pid)
        clusters[target_name]["segments"].add(seg)
        clusters[target_name]["statements"].append(statement.strip())
        clusters[target_name]["evidence_ids"].update(ev_ids)

    return clusters


# ------------------------------------------------------------------
# 3. Evidence Cross-Validation Engine
# ------------------------------------------------------------------

def _cross_validate_finding(
    finding_text: str,
    cited_evidence_ids: List[str],
    all_evidence_records: Dict[str, Dict[str, Any]],
) -> EvidenceValidationItem:
    """
    Evaluate empirical evidence status for an aggregated finding.
    Statuses:
    - supported: relevant external records directly reinforce finding.
    - contradicted: external records explicitly conflict with finding.
    - mixed: external records show conflicting evidence.
    - insufficient_evidence: no direct evidence or only tangential population count.
    - not_applicable: purely subjective preference with no meaningful external data.
    """
    norm_text = finding_text.lower()

    # If no evidence IDs were cited by personas
    if not cited_evidence_ids:
        # Check if finding is purely subjective persona preference
        subjective_keywords = ["color", "ui design", "aesthetic", "favorite", "prefers email over chat", "button"]
        if any(sk in norm_text for sk in subjective_keywords):
            return EvidenceValidationItem(
                evidence_status=EvidenceStatus.NOT_APPLICABLE,
                explanation="Subjective persona workflow preference not applicable to empirical demographic or economic statistics.",
            )

        return EvidenceValidationItem(
            evidence_status=EvidenceStatus.INSUFFICIENT_EVIDENCE,
            caveats=["No external empirical evidence cited by simulated personas for this finding."],
            explanation="Finding is an unverified hypothesis lacking empirical market evidence.",
        )

    # Inspect the actual records corresponding to the cited evidence IDs
    matched_records = []
    sources = set()
    geos = []
    caveats = []
    supporting_eids: List[str] = []
    contradicting_eids: List[str] = []

    operational_keywords = [
        "operational", "latency", "uptime", "downtime", "maintenance", "dispatch",
        "turnaround", "throughput", "infrastructure", "hardware", "breakdown",
        "fleet management", "charging speed", "battery degradation", "grid capacity",
        "power cutoff", "load shedding", "logistics route", "warehouse storage"
    ]
    statistical_keywords = [
        "market share", "% of market", "percent of market", "% of drivers", "% of users",
        "statistically", "nationwide", "statewide", "market size", "total addressable market",
        "tam", "cagr", "penetration rate", "population-wide", "majority of fleets", "majority of users"
    ]
    conversion_keywords = [
        "conversion rate", "purchase intent", "will purchase", "will pay", "subscription conversion"
    ]

    for eid in cited_evidence_ids:
        rec = all_evidence_records.get(eid)
        if not rec:
            caveats.append(f"Cited evidence ID [{eid}] not found in retrieved evidence index.")
            continue

        src = rec.get("source")
        if not src or str(src).strip().lower() in ("unknown", "", "none"):
            caveats.append(f"Evidence record [{eid}] lacks verified source metadata; excluded from empirical validation.")
            continue

        src_str = str(src).strip()
        text = str(rec.get("text", "")).strip().lower()
        if not text:
            caveats.append(f"Evidence record [{eid}] from {src_str} contains empty text; excluded from empirical validation.")
            continue

        matched_records.append(rec)
        sources.add(src_str)
        if rec.get("geography"):
            geos.append(rec["geography"])
        if rec.get("limitations"):
            lims = rec["limitations"] if isinstance(rec["limitations"], list) else [str(rec["limitations"])]
            caveats.extend(lims)

        src_lower = src_str.lower()

        # Rule 1: Google Trends reflects public search interest, NOT operational feasibility or performance
        if "trends" in src_lower or "google_trends" in src_lower:
            if any(op in norm_text for op in operational_keywords):
                caveats.append(f"Google Trends record [{eid}] reflects search query activity, which cannot corroborate operational claims.")
            elif any(kw in norm_text for kw in ["search", "trend", "interest", "demand", "awareness", "volume", "popularity", "query"]):
                supporting_eids.append(eid)
            else:
                caveats.append(f"Google Trends record [{eid}] provides query index data without direct validation of this specific finding.")

        # Rule 2: Qualitative Reddit discussion cannot substantiate market-wide statistical metrics
        elif "reddit" in src_lower:
            if any(stat in norm_text for stat in statistical_keywords):
                caveats.append(f"Reddit record [{eid}] reflects qualitative anecdotal discussion, which cannot substantiate market-wide statistical metrics.")
            elif "delay" in text or "cancel" in text or "complaint" in text or "issue" in text or "friction" in text:
                if "monsoon" in norm_text or "cancel" in norm_text or any(kw in norm_text for kw in ["reliability", "punctual", "on-time", "100%", "99%"]):
                    contradicting_eids.append(eid)
                else:
                    supporting_eids.append(eid)
            else:
                supporting_eids.append(eid)

        # Rule 3: Census / PLFS provide macroeconomic demographic/wage data, NOT product conversion rates
        elif "plfs" in src_lower or "census" in src_lower:
            if any(conv in norm_text for conv in conversion_keywords):
                caveats.append(f"Aggregate {src_str} record [{eid}] provides demographic and wage context but does not prove willingness to pay or product conversion.")
            elif any(k in norm_text for k in ["salary", "budget", "afford", "income", "wage", "education", "engineer", "literacy", "tech", "demographic", "worker", "labour", "employment"]):
                supporting_eids.append(eid)
            else:
                caveats.append(f"Aggregate {src_str} record [{eid}] provides demographic context but does not validate specific product intent.")

        else:
            # Other verified external sources
            supporting_eids.append(eid)

    has_support = len(supporting_eids) > 0
    has_conflict = len(contradicting_eids) > 0

    if not has_support and not has_conflict:
        status = EvidenceStatus.INSUFFICIENT_EVIDENCE
        expl = f"Cited records ({', '.join(sorted(sources)) if sources else 'none'}) provide background context but do not directly validate this specific finding."
    elif has_support and has_conflict:
        status = EvidenceStatus.MIXED
        expl = f"Empirical records contain mixed signals: support from {', '.join(sorted(sources))} with conflicting complaints or limitations."
    elif has_conflict:
        status = EvidenceStatus.CONTRADICTED
        expl = f"Empirical observations from {', '.join(sorted(sources))} directly conflict with the simulated expectation."
    else:
        status = EvidenceStatus.SUPPORTED
        expl = f"Directly corroborated by empirical records from {', '.join(sorted(sources))}."

    geo_summary = None
    if geos:
        first_geo = geos[0]
        if isinstance(first_geo, dict):
            geo_summary = first_geo
        elif isinstance(first_geo, str):
            geo_summary = {"region": first_geo}

    return EvidenceValidationItem(
        evidence_status=status,
        supporting_evidence_ids=supporting_eids,
        contradicting_evidence_ids=contradicting_eids,
        evidence_sources=sorted(list(sources)),
        geography=geo_summary,
        time_period="2011-2025" if sources else None,
        caveats=list(dict.fromkeys(caveats))[:3],
        explanation=expl,
    )


# ------------------------------------------------------------------
# 4. Master Market Analysis Function
# ------------------------------------------------------------------

def analyze_market(
    idea: str,
    personas: List[Union[Persona, Dict[str, Any]]],
    evaluations: List[Union[PersonaEvaluation, Dict[str, Any]]],
    research_evidence: Optional[Dict[str, Any]] = None,
    retrieved_chunks: Optional[List[Any]] = None,
) -> Tuple[MarketAnalysis, Dict[str, Any]]:
    """
    Deterministically aggregate persona evaluations and cross-validate findings against evidence.

    Parameters:
    - idea: Business idea string.
    - personas: List of Persona objects or dictionaries.
    - evaluations: List of PersonaEvaluation objects or dictionaries.
    - research_evidence: Raw/cleaned research evidence from state.
    - retrieved_chunks: Retrieved evidence chunks.

    Returns:
    - (MarketAnalysis, diagnostics_dict)
    """
    diagnostics: Dict[str, Any] = {
        "total_personas": len(personas),
        "total_evaluations": len(evaluations),
        "issues": [],
    }

    if not idea or not idea.strip():
        raise ValueError("Business idea string cannot be empty.")

    # 1. Index Personas by persona_id
    persona_map: Dict[str, Persona] = {}
    for p in personas:
        try:
            p_obj = p if isinstance(p, Persona) else Persona.model_validate(p)
            persona_map[p_obj.persona_id] = p_obj
        except Exception as e:
            diagnostics["issues"].append(f"Persona validation warning: {e}")

    # 2. Index Evaluations by persona_id
    valid_evaluations: List[PersonaEvaluation] = []
    failed_eval_count = 0
    for e in evaluations:
        try:
            e_obj = e if isinstance(e, PersonaEvaluation) else PersonaEvaluation.model_validate(e)
            valid_evaluations.append(e_obj)
        except Exception as e:
            failed_eval_count += 1
            diagnostics["issues"].append(f"Evaluation validation error: {e}")

    # 3. Build Evidence Index from retrieved chunks and cleaned records
    # NOTE: DocumentChunk dicts produced by chunker.py store provenance fields
    # (source, geography, time_period, limitations) inside a nested 'metadata' dict.
    # _extract_chunk_source / _extract_chunk_metadata_field handle both layouts.
    all_evidence_records: Dict[str, Dict[str, Any]] = {}
    if retrieved_chunks:
        for chk in retrieved_chunks:
            cid = getattr(chk, "chunk_id", None) or (chk.get("chunk_id") if isinstance(chk, dict) else None)
            if cid:
                all_evidence_records[str(cid)] = {
                    "chunk_id": str(cid),
                    "text": getattr(chk, "text", "") or (chk.get("text", "") if isinstance(chk, dict) else ""),
                    "source": _extract_chunk_source(chk, str(cid)),
                    "geography": _extract_chunk_metadata_field(chk, "geography"),
                    "time_period": _extract_chunk_metadata_field(chk, "time_period"),
                    "limitations": _extract_chunk_metadata_field(chk, "limitations"),
                }

    if research_evidence:
        # Support both dictionary of id -> record and list of records
        for k, v in research_evidence.items():
            if isinstance(v, dict) and ("text" in v or "source" in v):
                all_evidence_records[k] = {
                    "chunk_id": k,
                    "text": v.get("text") or v.get("observation_summary", ""),
                    "source": _extract_chunk_source(v, k),
                    "geography": v.get("geography"),
                    "time_period": v.get("time_period"),
                    "limitations": v.get("limitations"),
                }
        for key in ["cleaned_evidence", "normalized_evidence", "census_evidence", "plfs_evidence", "reddit_evidence", "trends_evidence"]:
            for item in research_evidence.get(key, []):
                eid = item.get("evidence_id") if isinstance(item, dict) else getattr(item, "evidence_id", None)
                if not eid and isinstance(item, dict):
                    eid = item.get("chunk_id")
                if eid:
                    txt = (item.get("text") or item.get("observation_summary") or "") if isinstance(item, dict) else (getattr(item, "text", None) or getattr(item, "observation_summary", ""))
                    all_evidence_records[str(eid)] = {
                        "chunk_id": str(eid),
                        "text": txt,
                        "source": _extract_chunk_source(item, str(eid)),
                        "geography": _extract_chunk_metadata_field(item, "geography"),
                        "time_period": _extract_chunk_metadata_field(item, "time_period"),
                        "limitations": _extract_chunk_metadata_field(item, "limitations"),
                    }

    # 4. Compute Overall Evaluation Statistics (Deterministic)
    interest_scores = [ev.interest_score for ev in valid_evaluations]
    intent_scores = [ev.simulated_purchase_intent for ev in valid_evaluations]
    value_scores = [ev.perceived_value_score for ev in valid_evaluations]
    afford_scores = [ev.affordability_score for ev in valid_evaluations]
    barrier_scores = [ev.adoption_barrier_score for ev in valid_evaluations]

    overall_stats = OverallEvaluationStatistics(
        total_personas_generated=len(personas),
        successful_evaluations_count=len(valid_evaluations),
        failed_evaluations_count=failed_eval_count,
        interest_stats=compute_metric_statistics("interest_score", interest_scores),
        purchase_intent_stats=compute_metric_statistics("simulated_purchase_intent", intent_scores),
        perceived_value_stats=compute_metric_statistics("perceived_value_score", value_scores),
        affordability_stats=compute_metric_statistics("affordability_score", afford_scores),
        adoption_barrier_stats=compute_metric_statistics("adoption_barrier_score", barrier_scores),
    )

    # 5. Aggregate Features (Positive & Negative/Unnecessary)
    # BOUNDARY: Only clusters with positive_mentions_count >= 1 qualify as feature
    # hypotheses (features_analysis).  Clusters that are purely negative (zero positive
    # mentions) are routed to concerns_analysis as explicitly-rejected items so they
    # remain traceable without being misrepresented as feature candidates.
    pos_feature_items: List[Tuple[str, str, str, List[str]]] = []
    neg_feature_items: List[Tuple[str, str, str, List[str]]] = []

    for ev in valid_evaluations:
        p_obj = persona_map.get(ev.persona_id)
        seg = p_obj.segment if p_obj else "General"
        ev_ids = ev.supporting_evidence_ids or []

        # Positive features
        for f in ev.valued_features + ev.positive_aspects:
            pos_feature_items.append((f, ev.persona_id, seg, ev_ids))

        # Unnecessary or rejected features
        for f in ev.unnecessary_features:
            neg_feature_items.append((f, ev.persona_id, seg, ev_ids))

    pos_clusters = _cluster_items(pos_feature_items)
    neg_clusters = _cluster_items(neg_feature_items)

    aggregated_features: List[AggregatedFeature] = []
    # Clusters appearing only in neg_clusters (zero positive mentions) are preserved
    # as rejected-feature concerns and appended to concern_items later.
    purely_negative_clusters: List[Tuple[str, Dict[str, Any]]] = []

    all_cluster_names = set(pos_clusters.keys()).union(set(neg_clusters.keys()))

    for c_name in sorted(all_cluster_names):
        pos_data = pos_clusters.get(c_name, {"persona_ids": set(), "segments": set(), "statements": [], "evidence_ids": set()})
        neg_data = neg_clusters.get(c_name, {"persona_ids": set(), "segments": set(), "statements": [], "evidence_ids": set()})

        pos_count = len(pos_data["persona_ids"])
        neg_count = len(neg_data["persona_ids"])

        # Features with zero positive mentions are not feature hypotheses.
        # They are preserved separately and folded into concerns below.
        if pos_count == 0 and neg_count > 0:
            purely_negative_clusters.append((c_name, neg_data))
            continue

        all_pids = sorted(list(pos_data["persona_ids"].union(neg_data["persona_ids"])))
        all_segs = sorted(list(pos_data["segments"].union(neg_data["segments"])))
        all_stmts = list(dict.fromkeys(pos_data["statements"] + neg_data["statements"]))[:4]

        # Use the specific evidence IDs cited by the evaluations contributing to this feature
        rel_ev_ids = sorted(list(pos_data["evidence_ids"].union(neg_data["evidence_ids"])))
        val_item = _cross_validate_finding(c_name, rel_ev_ids, all_evidence_records)

        aggregated_features.append(
            AggregatedFeature(
                feature_name=c_name,
                positive_mentions_count=pos_count,
                negative_mentions_count=neg_count,
                persona_ids=all_pids,
                segments_represented=all_segs,
                original_statements=all_stmts,
                validation=val_item,
            )
        )

    # Sort features by popularity (positive mentions descending)
    aggregated_features.sort(key=lambda x: x.positive_mentions_count, reverse=True)

    # 6. Aggregate Concerns and Barriers
    # Also folds in purely-negative feature clusters (zero positive mentions) so they
    # are preserved in the report with category 'missing_functionality' / 'general'.
    concern_items: List[Tuple[str, str, str, List[str]]] = []
    for ev in valid_evaluations:
        p_obj = persona_map.get(ev.persona_id)
        seg = p_obj.segment if p_obj else "General"
        ev_ids = ev.supporting_evidence_ids or []
        for c in ev.negative_aspects + ev.needs_unmet:
            concern_items.append((c, ev.persona_id, seg, ev_ids))

    concern_clusters = _cluster_items(concern_items)
    aggregated_concerns: List[AggregatedConcern] = []

    for c_name, c_data in concern_clusters.items():
        pids = sorted(list(c_data["persona_ids"]))
        segs = sorted(list(c_data["segments"]))
        stmts = list(dict.fromkeys(c_data["statements"]))[:4]
        cat = _categorize_concern(c_name)

        # Use the specific evidence IDs cited by the evaluations contributing to this concern
        rel_ev_ids = sorted(list(c_data["evidence_ids"]))
        val_item = _cross_validate_finding(c_name, rel_ev_ids, all_evidence_records)

        aggregated_concerns.append(
            AggregatedConcern(
                concern_name=c_name,
                category=cat,
                persona_mentions_count=len(pids),
                persona_ids=pids,
                segments_represented=segs,
                original_statements=stmts,
                validation=val_item,
            )
        )

    # Fold purely-negative feature clusters into concerns (labelled 'missing_functionality')
    for c_name, c_data in purely_negative_clusters:
        pids = sorted(list(c_data["persona_ids"]))
        segs = sorted(list(c_data["segments"]))
        stmts = list(dict.fromkeys(c_data["statements"]))[:4]
        # Prefer 'missing_functionality' category to distinguish rejected features from barriers
        cat = _categorize_concern(c_name) or "missing_functionality"
        rel_ev_ids = sorted(list(c_data["evidence_ids"]))
        val_item = _cross_validate_finding(c_name, rel_ev_ids, all_evidence_records)
        aggregated_concerns.append(
            AggregatedConcern(
                concern_name=c_name,
                category=cat,
                persona_mentions_count=len(pids),
                persona_ids=pids,
                segments_represented=segs,
                original_statements=stmts,
                validation=val_item,
            )
        )

    aggregated_concerns.sort(key=lambda x: x.persona_mentions_count, reverse=True)

    # 7. Segment Analysis
    segments_dict: Dict[str, List[PersonaEvaluation]] = defaultdict(list)
    segment_persona_counts: Dict[str, int] = defaultdict(int)

    for p in persona_map.values():
        segment_persona_counts[p.segment] += 1

    for ev in valid_evaluations:
        p_obj = persona_map.get(ev.persona_id)
        seg = p_obj.segment if p_obj else "General"
        segments_dict[seg].append(ev)

    segment_analyses: List[SegmentAnalysis] = []
    for seg_name, seg_evals in segments_dict.items():
        eval_count = len(seg_evals)
        total_p = segment_persona_counts.get(seg_name, eval_count)

        med_int = round(float(statistics.median([e.interest_score for e in seg_evals])), 2) if seg_evals else None
        med_pi = round(float(statistics.median([e.simulated_purchase_intent for e in seg_evals])), 2) if seg_evals else None
        med_val = round(float(statistics.median([e.perceived_value_score for e in seg_evals])), 2) if seg_evals else None
        med_aff = round(float(statistics.median([e.affordability_score for e in seg_evals])), 2) if seg_evals else None
        med_bar = round(float(statistics.median([e.adoption_barrier_score for e in seg_evals])), 2) if seg_evals else None

        # Top features & concerns for this segment
        seg_features = []
        for e in seg_evals:
            seg_features.extend(e.valued_features)
        top_feats = [f for f, _ in defaultdict(int, {x: seg_features.count(x) for x in seg_features}).items()][:3]

        seg_concerns = []
        for e in seg_evals:
            seg_concerns.extend(e.negative_aspects)
        top_concs = [c for c, _ in defaultdict(int, {x: seg_concerns.count(x) for x in seg_concerns}).items()][:3]

        aff_barr_summary = f"Affordability median: {med_aff}/10 | Adoption barrier median: {med_bar}/10"
        if med_aff is not None and med_aff <= 4:
            aff_barr_summary += " (High budget sensitivity in this segment)"
        if med_bar is not None and med_bar >= 6:
            aff_barr_summary += " (Substantial switching or operational inertia)"

        # Evidence gaps for segment
        seg_gaps = []
        for e in seg_evals:
            seg_gaps.extend(e.evidence_gaps)
        top_gaps = list(dict.fromkeys(seg_gaps))[:3]

        coverage_summary = f"{len(seg_evals)} evaluations grounded in {len(set(id for e in seg_evals for id in e.supporting_evidence_ids))} distinct evidence records."

        segment_analyses.append(
            SegmentAnalysis(
                segment_name=seg_name,
                persona_count=total_p,
                evaluated_count=eval_count,
                median_interest=med_int,
                median_purchase_intent=med_pi,
                median_perceived_value=med_val,
                median_affordability=med_aff,
                median_adoption_barrier=med_bar,
                top_valued_features=top_feats,
                major_concerns=top_concs,
                affordability_and_adoption_summary=aff_barr_summary,
                evidence_coverage_summary=coverage_summary,
                important_gaps=top_gaps,
            )
        )

    segment_analyses.sort(key=lambda s: s.median_interest or 0, reverse=True)

    # 8. Detect Disagreement Areas
    disagreement_areas: List[DisagreementArea] = []

    # Check high standard deviation metrics across whole evaluation population
    for metric_name, stat_obj in [
        ("interest_score", overall_stats.interest_stats),
        ("affordability_score", overall_stats.affordability_stats),
        ("adoption_barrier_score", overall_stats.adoption_barrier_stats),
        ("simulated_purchase_intent", overall_stats.purchase_intent_stats),
    ]:
        if stat_obj.std_dev is not None and stat_obj.std_dev >= 2.0 and stat_obj.count >= 2:
            spread = stat_obj.max_val - stat_obj.min_val if (stat_obj.max_val and stat_obj.min_val) else stat_obj.std_dev
            disagreement_areas.append(
                DisagreementArea(
                    topic=f"Wide variance in {metric_name.replace('_', ' ')}",
                    description=f"Significant divergence observed (StdDev: {stat_obj.std_dev}, Min: {stat_obj.min_val}, Max: {stat_obj.max_val}).",
                    metric_or_facet=metric_name,
                    divergence_spread=float(spread),
                    opposing_views_or_segments={
                        "distribution": stat_obj.distribution,
                    },
                    explanation="Personas with differing budget constraints and operational habits reached opposing conclusions.",
                )
            )

    # Check cross-segment divergence
    if len(segment_analyses) >= 2:
        seg_a = segment_analyses[0]
        seg_b = segment_analyses[-1]
        if seg_a.median_interest is not None and seg_b.median_interest is not None:
            diff = abs(seg_a.median_interest - seg_b.median_interest)
            if diff >= 3.0:
                disagreement_areas.append(
                    DisagreementArea(
                        topic=f"Segment Receptivity Gap: {seg_a.segment_name} vs {seg_b.segment_name}",
                        description=f"Median interest diverges by {diff:.1f} points between segments.",
                        metric_or_facet="median_interest",
                        divergence_spread=round(diff, 2),
                        opposing_views_or_segments={
                            seg_a.segment_name: f"Median Interest: {seg_a.median_interest}/10",
                            seg_b.segment_name: f"Median Interest: {seg_b.median_interest}/10",
                        },
                        explanation="Differences in core workflow alignment and pain point urgency drive opposing receptivity.",
                    )
                )

    # 9. Evidence Coverage & Uncertainty Audit
    # NOTE: Founder context and synthetic persona scores are NOT counted as external evidence.
    # Only aggregated_features and aggregated_concerns are evaluated here.
    all_findings_validations = (
        [f.validation for f in aggregated_features]
        + [c.validation for c in aggregated_concerns]
    )
    total_findings = len(all_findings_validations)

    supported_count = sum(1 for v in all_findings_validations if v.evidence_status == EvidenceStatus.SUPPORTED)
    contradicted_count = sum(1 for v in all_findings_validations if v.evidence_status == EvidenceStatus.CONTRADICTED)
    mixed_count = sum(1 for v in all_findings_validations if v.evidence_status == EvidenceStatus.MIXED)
    insufficient_count = sum(1 for v in all_findings_validations if v.evidence_status == EvidenceStatus.INSUFFICIENT_EVIDENCE)
    na_count = sum(1 for v in all_findings_validations if v.evidence_status == EvidenceStatus.NOT_APPLICABLE)

    # Evidence coverage ratio (documented formula: empirical coverage measure, NOT success probability!)
    coverage_ratio = round((supported_count + contradicted_count + mixed_count) / max(1, total_findings), 2)

    # Collect unique sources
    all_sources = sorted(list(set(s for v in all_findings_validations for s in v.evidence_sources)))

    # Collect unresolved pricing assumptions
    unresolved_pricing = []
    has_cond_price = any(getattr(e, "price_is_conditional", False) for e in valid_evaluations)
    if has_cond_price:
        unresolved_pricing.append("Pricing is conditional: no verified price was specified in the business idea.")

    # Collect unsupported assumptions and evidence gaps across evaluations
    unsupported_assumptions = list(dict.fromkeys(a for e in valid_evaluations for a in e.unsupported_assumptions))[:5]
    evidence_gaps = list(dict.fromkeys(g for e in valid_evaluations for g in e.evidence_gaps))[:5]

    evidence_coverage = EvidenceCoverageMetrics(
        total_findings_evaluated=total_findings,
        supported_count=supported_count,
        contradicted_count=contradicted_count,
        mixed_count=mixed_count,
        insufficient_evidence_count=insufficient_count,
        not_applicable_count=na_count,
        evidence_coverage_ratio=coverage_ratio,
        sources_represented=all_sources,
        unresolved_pricing_assumptions=unresolved_pricing,
        unsupported_assumptions=unsupported_assumptions,
        important_evidence_gaps=evidence_gaps,
    )

    analysis_result = MarketAnalysis(
        overall_statistics=overall_stats,
        features_analysis=aggregated_features,
        concerns_analysis=aggregated_concerns,
        segment_analyses=segment_analyses,
        disagreement_areas=disagreement_areas,
        evidence_coverage=evidence_coverage,
        diagnostics=diagnostics,
    )

    return analysis_result, diagnostics


# ------------------------------------------------------------------
# 5. LangGraph Node Integration
# ------------------------------------------------------------------

def analyze_market_node(state: MarketState) -> Dict[str, Any]:
    """
    LangGraph node executing deterministic persona aggregation and evidence cross-validation.
    """
    idea = state.get("idea", "")
    personas = state.get("personas", [])
    evaluations = state.get("persona_evaluations", [])

    print("\n>>> PERSONA AGGREGATION & EVIDENCE CROSS-VALIDATION (Step 11)")

    if not evaluations:
        print("    Market Analysis: Skipped (No persona evaluations found in state).")
        return {
            "market_analysis": {},
            "market_analysis_diagnostics": {
                "status": "skipped",
                "issues": ["No persona evaluations found in state."],
            },
        }

    research_evidence = {
        "census_evidence": state.get("census_evidence", []),
        "plfs_evidence": state.get("plfs_evidence", []),
        "reddit_evidence": state.get("reddit_evidence", []),
        "trends_evidence": state.get("trends_evidence", []),
        "cleaned_evidence": state.get("cleaned_evidence", []),
        "normalized_evidence": state.get("normalized_evidence", []),
    }
    retrieved_chunks = state.get("retrieved_chunks", []) or state.get("document_chunks", [])

    try:
        analysis, diag = analyze_market(
            idea=idea,
            personas=personas,
            evaluations=evaluations,
            research_evidence=research_evidence,
            retrieved_chunks=retrieved_chunks,
        )

        analysis_dict = analysis.model_dump()
        stats = analysis.overall_statistics
        print(f"    Evaluations Aggregated: {stats.successful_evaluations_count} / {stats.total_personas_generated} personas")
        print(f"    Mean Interest: {stats.interest_stats.mean}/10 (Median: {stats.interest_stats.median}/10, StdDev: {stats.interest_stats.std_dev})")
        print(f"    Mean Purchase Intent: {stats.purchase_intent_stats.mean}/10 (Median: {stats.purchase_intent_stats.median}/10)")
        print(f"    Mean Adoption Barrier: {stats.adoption_barrier_stats.mean}/10 (Median: {stats.adoption_barrier_stats.median}/10)")
        print(f"    Segments Analyzed: {len(analysis.segment_analyses)} | Features Synthesized: {len(analysis.features_analysis)}")
        print(f"    Evidence Coverage Ratio: {analysis.evidence_coverage.evidence_coverage_ratio:.2f} ({analysis.evidence_coverage.supported_count} supported, {analysis.evidence_coverage.insufficient_evidence_count} insufficient)")

        return {
            "market_analysis": analysis_dict,
            "market_analysis_diagnostics": diag,
        }
    except Exception as e:
        print(f"    Market Analysis Error: {e}")
        return {
            "market_analysis": {},
            "market_analysis_diagnostics": {
                "status": "error",
                "issues": [f"Market analysis exception: {e}"],
            },
        }
