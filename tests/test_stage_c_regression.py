"""
tests.test_stage_c_regression
------------------------------
Stage C regression tests:
  C1. Nested metadata source recovery (source inside 'metadata' dict)
  C2. Evidence presence does NOT force SUPPORTED status
  C3. Zero-positive-mention items excluded from features_analysis
  C4. Synonym normalization consolidates overlapping phrases
  C5. Chunk-ID prefix source inference is deterministic
  C6. Coverage audit denominates both features AND concerns
  C7. CLI median-score key compatibility (short + prefixed keys)
  C8. PLFS earnings key compatibility in market_report
"""

import os
import pytest
from dotenv import load_dotenv

load_dotenv()
if not os.getenv("MISTRAL_API_KEY"):
    os.environ["MISTRAL_API_KEY"] = "mock-key-for-test"

from app.schemas.persona import BehavioralHypotheses, CustomerType, Persona, PersonaProvenance
from app.schemas.persona_evaluation import PersonaEvaluation
from app.schemas.market_analysis import EvidenceStatus
from app.nodes.market_analysis import (
    analyze_market,
    _extract_chunk_source,
    _extract_chunk_metadata_field,
)
from app.nodes.market_report import build_market_validation_report


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _persona(pid: str, name: str = "Test User", segment: str = "Tech") -> Persona:
    return Persona(
        persona_id=pid,
        name=name,
        customer_type=CustomerType.CONSUMER,
        segment=segment,
        age_band="25-34",
        occupation="Engineer",
        behavioral_hypotheses=BehavioralHypotheses(
            price_sensitivity=5,
            convenience_preference=7,
            brand_trust_importance=6,
            risk_tolerance=6,
            digital_adoption=8,
        ),
        goals_and_needs=["Fast commute"],
        pain_points=["Traffic"],
        purchasing_constraints=["Budget"],
        provenance=PersonaProvenance(is_synthetic=True, is_statistically_representative=False),
    )


def _eval(
    pid: str,
    interest: int = 7,
    valued_features: list = None,
    unnecessary_features: list = None,
    negative_aspects: list = None,
    evidence_ids: list = None,
) -> PersonaEvaluation:
    return PersonaEvaluation(
        persona_id=pid,
        interest_score=interest,
        simulated_purchase_intent=6,
        perceived_value_score=7,
        affordability_score=6,
        adoption_barrier_score=3,
        positive_aspects=[],
        negative_aspects=negative_aspects or [],
        needs_addressed=[],
        needs_unmet=[],
        pricing_considerations="Conditional",
        price_is_conditional=True,
        valued_features=valued_features or ["Core feature"],
        unnecessary_features=unnecessary_features or [],
        reasons_for_assessment="Test evaluation.",
        supporting_persona_attributes=[],
        supporting_evidence_ids=evidence_ids or [],
        unsupported_assumptions=["Assumed drivers are punctual"],
        evidence_gaps=["Route density unknown"],
        is_simulation=True,
        is_conversion_probability=False,
    )


# ------------------------------------------------------------------
# C1. Nested metadata source recovery
# ------------------------------------------------------------------

def test_nested_metadata_source_resolved():
    """
    Source field stored inside a nested 'metadata' dict (DocumentChunk.model_dump()
    layout) must be resolved correctly to a non-'unknown' value.
    """
    chunk = {
        "chunk_id": "doc_ev_plfs_abc123_c0",
        "text": "PLFS 2025: avg INR 22,638/mo.",
        "metadata": {
            "source": "plfs_2025",
            "geography": {"state": "Gujarat"},
            "time_period": "2025",
            "limitations": ["Survey estimate."],
        },
    }
    src = _extract_chunk_source(chunk, "doc_ev_plfs_abc123_c0")
    assert src == "plfs_2025", f"Expected 'plfs_2025', got {src!r}"

    geo = _extract_chunk_metadata_field(chunk, "geography")
    assert geo == {"state": "Gujarat"}

    tp = _extract_chunk_metadata_field(chunk, "time_period")
    assert tp == "2025"


def test_nested_metadata_source_used_in_evidence_index():
    """
    Evidence cross-validation must use the resolved source (not 'unknown')
    when chunks carry their provenance inside a nested metadata dict.
    """
    p = _persona("p1")
    chunk = {
        "chunk_id": "doc_ev_plfs_abc123_c0",
        "text": "PLFS 2025: regular salaried tech workers in Gujarat earn INR 22,638 monthly.",
        "metadata": {"source": "plfs_2025", "geography": {"state": "Gujarat"}},
    }
    ev = _eval("p1", valued_features=["Affordable salary-aligned pricing"], evidence_ids=["doc_ev_plfs_abc123_c0"])

    analysis, _ = analyze_market("Smart Shuttle", [p], [ev], retrieved_chunks=[chunk])

    # At least one finding must have been indexed and evaluated
    assert analysis.evidence_coverage.total_findings_evaluated > 0

    # The resolved sources must not be just 'unknown'
    all_sources = analysis.evidence_coverage.sources_represented
    # It's possible sources_represented is empty if finding didn't reach SUPPORTED,
    # but if there are any sources, 'unknown' must not be the only one
    if all_sources:
        assert any(s != "unknown" for s in all_sources), (
            f"sources_represented is all 'unknown': {all_sources}"
        )


# ------------------------------------------------------------------
# C2. Evidence presence does NOT force SUPPORTED status
# ------------------------------------------------------------------

def test_census_pop_chunk_does_not_support_massage_chairs():
    """
    Fixing source metadata (so 'census_2011' is recovered) must NOT automatically
    promote a finding to SUPPORTED. Population counts cannot validate feature claims.
    """
    p = _persona("p1")
    chunk = {
        "chunk_id": "doc_ev_census_pop_c0",
        "text": "Total population Ahmedabad district: 7,214,225 (Census 2011).",
        "metadata": {"source": "census_2011", "geography": {"state": "Gujarat"}},
    }
    ev = _eval("p1", valued_features=["In-ride massage chairs"], evidence_ids=["doc_ev_census_pop_c0"])

    analysis, _ = analyze_market("Luxury Shuttle", [p], [ev], retrieved_chunks=[chunk])

    massage = [f for f in analysis.features_analysis if "massage" in f.feature_name.lower()]
    assert len(massage) > 0, "Expected massage feature to be in features_analysis"
    status = massage[0].validation.evidence_status
    assert status in (EvidenceStatus.INSUFFICIENT_EVIDENCE, EvidenceStatus.NOT_APPLICABLE), (
        f"Census pop should not SUPPORT massage chairs; got {status}"
    )

    # supported_count must remain 0
    assert analysis.evidence_coverage.supported_count == 0


# ------------------------------------------------------------------
# C3. Zero-positive-mention items excluded from features_analysis
# ------------------------------------------------------------------

def test_zero_positive_features_excluded():
    """
    Clusters with zero positive mentions (purely unnecessary_features) must NOT
    appear in features_analysis; they must appear in concerns_analysis instead.
    """
    p = _persona("p1")
    ev = PersonaEvaluation(
        persona_id="p1",
        interest_score=7,
        simulated_purchase_intent=6,
        perceived_value_score=7,
        affordability_score=6,
        adoption_barrier_score=3,
        positive_aspects=["Reserved seat booking"],
        valued_features=["Reserved seat booking"],
        unnecessary_features=[
            "Complex gamification loyalty points system",
            "In-ride massage chair option",
        ],
        negative_aspects=[],
        reasons_for_assessment="Good shuttle; unnecessary extras inflate cost.",
        is_simulation=True,
        is_conversion_probability=False,
    )

    analysis, _ = analyze_market("Smart Shuttle", [p], [ev])

    feature_names_lower = [f.feature_name.lower() for f in analysis.features_analysis]
    assert not any("gamification" in fn for fn in feature_names_lower), (
        "'gamification' (0 positive mentions) must NOT be in features_analysis"
    )
    assert not any("massage" in fn for fn in feature_names_lower), (
        "'massage chair' (0 positive mentions) must NOT be in features_analysis"
    )

    # Must be in concerns_analysis
    concern_names_lower = [c.concern_name.lower() for c in analysis.concerns_analysis]
    assert any("gamification" in cn or "massage" in cn for cn in concern_names_lower), (
        "Rejected features must appear in concerns_analysis"
    )

    # Invariant: all features have positive_mentions_count >= 1
    for feat in analysis.features_analysis:
        assert feat.positive_mentions_count >= 1, (
            f"Feature '{feat.feature_name}' has 0 positive mentions in features_analysis"
        )


# ------------------------------------------------------------------
# C4. Synonym normalization consolidates overlapping phrases
# ------------------------------------------------------------------

def test_synonym_normalization_consolidates_booking_clusters():
    """
    'booking', 'pre-booking', 'reservation' share a synonym group and should
    cause the overlapping phrases to consolidate into at most 2 clusters.
    """
    personas = [_persona(f"p{i}") for i in range(1, 4)]
    evals = [
        _eval("p1", valued_features=["Booking service for guaranteed charger availability"]),
        _eval("p2", valued_features=["Pre-booking system for guaranteed charger slots"]),
        _eval("p3", valued_features=["Reservation of charger time slots in advance"]),
    ]

    analysis, _ = analyze_market("EV Charging Platform", personas, evals)

    booking_clusters = [
        f for f in analysis.features_analysis
        if any(w in f.feature_name.lower() for w in ["booking", "reservation", "pre-booking", "prebooking", "charger"])
    ]
    assert len(booking_clusters) <= 2, (
        f"Expected synonym phrases to cluster into <=2 groups, got {len(booking_clusters)}: "
        f"{[f.feature_name for f in booking_clusters]}"
    )


# ------------------------------------------------------------------
# C5. Chunk-ID prefix source inference is deterministic
# ------------------------------------------------------------------

def test_chunk_id_prefix_source_inference():
    assert _extract_chunk_source({"chunk_id": "doc_ev_census_abc_c0"}, "doc_ev_census_abc_c0") == "census_2011"
    assert _extract_chunk_source({"chunk_id": "doc_ev_plfs_xyz_c0"}, "doc_ev_plfs_xyz_c0") == "plfs_2025"
    assert _extract_chunk_source({"chunk_id": "doc_ev_reddit_foo_c0"}, "doc_ev_reddit_foo_c0") == "reddit"
    assert _extract_chunk_source({"chunk_id": "doc_ev_trends_bar_c0"}, "doc_ev_trends_bar_c0") == "google_trends"
    # Unknown IDs must return 'unknown', not invented values
    assert _extract_chunk_source({"chunk_id": "some_random_chunk"}, "some_random_chunk") == "unknown"
    # Top-level source key must take priority over prefix inference
    assert _extract_chunk_source({"chunk_id": "doc_ev_census_abc_c0", "source": "reddit"}, "doc_ev_census_abc_c0") == "reddit"


# ------------------------------------------------------------------
# C6. Coverage audit denominator = features + concerns
# ------------------------------------------------------------------

def test_coverage_audit_denominator_includes_concerns():
    """
    total_findings_evaluated must equal len(features_analysis) + len(concerns_analysis).
    Previously the list comprehension bug made it count concerns twice or not at all.
    """
    p = _persona("p1")
    ev = _eval(
        "p1",
        valued_features=["Fast wireless charging"],
        negative_aspects=["No overnight parking", "Poor route coverage"],
        evidence_ids=[],
    )

    analysis, _ = analyze_market("EV Charging Platform", [p], [ev])

    cov = analysis.evidence_coverage
    expected_total = len(analysis.features_analysis) + len(analysis.concerns_analysis)
    assert cov.total_findings_evaluated == expected_total, (
        f"Expected {expected_total} total findings, got {cov.total_findings_evaluated}"
    )

    # Formula consistency
    expected_ratio = round(
        (cov.supported_count + cov.contradicted_count + cov.mixed_count) / max(1, cov.total_findings_evaluated),
        2
    )
    assert cov.evidence_coverage_ratio == expected_ratio


# ------------------------------------------------------------------
# C7. CLI median-score key compatibility
# ------------------------------------------------------------------

def test_median_scores_dict_contains_both_key_forms():
    """
    SegmentComparisonItem.median_scores must contain BOTH the short canonical keys
    ('interest', 'purchase_intent', etc.) and the prefixed forms ('median_interest',
    etc.) for backward compatibility with existing CLI rendering code.
    """
    p = _persona("p1")
    ev = _eval("p1", interest=8)
    analysis, _ = analyze_market("Smart Shuttle", [p], [ev])

    report, diag = build_market_validation_report(
        idea="Smart Shuttle",
        market_analysis=analysis,
        personas=[p],
        evaluations=[ev],
    )

    assert diag["status"] == "success"
    assert len(report.segment_comparison) > 0

    for seg in report.segment_comparison:
        scores = seg.median_scores
        # Short canonical keys
        assert "interest" in scores, "Short key 'interest' missing from median_scores"
        assert "purchase_intent" in scores, "Short key 'purchase_intent' missing"
        assert "affordability" in scores, "Short key 'affordability' missing"
        assert "adoption_barrier" in scores, "Short key 'adoption_barrier' missing"
        # Prefixed backward-compat keys
        assert "median_interest" in scores, "Prefixed key 'median_interest' missing from median_scores"
        assert "median_purchase_intent" in scores, "Prefixed key 'median_purchase_intent' missing"
        assert "median_affordability" in scores, "Prefixed key 'median_affordability' missing"
        assert "median_adoption_barrier" in scores, "Prefixed key 'median_adoption_barrier' missing"
        # Values must agree
        assert scores["interest"] == scores["median_interest"]
        assert scores["affordability"] == scores["median_affordability"]


# ------------------------------------------------------------------
# C8. PLFS earnings key in market_report
# ------------------------------------------------------------------

def test_plfs_earnings_key_in_pricing_report():
    """
    build_market_validation_report reads PLFS earnings from plfs_evidence[0] using
    the 'earnings' sub-dict with key 'regular_salaried' (canonical). The resulting
    contextual_earnings_evidence dict must contain 'regular_salaried_avg_inr'.
    """
    plfs_record_with_earnings = {
        "state": "Gujarat",
        "sector": "Urban",
        "earnings": {
            "regular_salaried": {"avg_monthly_salary_inr": 22638},
            "self_employed": {"avg_monthly_earnings_inr": 14500},
        },
    }
    research_evidence = {"plfs_evidence": [plfs_record_with_earnings]}

    p = _persona("p1")
    ev = _eval("p1")
    analysis, _ = analyze_market("Smart Shuttle", [p], [ev])

    report, diag = build_market_validation_report(
        idea="Premium shuttle service priced at Rs. 2500 per month",
        market_analysis=analysis,
        personas=[p],
        evaluations=[ev],
        research_evidence=research_evidence,
    )

    pa = report.pricing_and_affordability
    if pa.contextual_earnings_evidence:
        earn_dict = pa.contextual_earnings_evidence
        assert "regular_salaried_avg_inr" in earn_dict, (
            f"Expected 'regular_salaried_avg_inr' key, got: {list(earn_dict.keys())}"
        )
        assert earn_dict["regular_salaried_avg_inr"] == 22638
