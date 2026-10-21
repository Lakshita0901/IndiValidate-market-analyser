"""
normalizer.py
-------------
Source-specific adapters that normalize raw evidence records from
Reddit, Google Trends, Census 2011, and PLFS 2025 into validated
EvidenceRecord instances conforming to the common schema.
"""

from hashlib import sha256
from typing import Any, Dict, List, Optional, Union

from app.schemas.evidence import (
    EvidenceRecord,
    EvidenceType,
    GeographyScope,
    SourceType,
)


# ------------------------------------------------------------------
# Geo-code helpers
# ------------------------------------------------------------------

_GEO_CODE_TO_STATE: Dict[str, str] = {
    "IN-AP": "Andhra Pradesh",
    "IN-AR": "Arunachal Pradesh",
    "IN-AS": "Assam",
    "IN-BR": "Bihar",
    "IN-CT": "Chhattisgarh",
    "IN-GA": "Goa",
    "IN-GJ": "Gujarat",
    "IN-HR": "Haryana",
    "IN-HP": "Himachal Pradesh",
    "IN-JH": "Jharkhand",
    "IN-KA": "Karnataka",
    "IN-KL": "Kerala",
    "IN-MP": "Madhya Pradesh",
    "IN-MH": "Maharashtra",
    "IN-MN": "Manipur",
    "IN-ML": "Meghalaya",
    "IN-MZ": "Mizoram",
    "IN-NL": "Nagaland",
    "IN-OR": "Odisha",
    "IN-PB": "Punjab",
    "IN-RJ": "Rajasthan",
    "IN-SK": "Sikkim",
    "IN-TN": "Tamil Nadu",
    "IN-TG": "Telangana",
    "IN-TR": "Tripura",
    "IN-UP": "Uttar Pradesh",
    "IN-UT": "Uttarakhand",
    "IN-WB": "West Bengal",
    "IN-DL": "Delhi",
    "IN-JK": "Jammu & Kashmir",
    "IN-LA": "Ladakh",
    "IN-CH": "Chandigarh",
    "IN-PY": "Puducherry",
}


def _make_id(source: str, *parts: Any) -> str:
    """Generate a deterministic 12-char hex ID from source and key parts."""
    raw = f"{source}|" + "|".join(str(p).strip().lower() for p in parts if p is not None)
    digest = sha256(raw.encode("utf-8")).hexdigest()[:12]
    return f"ev_{source}_{digest}"


def _safe_float(val: Any) -> Optional[float]:
    if val is None or val == "N/A":
        return None
    try:
        f = float(val)
        return None if (f != f) else round(f, 2)  # NaN check
    except (ValueError, TypeError):
        return None


def _safe_int(val: Any) -> Optional[int]:
    if val is None or val == "N/A":
        return None
    try:
        return int(float(val))
    except (ValueError, TypeError):
        return None


def _fmt_int(val: Any) -> str:
    i = _safe_int(val)
    return f"{i:,}" if i is not None else "N/A"


def _fmt_float(val: Any, decimals: int = 2) -> str:
    f = _safe_float(val)
    return f"{f:,.{decimals}f}" if f is not None else "N/A"


# ------------------------------------------------------------------
# 1. Reddit Adapter
# ------------------------------------------------------------------

def normalize_reddit_records(raw_records: Optional[List[Dict[str, Any]]]) -> List[EvidenceRecord]:
    """
    Normalize raw Reddit records from Kaggle dataset search.
    Each relevant discussion post becomes an individual EvidenceRecord.
    Skips error or 'no_results' status records.
    """
    evidence: List[EvidenceRecord] = []
    if not raw_records or not isinstance(raw_records, list):
        return evidence

    for item in raw_records:
        if not isinstance(item, dict):
            continue
        if item.get("status") in ("error", "no_results") or "error" in item:
            continue

        title = str(item.get("title", "")).strip()
        text = str(item.get("text", "")).strip()
        if not title and not text:
            continue

        subreddit = item.get("subreddit")
        score = _safe_int(item.get("score"))
        created_at = str(item.get("created_at", "")).strip() or None
        url = item.get("url")
        keywords_matched = item.get("keywords_matched", [])
        relevance_query = item.get("relevance_query", "")

        ev_id = _make_id("reddit", subreddit, title[:80], created_at or "")

        title_display = f"Reddit Discussion: {title[:75]}" if title else f"Reddit Discussion in r/{subreddit or 'general'}"
        content_parts = []
        if subreddit:
            content_parts.append(f"Subreddit: r/{subreddit}")
        if title:
            content_parts.append(f"Title: '{title}'")
        if text:
            content_parts.append(f"Excerpt: '{text}'")
        if keywords_matched:
            content_parts.append(f"Matched Keywords: {', '.join(keywords_matched)}")
        content = ". ".join(content_parts)

        provenance = {
            "source_type": item.get("source_type", "historical_dataset"),
            "dataset": item.get("dataset", "Kaggle Reddit dataset"),
            "url": url,
        }

        meta = {
            "subreddit": subreddit,
            "post_title": title,
            "post_text": text,
            "score": score,
            "keywords_matched": keywords_matched,
            "relevance_query": relevance_query,
            "created_at": created_at,
        }

        limitations = [
            "Historical dataset observation from Kaggle archive; does not represent live Reddit activity.",
            "Keyword heuristic match; sentiment and contextual relevance may vary.",
        ]

        try:
            rec = EvidenceRecord(
                evidence_id=ev_id,
                source=SourceType.REDDIT,
                evidence_type=EvidenceType.DISCUSSION,
                title=title_display,
                content=content,
                value=score,
                unit="upvotes" if score is not None else None,
                geography=None,
                time_period=created_at,
                retrieved_at=None,
                provenance=provenance,
                metadata=meta,
                limitations=limitations,
            )
            evidence.append(rec)
        except Exception:
            continue

    return evidence


# ------------------------------------------------------------------
# 2. Google Trends Adapter
# ------------------------------------------------------------------

def normalize_trends_records(raw_records: Optional[List[Dict[str, Any]]]) -> List[EvidenceRecord]:
    """
    Normalize raw Google Trends keyword responses.
    Each successful keyword query becomes an EvidenceRecord with normalized
    search interest indices and trend direction.
    """
    evidence: List[EvidenceRecord] = []
    if not raw_records or not isinstance(raw_records, list):
        return evidence

    for item in raw_records:
        if not isinstance(item, dict):
            continue
        if item.get("status") in ("error", "no_data") or "error" in item:
            continue

        keyword = str(item.get("keyword", "")).strip()
        if not keyword:
            continue

        geo = item.get("geo", "IN")
        time_range = item.get("time_range", "today 12-m")
        latest_val = _safe_float(item.get("latest_value"))
        avg_val = _safe_float(item.get("average_value"))
        peak_val = _safe_float(item.get("peak_value"))
        trend_dir = item.get("trend_direction", "unknown")
        rel_interest = item.get("relative_interest", [])
        date_labels = item.get("date_labels", [])
        cache_hit = bool(item.get("cache_hit", False))
        cache_age = _safe_int(item.get("cache_age_seconds"))
        retrieval_note = item.get("retrieval_note", "")

        period_str = time_range
        if date_labels and len(date_labels) >= 2:
            period_str = f"{date_labels[0]} to {date_labels[-1]} ({time_range})"

        state_name = _GEO_CODE_TO_STATE.get(geo)
        geo_scope = GeographyScope(
            country="India",
            state=state_name,
            district=None,
            rural_urban=None,
            level="state" if state_name else "national",
        )

        ev_id = _make_id("trends", keyword, geo, time_range)
        content = (
            f"Google Trends relative search interest for '{keyword}' in {geo} ({period_str}): "
            f"latest index={latest_val}/100, average index={avg_val}/100, peak index={peak_val}/100. "
            f"Trend direction: {trend_dir}."
        )

        provenance = {
            "source": "Google Trends via pytrends",
            "endpoint": "interest_over_time",
            "geo": geo,
            "timeframe": time_range,
        }

        meta = {
            "keyword": keyword,
            "geo_code": geo,
            "timeframe": time_range,
            "trend_direction": trend_dir,
            "latest_value": latest_val,
            "average_value": avg_val,
            "peak_value": peak_val,
            "relative_interest_series": rel_interest,
            "date_labels": date_labels,
            "cache_hit": cache_hit,
            "cache_age_seconds": cache_age,
            "retrieval_note": retrieval_note,
        }

        limitations = [
            "Relative search interest on a 0-100 scale; does not represent absolute search volume.",
            "Normalized against peak interest within the selected time window and region.",
        ]
        if cache_hit:
            limitations.append(
                f"Served from local cache (age: {cache_age}s); reflects observation at earlier fetch time."
            )

        try:
            rec = EvidenceRecord(
                evidence_id=ev_id,
                source=SourceType.GOOGLE_TRENDS,
                evidence_type=EvidenceType.SEARCH_INTEREST,
                title=f"Google Trends: '{keyword}' search interest ({geo})",
                content=content,
                value=latest_val,
                unit="relative_interest_index",
                geography=geo_scope,
                time_period=period_str,
                retrieved_at=None,
                provenance=provenance,
                metadata=meta,
                limitations=limitations,
            )
            evidence.append(rec)
        except Exception:
            continue

    return evidence


# ------------------------------------------------------------------
# 3. Census 2011 Adapter
# ------------------------------------------------------------------

def normalize_census_records(raw_evidence: Optional[List[Dict[str, Any]]]) -> List[EvidenceRecord]:
    """
    Normalize Census 2011 structured evidence into granular EvidenceRecords:
      - Total Population & Sex Ratio
      - Total Households
      - Literacy Rate (crude and effective)
      - Workforce Participation & Worker Categories
      - Educational Attainment - Graduate & Above (Table C-08)
      - Higher Education Disciplines (Table C-08A)
    """
    evidence: List[EvidenceRecord] = []
    if not raw_evidence or not isinstance(raw_evidence, list):
        return evidence

    for rec in raw_evidence:
        if not isinstance(rec, dict):
            continue
        if rec.get("status") == "error":
            continue

        geo = rec.get("geography", {})
        state_name = geo.get("state")
        dist_name = geo.get("district")
        level = geo.get("level")
        tru = geo.get("tru", "Total")
        loc_display = f"{dist_name}, {state_name}" if dist_name else (state_name or "India")

        geo_scope = GeographyScope(
            country="India",
            state=state_name,
            district=dist_name,
            rural_urban=tru,
            level=level,
        )

        pca = rec.get("pca", {})
        if pca and isinstance(pca, dict):
            # 1. Population & Sex Ratio
            pop_data = pca.get("population", {})
            tot_p = _safe_int(pop_data.get("total"))
            tot_m = _safe_int(pop_data.get("male"))
            tot_f = _safe_int(pop_data.get("female"))
            sex_ratio = _safe_float(pop_data.get("sex_ratio_females_per_1000_males"))

            if tot_p is not None:
                ev_id = _make_id("census", loc_display, tru, "population")
                tot_p_str = _fmt_int(tot_p)
                tot_m_str = _fmt_int(tot_m)
                tot_f_str = _fmt_int(tot_f)
                sex_ratio_str = str(sex_ratio) if sex_ratio is not None else "N/A"
                content = (
                    f"Census 2011 Total Population in {loc_display} ({tru}): {tot_p_str} persons "
                    f"(Male: {tot_m_str}, Female: {tot_f_str}, "
                    f"Sex Ratio: {sex_ratio_str} females per 1,000 males)."
                )
                evidence.append(
                    EvidenceRecord(
                        evidence_id=ev_id,
                        source=SourceType.CENSUS,
                        evidence_type=EvidenceType.DEMOGRAPHIC_STATISTIC,
                        title=f"Census 2011: Population ({loc_display}, {tru})",
                        content=content,
                        value=tot_p,
                        unit="people",
                        geography=geo_scope,
                        time_period="2011",
                        retrieved_at=None,
                        provenance={"dataset": "Primary Census Abstract (PCA 2011)", "census_year": 2011},
                        metadata={"male_population": tot_m, "female_population": tot_f, "sex_ratio": sex_ratio},
                        limitations=["Official Census 2011 benchmark; does not reflect subsequent population growth."],
                    )
                )

            # 2. Households
            no_hh = _safe_int(pca.get("households"))
            if no_hh is not None:
                ev_id = _make_id("census", loc_display, tru, "households")
                evidence.append(
                    EvidenceRecord(
                        evidence_id=ev_id,
                        source=SourceType.CENSUS,
                        evidence_type=EvidenceType.DEMOGRAPHIC_STATISTIC,
                        title=f"Census 2011: Households ({loc_display}, {tru})",
                        content=f"Census 2011 Total Households in {loc_display} ({tru}): {no_hh:,} households.",
                        value=no_hh,
                        unit="households",
                        geography=geo_scope,
                        time_period="2011",
                        retrieved_at=None,
                        provenance={"dataset": "Primary Census Abstract (PCA 2011)", "census_year": 2011},
                        metadata={"households_count": no_hh},
                        limitations=["Official Census 2011 benchmark; does not reflect subsequent household formation."],
                    )
                )

            # 3. Literacy
            lit_data = pca.get("literacy", {})
            crude_lit = _safe_float(lit_data.get("crude_literacy_rate_percent"))
            eff_lit = _safe_float(lit_data.get("effective_literacy_rate_percent"))
            p_lit = _safe_int(lit_data.get("literate_total"))
            if crude_lit is not None:
                ev_id = _make_id("census", loc_display, tru, "literacy")
                eff_lit_str = f"{eff_lit}%" if eff_lit is not None else "N/A"
                p_lit_str = _fmt_int(p_lit)
                content = (
                    f"Census 2011 Crude Literacy Rate in {loc_display} ({tru}): {crude_lit}% "
                    f"(Effective Rate: {eff_lit_str}, Total Literates: {p_lit_str})."
                )
                evidence.append(
                    EvidenceRecord(
                        evidence_id=ev_id,
                        source=SourceType.CENSUS,
                        evidence_type=EvidenceType.EDUCATION_STATISTIC,
                        title=f"Census 2011: Literacy Rate ({loc_display}, {tru})",
                        content=content,
                        value=crude_lit,
                        unit="percent",
                        geography=geo_scope,
                        time_period="2011",
                        retrieved_at=None,
                        provenance={"dataset": "Primary Census Abstract (PCA 2011)", "census_year": 2011},
                        metadata={"crude_literacy_rate": crude_lit, "effective_literacy_rate": eff_lit, "total_literates": p_lit},
                        limitations=["Official Census 2011 benchmark."],
                    )
                )

            # 4. Workforce Participation & Categories
            workers = pca.get("workers", {})
            wpr = _safe_float(workers.get("work_participation_rate_percent"))
            tot_w = _safe_int(workers.get("total_workers"))
            cats = workers.get("categories", {})
            if wpr is not None:
                ev_id = _make_id("census", loc_display, tru, "workforce")
                tot_w_str = _fmt_int(tot_w)
                cult_share = _safe_float(cats.get("cultivators", {}).get("share_of_workers_percent"))
                agri_share = _safe_float(cats.get("agricultural_labourers", {}).get("share_of_workers_percent"))
                hh_share = _safe_float(cats.get("household_industry", {}).get("share_of_workers_percent"))
                other_share = _safe_float(cats.get("other_workers", {}).get("share_of_workers_percent"))

                content = (
                    f"Census 2011 Work Participation Rate in {loc_display} ({tru}): {wpr}% ({tot_w_str} total workers). "
                    f"Categories: Cultivators {cult_share}%, Agricultural Labourers {agri_share}%, "
                    f"Household Industry {hh_share}%, Other Workers {other_share}%."
                )
                evidence.append(
                    EvidenceRecord(
                        evidence_id=ev_id,
                        source=SourceType.CENSUS,
                        evidence_type=EvidenceType.LABOUR_STATISTIC,
                        title=f"Census 2011: Work Participation ({loc_display}, {tru})",
                        content=content,
                        value=wpr,
                        unit="percent",
                        geography=geo_scope,
                        time_period="2011",
                        retrieved_at=None,
                        provenance={"dataset": "Primary Census Abstract (PCA 2011)", "census_year": 2011},
                        metadata={
                            "total_workers": tot_w,
                            "work_participation_rate": wpr,
                            "cultivator_share": cult_share,
                            "agricultural_labourer_share": agri_share,
                            "household_industry_share": hh_share,
                            "other_worker_share": other_share,
                        },
                        limitations=["Census 2011 workforce definitions (Main + Marginal workers)."],
                    )
                )

        # 5. Table C-08 (Educational Attainment)
        c08 = rec.get("education", {})
        if c08 and isinstance(c08, dict) and c08.get("status") != "error":
            c08_summary = c08.get("summary", {})
            c08_levels = c08_summary.get("levels", {})
            grad_p = _safe_int(c08_levels.get("graduate_and_above", {}).get("persons"))
            is_fallback = bool(c08.get("is_state_fallback", False))
            c08_tru = c08.get("tru", tru)

            if grad_p is not None:
                ev_id = _make_id("census", loc_display, c08_tru, "c08_graduates")
                fallback_tag = " (State-level fallback)" if is_fallback else ""
                content = (
                    f"Census 2011 Table C-08 Graduate and Above population in {loc_display}{fallback_tag} ({c08_tru}): "
                    f"{grad_p:,} persons."
                )
                limits = ["Census 2011 Table C-08 educational classification."]
                if is_fallback:
                    limits.append("District-level C-08 data unavailable for this state; state-level aggregate shown as fallback.")

                evidence.append(
                    EvidenceRecord(
                        evidence_id=ev_id,
                        source=SourceType.CENSUS,
                        evidence_type=EvidenceType.EDUCATION_STATISTIC,
                        title=f"Census 2011: Graduate & Above Education ({loc_display}{fallback_tag}, {c08_tru})",
                        content=content,
                        value=grad_p,
                        unit="people",
                        geography=geo_scope,
                        time_period="2011",
                        retrieved_at=None,
                        provenance={
                            "dataset": "Table C-08 (Age x Education x Sex)",
                            "table": "DDW-2400C-08.xlsx" if not is_fallback else "DDW-0000C-08.xlsx",
                            "census_year": 2011,
                        },
                        metadata={
                            "graduate_and_above": grad_p,
                            "is_state_fallback": is_fallback,
                            "c08_tru": c08_tru,
                        },
                        limitations=limits,
                    )
                )

        # 6. Table C-08A (Higher Education Disciplines)
        c08a = rec.get("higher_education", {})
        if c08a and isinstance(c08a, dict) and c08a.get("status") != "error":
            c08a_summary = c08a.get("summary", {})
            disc = c08a_summary.get("disciplines", {})
            eng = _safe_int(disc.get("engineering_and_technology", {}).get("persons"))
            med = _safe_int(disc.get("medicine", {}).get("persons"))
            teach = _safe_int(disc.get("teaching", {}).get("persons"))
            agri = _safe_int(disc.get("agriculture_and_dairying", {}).get("persons"))
            is_fallback = bool(c08a.get("is_state_fallback", False))

            if eng is not None or med is not None:
                ev_id = _make_id("census", loc_display, "c08a_disciplines")
                fallback_tag = " (State-level fallback)" if is_fallback else ""
                eng_str = _fmt_int(eng)
                med_str = _fmt_int(med)
                teach_str = _fmt_int(teach)
                agri_str = _fmt_int(agri)
                content = (
                    f"Census 2011 Table C-08A Higher Education Disciplines in {loc_display}{fallback_tag}: "
                    f"Engineering & Tech: {eng_str}, Medicine: {med_str}, "
                    f"Teaching: {teach_str}, Agriculture & Dairying: {agri_str}."
                )
                limits = ["Census 2011 Table C-08A discipline classification."]
                if is_fallback:
                    limits.append("District-level C-08A data unavailable for this state; state-level aggregate shown as fallback.")

                evidence.append(
                    EvidenceRecord(
                        evidence_id=ev_id,
                        source=SourceType.CENSUS,
                        evidence_type=EvidenceType.EDUCATION_STATISTIC,
                        title=f"Census 2011: Higher Education Disciplines ({loc_display}{fallback_tag})",
                        content=content,
                        value={
                            "engineering_and_technology": eng or 0,
                            "medicine": med or 0,
                            "teaching": teach or 0,
                            "agriculture_and_dairying": agri or 0,
                        },
                        unit="people",
                        geography=geo_scope,
                        time_period="2011",
                        retrieved_at=None,
                        provenance={
                            "dataset": "Table C-08A (Higher Education Disciplines)",
                            "table": "DDW-2400C-08A.xlsx" if not is_fallback else "DDW-0000C-08A.xlsx",
                            "census_year": 2011,
                        },
                        metadata={
                            "engineering_and_technology": eng,
                            "medicine": med,
                            "teaching": teach,
                            "agriculture_and_dairying": agri,
                            "is_state_fallback": is_fallback,
                        },
                        limitations=limits,
                    )
                )

    return evidence


# ------------------------------------------------------------------
# 4. PLFS 2025 Adapter
# ------------------------------------------------------------------

def normalize_plfs_records(raw_evidence: Optional[List[Dict[str, Any]]]) -> List[EvidenceRecord]:
    """
    Normalize PLFS 2025 survey-weighted evidence into granular EvidenceRecords:
      - Headline Labour Force Indicators (Usual Status ps+ss, Age 15+)
      - Regular Salaried Monthly Earnings
      - Self-Employed Monthly Earnings
      - Educational Attainment (Graduate & Above %, Age 15+)
      - Household Characteristics & Consumer Expenditure (if available)
    """
    evidence: List[EvidenceRecord] = []
    if not raw_evidence or not isinstance(raw_evidence, list):
        return evidence

    for rec in raw_evidence:
        if not isinstance(rec, dict):
            continue
        if rec.get("status") == "error":
            continue

        geo = rec.get("geography", {})
        state_name = geo.get("state")
        dist_name = geo.get("district")
        sector = geo.get("sector", "Total")
        level = geo.get("level")
        loc_display = f"{dist_name}, {state_name}" if dist_name else (state_name or "India")

        geo_scope = GeographyScope(
            country="India",
            state=state_name,
            district=dist_name,
            rural_urban=sector,
            level=level,
        )

        sample_meta = rec.get("sample_metadata", {})
        sample_persons = _safe_int(sample_meta.get("sample_persons_total"))
        sample_15plus = _safe_int(sample_meta.get("sample_persons_age_15_plus"))
        est_pop_15plus = _safe_int(sample_meta.get("estimated_population_age_15_plus"))

        prov_base = {
            "survey": "Periodic Labour Force Survey (PLFS) 2025",
            "period": "January - December 2025 (Annual)",
            "file": "cperv12025.csv",
            "sample_size_persons": sample_persons,
            "sample_size_age_15_plus": sample_15plus,
            "weighting": "MoSPI Survey Multiplier ('mult' weighted)",
        }

        plfs_limits = [
            "Sample survey estimate from MoSPI PLFS 2025 microdata using sampling weights; not a full census.",
            "Labour indicators calculated for working age population (Age 15 and above).",
        ]

        # 1. Headline Labour Indicators (Usual Status ps+ss)
        labour = rec.get("labour_indicators", {})
        us = labour.get("usual_status_ps_plus_ss", {})
        lfpr_us = _safe_float(us.get("lfpr_percent"))
        wpr_us = _safe_float(us.get("wpr_percent"))
        ur_us = _safe_float(us.get("unemployment_rate_percent"))

        if lfpr_us is not None:
            ev_id = _make_id("plfs", loc_display, sector, "labour_usual_status")
            content = (
                f"PLFS 2025 Headline Labour Indicators for {loc_display} ({sector}, Age 15+): "
                f"Labour Force Participation Rate (LFPR) = {lfpr_us}%, Worker Population Ratio (WPR) = {wpr_us}%, "
                f"Unemployment Rate (UR) = {ur_us}% (Usual Status ps+ss, survey-weighted)."
            )
            evidence.append(
                EvidenceRecord(
                    evidence_id=ev_id,
                    source=SourceType.PLFS,
                    evidence_type=EvidenceType.LABOUR_STATISTIC,
                    title=f"PLFS 2025: Labour Indicators (Usual Status, {loc_display})",
                    content=content,
                    value={
                        "lfpr_percent": lfpr_us,
                        "wpr_percent": wpr_us,
                        "unemployment_rate_percent": ur_us,
                    },
                    unit="percent",
                    geography=geo_scope,
                    time_period="2025 (Annual)",
                    retrieved_at=None,
                    provenance=prov_base,
                    metadata={
                        "benchmark_population": "Age 15 and above (Working Age)",
                        "status_criterion": "Usual Status (ps+ss)",
                        "lfpr": lfpr_us,
                        "wpr": wpr_us,
                        "unemployment_rate": ur_us,
                        "survey_weighted": True,
                    },
                    limitations=plfs_limits,
                )
            )

        # 2. Regular Salaried Monthly Earnings
        earnings = rec.get("earnings", {})
        sal = earnings.get("regular_salaried", {})
        sal_avg = _safe_float(sal.get("avg_monthly_salary_inr"))
        sal_med = _safe_float(sal.get("median_monthly_salary_inr"))
        sal_n = _safe_int(sal.get("sample_size"))

        if sal_avg is not None and sal_avg > 0:
            ev_id = _make_id("plfs", loc_display, sector, "earnings_salary")
            sal_med_str = f"INR {sal_med:,.2f}/month" if sal_med is not None else "N/A"
            sal_n_str = _fmt_int(sal_n)
            content = (
                f"PLFS 2025 Regular Salaried Monthly Earnings in {loc_display} ({sector}): "
                f"Average = INR {sal_avg:,.2f}/month (Median: {sal_med_str}, sample: {sal_n_str} workers)."
            )
            evidence.append(
                EvidenceRecord(
                    evidence_id=ev_id,
                    source=SourceType.PLFS,
                    evidence_type=EvidenceType.EARNINGS_STATISTIC,
                    title=f"PLFS 2025: Regular Salaried Monthly Earnings ({loc_display})",
                    content=content,
                    value=sal_avg,
                    unit="INR/month",
                    geography=geo_scope,
                    time_period="2025 (Annual)",
                    retrieved_at=None,
                    provenance=prov_base,
                    metadata={
                        "average_monthly_salary_inr": sal_avg,
                        "median_monthly_salary_inr": sal_med,
                        "sample_size": sal_n,
                        "survey_weighted": True,
                    },
                    limitations=[
                        "Weighted average from reported earnings of regular wage/salaried employees in PLFS 2025.",
                    ],
                )
            )

        # 3. Self-Employed Monthly Earnings
        se = earnings.get("self_employed", {})
        se_avg = _safe_float(se.get("avg_monthly_earnings_inr"))
        se_med = _safe_float(se.get("median_monthly_earnings_inr"))
        se_n = _safe_int(se.get("sample_size"))

        if se_avg is not None and se_avg > 0:
            ev_id = _make_id("plfs", loc_display, sector, "earnings_self_employed")
            se_med_str = f"INR {se_med:,.2f}/month" if se_med is not None else "N/A"
            se_n_str = _fmt_int(se_n)
            content = (
                f"PLFS 2025 Self-Employed Monthly Gross Earnings/Net Profit in {loc_display} ({sector}): "
                f"Average = INR {se_avg:,.2f}/month (Median: {se_med_str}, sample: {se_n_str} workers)."
            )
            evidence.append(
                EvidenceRecord(
                    evidence_id=ev_id,
                    source=SourceType.PLFS,
                    evidence_type=EvidenceType.EARNINGS_STATISTIC,
                    title=f"PLFS 2025: Self-Employed Monthly Earnings ({loc_display})",
                    content=content,
                    value=se_avg,
                    unit="INR/month",
                    geography=geo_scope,
                    time_period="2025 (Annual)",
                    retrieved_at=None,
                    provenance=prov_base,
                    metadata={
                        "average_monthly_earnings_inr": se_avg,
                        "median_monthly_earnings_inr": se_med,
                        "sample_size": se_n,
                        "survey_weighted": True,
                    },
                    limitations=[
                        "Weighted average from reported gross earnings/net profit (including business losses) in PLFS 2025.",
                    ],
                )
            )

        # 4. Educational Attainment (PLFS 2025)
        edu = rec.get("education", {})
        grad_pct = _safe_float(edu.get("graduate_and_above_percent"))
        sec_pct = _safe_float(edu.get("secondary_and_above_percent"))
        not_lit_pct = _safe_float(edu.get("not_literate_percent"))

        if grad_pct is not None:
            ev_id = _make_id("plfs", loc_display, sector, "education_attainment")
            content = (
                f"PLFS 2025 Educational Attainment in {loc_display} ({sector}, Age 15+): "
                f"Graduate & Above = {grad_pct}%, Secondary & Above = {sec_pct}%, Not Literate = {not_lit_pct}%."
            )
            evidence.append(
                EvidenceRecord(
                    evidence_id=ev_id,
                    source=SourceType.PLFS,
                    evidence_type=EvidenceType.EDUCATION_STATISTIC,
                    title=f"PLFS 2025: Educational Attainment ({loc_display}, Age 15+)",
                    content=content,
                    value=grad_pct,
                    unit="percent",
                    geography=geo_scope,
                    time_period="2025 (Annual)",
                    retrieved_at=None,
                    provenance=prov_base,
                    metadata={
                        "graduate_and_above_percent": grad_pct,
                        "secondary_and_above_percent": sec_pct,
                        "not_literate_percent": not_lit_pct,
                        "survey_weighted": True,
                    },
                    limitations=["Sample survey estimates for Age 15+ population in PLFS 2025."],
                )
            )

        # 5. Household Characteristics (from chhv12025.csv)
        hh = rec.get("household", {})
        if hh and isinstance(hh, dict) and hh.get("status") == "available":
            avg_size = _safe_float(hh.get("avg_household_size"))
            avg_hce = _safe_float(hh.get("avg_monthly_consumer_expenditure_inr"))
            hh_n = _safe_int(hh.get("sample_households"))

            if avg_size is not None or avg_hce is not None:
                ev_id = _make_id("plfs", loc_display, sector, "household_context")
                avg_size_str = str(avg_size) if avg_size is not None else "N/A"
                hce_str = f"INR {avg_hce:,.2f}" if avg_hce is not None else "N/A"
                hh_n_str = _fmt_int(hh_n)
                content = (
                    f"PLFS 2025 Household Context for {loc_display} ({sector}): "
                    f"Average Household Size = {avg_size_str} persons, "
                    f"Average Monthly Household Consumer Expenditure = {hce_str} (sample: {hh_n_str} households)."
                )
                evidence.append(
                    EvidenceRecord(
                        evidence_id=ev_id,
                        source=SourceType.PLFS,
                        evidence_type=EvidenceType.HOUSEHOLD_STATISTIC,
                        title=f"PLFS 2025: Household Size & Expenditure ({loc_display})",
                        content=content,
                        value={"avg_household_size": avg_size, "avg_monthly_consumer_expenditure_inr": avg_hce},
                        unit="INR/month" if avg_hce else "persons",
                        geography=geo_scope,
                        time_period="2025 (Annual)",
                        retrieved_at=None,
                        provenance={
                            "survey": "Periodic Labour Force Survey (PLFS) 2025",
                            "file": "chhv12025.csv",
                            "sample_households": hh_n,
                            "weighting": "MoSPI Survey Multiplier ('mult' weighted)",
                        },
                        metadata={
                            "avg_household_size": avg_size,
                            "avg_monthly_consumer_expenditure_inr": avg_hce,
                            "sample_households": hh_n,
                            "survey_weighted": True,
                        },
                        limitations=["Household consumer expenditure from MoSPI PLFS 2025 schedule."],
                    )
                )

    return evidence


# ------------------------------------------------------------------
# Master Normalization Function
# ------------------------------------------------------------------

def normalize_all_evidence(
    reddit_evidence: Optional[List[Dict[str, Any]]] = None,
    trends_evidence: Optional[List[Dict[str, Any]]] = None,
    census_evidence: Optional[List[Dict[str, Any]]] = None,
    plfs_evidence: Optional[List[Dict[str, Any]]] = None,
) -> List[EvidenceRecord]:
    """
    Main normalization entry point.
    Converts successful raw results from all four evidence sources into
    a unified list of validated EvidenceRecord instances.
    Each source is handled independently; a failure or missing data in one
    source does not prevent valid evidence from other sources from normalizing.
    """
    normalized: List[EvidenceRecord] = []

    if reddit_evidence:
        normalized.extend(normalize_reddit_records(reddit_evidence))

    if trends_evidence:
        normalized.extend(normalize_trends_records(trends_evidence))

    if census_evidence:
        normalized.extend(normalize_census_records(census_evidence))

    if plfs_evidence:
        normalized.extend(normalize_plfs_records(plfs_evidence))

    return normalized
