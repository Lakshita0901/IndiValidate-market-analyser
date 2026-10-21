"""
census_tool.py
--------------
Retrieves REAL Census 2011 demographic, educational, and workforce evidence
directly from local official Census 2011 datasets:

1. Primary Census Abstract (PCA 2011):
   - Total/Male/Female Population
   - Total Households
   - Age 0-6 population
   - SC/ST population
   - Literacy rates (crude & effective)
   - Total, Main, Marginal, and Non-workers
   - Worker categories (Cultivators, Agricultural Labourers, Household Industry, Other Workers)
   - Area and Population Density
   - Geographic context

2. Table C-08 (Age x Education x Sex):
   - DDW-0000C-08.xlsx (India + all 35 States)
   - DDW-2400C-08.xlsx (Gujarat state + 26 districts)
   - Educational attainment breakdown (Illiterate to Graduate & above)
   - Age-wise population and literacy breakdown
   - Total / Rural / Urban disaggregation

3. Table C-08 Appendix (C-08A - Higher Education Disciplines):
   - DDW-0000C-08A.xlsx (India + all 35 States)
   - DDW-2400C-08A.xlsx (Gujarat state + 26 districts)
   - Disciplines: Engineering & Technology, Medicine, Agriculture & Dairying,
     Veterinary, Teaching, Non-technical Graduate/Post-Graduate, Others
   - Age-wise distribution (15+)
   - Total / Rural / Urban disaggregation

Design principles:
- 100% deterministic local dataset queries (No mock data, no LLM reasoning here)
- Reads official Excel (.xlsx) and CSV files locally using pandas and openpyxl
- Graceful fallbacks: non-Gujarat district queries fallback to state-level C-08/C-08A
- Robust error isolation: missing/corrupted files return structured errors
"""

import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union
import pandas as pd
import openpyxl
from langchain_core.tools import tool

# ------------------------------------------------------------------
# File Paths and Directory Architecture
# ------------------------------------------------------------------
CENSUS_BASE_DIR = Path("data/census")
PCA_DIR = CENSUS_BASE_DIR / "pca"
C08_INDIA_DIR = CENSUS_BASE_DIR / "c08" / "india"
C08_GUJARAT_DIR = CENSUS_BASE_DIR / "c08" / "gujarat"

PCA_DEFAULT_FILE = PCA_DIR / "pca-total.csv"
C08_INDIA_DEFAULT = C08_INDIA_DIR / "DDW-0000C-08.xlsx"
C08A_INDIA_DEFAULT = C08_INDIA_DIR / "DDW-0000C-08A.xlsx"
C08_GUJARAT_DEFAULT = C08_GUJARAT_DIR / "DDW-2400C-08.xlsx"
C08A_GUJARAT_DEFAULT = C08_GUJARAT_DIR / "DDW-2400C-08A.xlsx"

# ------------------------------------------------------------------
# Geographic Knowledge Base (Census 2011 Official Codes & Aliases)
# ------------------------------------------------------------------
STATE_CODE_TO_NAME = {
    0: "India",
    1: "Jammu & Kashmir", 2: "Himachal Pradesh", 3: "Punjab", 4: "Chandigarh",
    5: "Uttarakhand", 6: "Haryana", 7: "NCT of Delhi", 8: "Rajasthan",
    9: "Uttar Pradesh", 10: "Bihar", 11: "Sikkim", 12: "Arunachal Pradesh",
    13: "Nagaland", 14: "Manipur", 15: "Mizoram", 16: "Tripura",
    17: "Meghalaya", 18: "Assam", 19: "West Bengal", 20: "Jharkhand",
    21: "Odisha", 22: "Chhattisgarh", 23: "Madhya Pradesh", 24: "Gujarat",
    25: "Daman & Diu", 26: "Dadra & Nagar Haveli", 27: "Maharashtra",
    28: "Andhra Pradesh", 29: "Karnataka", 30: "Goa", 31: "Lakshadweep",
    32: "Kerala", 33: "Tamil Nadu", 34: "Puducherry", 35: "Andaman & Nicobar Islands"
}

STATE_NAME_TO_CODE = {name.lower(): code for code, name in STATE_CODE_TO_NAME.items()}
STATE_NAME_TO_CODE.update({
    "delhi": 7,
    "new delhi": 7,
    "orissa": 21,
    "pondicherry": 34,
    "uttaranchal": 5,
    "jammu and kashmir": 1,
    "andaman and nicobar": 35,
    "andaman and nicobar islands": 35,
    "dadra and nagar haveli": 26,
    "daman and diu": 25,
})

DISTRICT_ALIASES = {
    "ahmedabad": "ahmadabad",
    "baroda": "vadodara",
    "bangalore": "bangalore",
    "bengaluru": "bangalore",
    "bombay": "mumbai",
    "kutch": "kachchh",
    "banaskantha": "banas kantha",
    "sabarkantha": "sabar kantha",
    "panchmahal": "panch mahals",
    "panchmahals": "panch mahals",
    "dahod": "dohad",
    "dangs": "the dangs",
    "dang": "the dangs",
    "mehsana": "mahesana",
    "calcutta": "kolkata",
    "madras": "chennai",
    "trivandrum": "thiruvananthapuram",
    "cochin": "ernakulam",
    "kochi": "ernakulam",
    "gurgaon": "gurgaon",
    "gurugram": "gurgaon",
}

# In-memory caches to prevent redundant disk I/O
_PCA_DF: Optional[pd.DataFrame] = None
_C08_GUJARAT_ROWS: Optional[List[tuple]] = None
_C08A_GUJARAT_ROWS: Optional[List[tuple]] = None
_C08_INDIA_ROWS: Optional[List[tuple]] = None
_C08A_INDIA_ROWS: Optional[List[tuple]] = None
_DISTRICT_INDEX: Optional[Dict[str, Dict[str, Any]]] = None


def clear_cache():
    """Clear memory caches (useful for testing and reloading datasets)."""
    global _PCA_DF, _C08_GUJARAT_ROWS, _C08A_GUJARAT_ROWS, _C08_INDIA_ROWS, _C08A_INDIA_ROWS, _DISTRICT_INDEX
    _PCA_DF = None
    _C08_GUJARAT_ROWS = None
    _C08A_GUJARAT_ROWS = None
    _C08_INDIA_ROWS = None
    _C08A_INDIA_ROWS = None
    _DISTRICT_INDEX = None


def _load_pca_df(pca_path: Path = PCA_DEFAULT_FILE) -> Tuple[Optional[pd.DataFrame], Optional[str]]:
    global _PCA_DF
    if _PCA_DF is not None:
        return _PCA_DF, None
    if not pca_path.exists():
        csvs = list(pca_path.parent.glob("*.csv")) if pca_path.parent.exists() else []
        if csvs:
            pca_path = csvs[0]
        else:
            return None, f"PCA dataset file not found at {pca_path}."
    try:
        df = pd.read_csv(pca_path)
        if df.empty or len(df.columns) < 10:
            return None, f"PCA dataset file at {pca_path} is empty or malformed."
        df.columns = [c.strip() for c in df.columns]
        _PCA_DF = df
        return _PCA_DF, None
    except Exception as e:
        return None, f"Failed to read PCA file {pca_path}: {e}"


def _load_excel_rows(excel_path: Path) -> Tuple[Optional[List[tuple]], Optional[str]]:
    if not excel_path.exists():
        return None, f"Excel file not found at {excel_path}."
    try:
        wb = openpyxl.load_workbook(excel_path, data_only=True, read_only=True)
        sheet = wb.active
        rows = [r for r in sheet.iter_rows(values_only=True)]
        wb.close()
        if len(rows) < 7:
            return None, f"Excel file {excel_path} has fewer than 7 rows (malformed)."
        return rows, None
    except Exception as e:
        return None, f"Failed to load Excel file {excel_path}: {e}"


def _get_c08_gujarat_rows() -> Tuple[Optional[List[tuple]], Optional[str]]:
    global _C08_GUJARAT_ROWS
    if _C08_GUJARAT_ROWS is not None:
        return _C08_GUJARAT_ROWS, None
    rows, err = _load_excel_rows(C08_GUJARAT_DEFAULT)
    if err:
        return None, err
    _C08_GUJARAT_ROWS = rows
    return _C08_GUJARAT_ROWS, None


def _get_c08a_gujarat_rows() -> Tuple[Optional[List[tuple]], Optional[str]]:
    global _C08A_GUJARAT_ROWS
    if _C08A_GUJARAT_ROWS is not None:
        return _C08A_GUJARAT_ROWS, None
    rows, err = _load_excel_rows(C08A_GUJARAT_DEFAULT)
    if err:
        return None, err
    _C08A_GUJARAT_ROWS = rows
    return _C08A_GUJARAT_ROWS, None


def _get_c08_india_rows() -> Tuple[Optional[List[tuple]], Optional[str]]:
    global _C08_INDIA_ROWS
    if _C08_INDIA_ROWS is not None:
        return _C08_INDIA_ROWS, None
    rows, err = _load_excel_rows(C08_INDIA_DEFAULT)
    if err:
        return None, err
    _C08_INDIA_ROWS = rows
    return _C08_INDIA_ROWS, None


def _get_c08a_india_rows() -> Tuple[Optional[List[tuple]], Optional[str]]:
    global _C08A_INDIA_ROWS
    if _C08A_INDIA_ROWS is not None:
        return _C08A_INDIA_ROWS, None
    rows, err = _load_excel_rows(C08A_INDIA_DEFAULT)
    if err:
        return None, err
    _C08A_INDIA_ROWS = rows
    return _C08A_INDIA_ROWS, None


def _build_district_index() -> Tuple[Optional[Dict[str, Dict[str, Any]]], Optional[str]]:
    global _DISTRICT_INDEX
    if _DISTRICT_INDEX is not None:
        return _DISTRICT_INDEX, None
    df, err = _load_pca_df()
    if err or df is None:
        return None, err

    idx: Dict[str, Dict[str, Any]] = {}
    for _, row in df.iterrows():
        try:
            d_name = str(row["Name"]).strip()
            s_code = int(row["State"])
            d_code = int(row["District"])
            entry = {
                "district_name": d_name,
                "district_code": d_code,
                "state_code": s_code,
                "state_name": STATE_CODE_TO_NAME.get(s_code, f"State-{s_code}"),
            }
            clean_name = re.sub(r"[^a-zA-Z0-9\s]", "", d_name).lower().strip()
            idx[clean_name] = entry
            idx[d_name.lower()] = entry
        except Exception:
            continue
    _DISTRICT_INDEX = idx
    return _DISTRICT_INDEX, None


def _safe_int(val: Any) -> int:
    try:
        if val is None or val == "":
            return 0
        return int(float(val))
    except Exception:
        return 0


# ------------------------------------------------------------------
# Geography Resolver
# ------------------------------------------------------------------
def resolve_geography(
    location: str = "",
    state: str = "",
    district: str = "",
    tru: str = ""
) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """
    Deterministically resolves a query to canonical State, District, TRU, and Level.
    Returns (geo_dict, error_string).
    """
    raw_query = f"{location} {district} {state}".strip()
    if not raw_query:
        raw_query = "India"

    # 1. Detect TRU (Rural / Urban / Total)
    detected_tru = "Total"
    if tru:
        t_clean = tru.strip().capitalize()
        if t_clean in ("Rural", "Urban", "Total"):
            detected_tru = t_clean
    else:
        q_lower = raw_query.lower()
        if "rural" in q_lower:
            detected_tru = "Rural"
        elif "urban" in q_lower:
            detected_tru = "Urban"

    clean_query = re.sub(r"\b(rural|urban|total)\b", "", raw_query, flags=re.IGNORECASE)
    clean_query = re.sub(r"[,\(\)\-]", " ", clean_query).strip()
    clean_query_lower = clean_query.lower()

    # Check for National level
    if clean_query_lower in ("", "india", "pan india", "all india", "national", "not specified"):
        return {
            "level": "national",
            "state_name": "India",
            "state_code": 0,
            "district_name": None,
            "district_code": None,
            "tru": detected_tru,
            "requested_location": location or "India",
        }, None

    d_index, err = _build_district_index()
    if err:
        return None, err

    matched_district_info = None

    # Check direct district argument
    if district and district.strip().lower() not in ("not specified", "none", ""):
        dist_clean = re.sub(r"[^a-zA-Z0-9\s]", "", district).lower().strip()
        dist_clean = DISTRICT_ALIASES.get(dist_clean, dist_clean)
        if dist_clean in d_index:
            matched_district_info = d_index[dist_clean]
        else:
            return None, f"District '{district}' not recognized in Census 2011 dataset."

    # Check district alias in text
    if not matched_district_info:
        for alias_k, alias_v in DISTRICT_ALIASES.items():
            pattern = r"\b" + re.escape(alias_k) + r"\b"
            if re.search(pattern, clean_query_lower):
                if alias_v in d_index:
                    matched_district_info = d_index[alias_v]
                    break

    # Check tokens against all 640 districts
    if not matched_district_info:
        words = clean_query_lower.split()
        candidates = [clean_query_lower]
        if len(words) >= 2:
            for i in range(len(words) - 1):
                candidates.append(f"{words[i]} {words[i+1]}")
        candidates.extend(words)

        for cand in candidates:
            cand_clean = re.sub(r"[^a-zA-Z0-9\s]", "", cand).strip()
            cand_clean = DISTRICT_ALIASES.get(cand_clean, cand_clean)
            if cand_clean in d_index:
                matched_district_info = d_index[cand_clean]
                break

    if matched_district_info:
        return {
            "level": "district",
            "state_name": matched_district_info["state_name"],
            "state_code": matched_district_info["state_code"],
            "district_name": matched_district_info["district_name"],
            "district_code": matched_district_info["district_code"],
            "tru": detected_tru,
            "requested_location": location or matched_district_info["district_name"],
        }, None

    # Check State
    target_state_code = None
    target_state_name = None

    if state and state.strip().lower() not in ("not specified", "none", ""):
        s_clean = state.strip().lower()
        if s_clean in STATE_NAME_TO_CODE:
            target_state_code = STATE_NAME_TO_CODE[s_clean]
            target_state_name = STATE_CODE_TO_NAME[target_state_code]
        else:
            return None, f"State '{state}' not recognized in Census 2011 dataset."

    if target_state_code is None:
        for s_name, s_code in STATE_NAME_TO_CODE.items():
            pattern = r"\b" + re.escape(s_name) + r"\b"
            if re.search(pattern, clean_query_lower):
                target_state_code = s_code
                target_state_name = STATE_CODE_TO_NAME[s_code]
                break

    if target_state_code is not None:
        return {
            "level": "state",
            "state_name": target_state_name,
            "state_code": target_state_code,
            "district_name": None,
            "district_code": None,
            "tru": detected_tru,
            "requested_location": location or target_state_name,
        }, None

    return None, f"Location '{location or raw_query}' not recognized in Census 2011 dataset."


# ------------------------------------------------------------------
# Table Extractors
# ------------------------------------------------------------------
def _extract_pca_evidence(geo: Dict[str, Any], pca_df: pd.DataFrame) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    level = geo["level"]
    if level == "district":
        s_code = geo["state_code"]
        d_code = geo["district_code"]
        sub = pca_df[(pca_df["State"] == s_code) & (pca_df["District"] == d_code)]
        if sub.empty:
            return None, f"District code {d_code} in state {s_code} not found in PCA dataset."
        row = sub.iloc[0]
        agg = {col: row[col] for col in pca_df.columns if col in row}
    elif level == "state":
        s_code = geo["state_code"]
        sub = pca_df[pca_df["State"] == s_code]
        if sub.empty:
            return None, f"State code {s_code} not found in PCA dataset."
        numeric_cols = [c for c in sub.columns if pd.api.types.is_numeric_dtype(sub[c])]
        agg = sub[numeric_cols].sum().to_dict()
    else:  # national
        numeric_cols = [c for c in pca_df.columns if pd.api.types.is_numeric_dtype(pca_df[c])]
        agg = pca_df[numeric_cols].sum().to_dict()

    try:
        tot_p = int(agg.get("TOT_P", 0))
        tot_m = int(agg.get("TOT_M", 0))
        tot_f = int(agg.get("TOT_F", 0))
        no_hh = int(agg.get("No_HH", 0))
        p_06 = int(agg.get("P_06", 0))
        m_06 = int(agg.get("M_06", 0))
        f_06 = int(agg.get("F_06", 0))
        p_sc = int(agg.get("P_SC", 0))
        p_st = int(agg.get("P_ST", 0))
        p_lit = int(agg.get("P_LIT", 0))
        m_lit = int(agg.get("M_LIT", 0))
        f_lit = int(agg.get("F_LIT", 0))
        p_ill = int(agg.get("P_ILL", 0))
        tot_work = int(agg.get("TOT_WORK_P", 0))
        main_work = int(agg.get("MAINWORK_P", 0))
        marg_work = int(agg.get("MARGWORK_P", 0))
        non_work = int(agg.get("NON_WORK_P", 0))

        cultivators = int(agg.get("MAIN_CL_P", 0)) + int(agg.get("MARG_CL_P", 0))
        agri_labourers = int(agg.get("MAIN_AL_P", 0)) + int(agg.get("MARG_AL_P", 0))
        hh_industry = int(agg.get("MAIN_HH_P", 0)) + int(agg.get("MARG_HH_P", 0))
        other_workers = int(agg.get("MAIN_OT_P", 0)) + int(agg.get("MARG_OT_P", 0))

        area_sq_km = float(agg.get("TRU1", 0.0))

        sex_ratio = round((tot_f / tot_m) * 1000, 1) if tot_m > 0 else 0.0
        lit_rate = round((p_lit / tot_p) * 100, 2) if tot_p > 0 else 0.0
        eff_lit_rate = round((p_lit / (tot_p - p_06)) * 100, 2) if (tot_p - p_06) > 0 else 0.0
        work_rate = round((tot_work / tot_p) * 100, 2) if tot_p > 0 else 0.0
        density = round(tot_p / area_sq_km, 1) if area_sq_km > 0 else None

        return {
            "status": "available",
            "source_table": "Primary Census Abstract (PCA 2011)",
            "geography_level": level,
            "rural_urban_context": "Total",
            "population": {
                "total": tot_p,
                "male": tot_m,
                "female": tot_f,
                "sex_ratio_females_per_1000_males": sex_ratio,
            },
            "households": no_hh,
            "child_population_0_6": {
                "total": p_06,
                "male": m_06,
                "female": f_06,
                "share_percent": round((p_06 / tot_p) * 100, 2) if tot_p > 0 else 0.0,
            },
            "social_groups": {
                "scheduled_castes": p_sc,
                "scheduled_tribes": p_st,
                "sc_st_share_percent": round(((p_sc + p_st) / tot_p) * 100, 2) if tot_p > 0 else 0.0,
            },
            "literacy": {
                "literate_total": p_lit,
                "literate_male": m_lit,
                "literate_female": f_lit,
                "illiterate_total": p_ill,
                "crude_literacy_rate_percent": lit_rate,
                "effective_literacy_rate_percent": eff_lit_rate,
            },
            "workers": {
                "total_workers": tot_work,
                "main_workers": main_work,
                "marginal_workers": marg_work,
                "non_workers": non_work,
                "work_participation_rate_percent": work_rate,
                "categories": {
                    "cultivators": {"count": cultivators, "share_of_workers_percent": round((cultivators / tot_work) * 100, 2) if tot_work > 0 else 0.0},
                    "agricultural_labourers": {"count": agri_labourers, "share_of_workers_percent": round((agri_labourers / tot_work) * 100, 2) if tot_work > 0 else 0.0},
                    "household_industry": {"count": hh_industry, "share_of_workers_percent": round((hh_industry / tot_work) * 100, 2) if tot_work > 0 else 0.0},
                    "other_workers": {"count": other_workers, "share_of_workers_percent": round((other_workers / tot_work) * 100, 2) if tot_work > 0 else 0.0},
                }
            },
            "area_sq_km": area_sq_km,
            "population_density_per_sq_km": density,
        }, None
    except Exception as e:
        return None, f"Error calculating PCA metrics: {e}"


def _extract_c08_evidence(geo: Dict[str, Any]) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    level = geo["level"]
    s_code = geo["state_code"]
    d_code = geo["district_code"]
    requested_tru = geo["tru"]

    rows = None
    table_geo_level = level
    fallback = False

    if level == "district" and s_code == 24:
        rows, err = _get_c08_gujarat_rows()
        target_s = "24"
        target_d = str(d_code)
    else:
        rows, err = _get_c08_india_rows()
        if level == "district":
            fallback = True
            table_geo_level = "state"
        target_s = str(s_code).zfill(2)
        target_d = "000"

    if rows is None:
        return None, f"C-08 dataset unavailable: {err}"

    area_rows = []
    for r in rows[7:]:
        if len(r) > 5 and str(r[1]).zfill(2) == target_s and str(r[2]).zfill(3) == target_d.zfill(3):
            area_rows.append(r)

    if not area_rows:
        return None, f"No C-08 rows found for State {target_s}, District {target_d}."

    tru_rows = [r for r in area_rows if str(r[4]).strip().lower() == requested_tru.lower()]
    actual_tru = requested_tru
    if not tru_rows:
        tru_rows = [r for r in area_rows if str(r[4]).strip().lower() == "total"]
        actual_tru = "Total"

    if not tru_rows:
        return None, f"No C-08 records matching TRU {requested_tru} or Total."

    all_ages_row = None
    for r in tru_rows:
        if str(r[5]).strip().lower() == "all ages":
            all_ages_row = r
            break
    if not all_ages_row:
        all_ages_row = tru_rows[0]

    tot_p = _safe_int(all_ages_row[6])
    tot_m = _safe_int(all_ages_row[7])
    tot_f = _safe_int(all_ages_row[8])
    ill_p = _safe_int(all_ages_row[9])
    ill_m = _safe_int(all_ages_row[10])
    ill_f = _safe_int(all_ages_row[11])
    lit_p = _safe_int(all_ages_row[12])
    lit_m = _safe_int(all_ages_row[13])
    lit_f = _safe_int(all_ages_row[14])

    levels = {
        "literate_without_educational_level": {"persons": _safe_int(all_ages_row[15]), "males": _safe_int(all_ages_row[16]), "females": _safe_int(all_ages_row[17])},
        "below_primary": {"persons": _safe_int(all_ages_row[18]), "males": _safe_int(all_ages_row[19]), "females": _safe_int(all_ages_row[20])},
        "primary": {"persons": _safe_int(all_ages_row[21]), "males": _safe_int(all_ages_row[22]), "females": _safe_int(all_ages_row[23])},
        "middle": {"persons": _safe_int(all_ages_row[24]), "males": _safe_int(all_ages_row[25]), "females": _safe_int(all_ages_row[26])},
        "matric_secondary": {"persons": _safe_int(all_ages_row[27]), "males": _safe_int(all_ages_row[28]), "females": _safe_int(all_ages_row[29])},
        "higher_secondary_intermediate": {"persons": _safe_int(all_ages_row[30]), "males": _safe_int(all_ages_row[31]), "females": _safe_int(all_ages_row[32])},
        "non_technical_diploma": {"persons": _safe_int(all_ages_row[33]), "males": _safe_int(all_ages_row[34]), "females": _safe_int(all_ages_row[35])},
        "technical_diploma": {"persons": _safe_int(all_ages_row[36]), "males": _safe_int(all_ages_row[37]), "females": _safe_int(all_ages_row[38])},
        "graduate_and_above": {"persons": _safe_int(all_ages_row[39]), "males": _safe_int(all_ages_row[40]), "females": _safe_int(all_ages_row[41])},
    }

    broad_brackets = {
        "0-6": [0, 0, 0, 0],
        "7-14": [0, 0, 0, 0],
        "15-19": [0, 0, 0, 0],
        "20-24": [0, 0, 0, 0],
        "25-29": [0, 0, 0, 0],
        "30-34": [0, 0, 0, 0],
        "35-59": [0, 0, 0, 0],
        "60+": [0, 0, 0, 0],
        "Age not stated": [0, 0, 0, 0],
    }

    for r in tru_rows:
        age_label = str(r[5]).strip()
        p = _safe_int(r[6])
        m = _safe_int(r[7])
        f = _safe_int(r[8])
        l = _safe_int(r[12])

        if age_label == "0-6":
            broad_brackets["0-6"] = [p, m, f, l]
        elif age_label.isdigit() and 7 <= int(age_label) <= 14:
            for i, val in enumerate([p, m, f, l]):
                broad_brackets["7-14"][i] += val
        elif age_label in ("15", "16", "17", "18", "19"):
            for i, val in enumerate([p, m, f, l]):
                broad_brackets["15-19"][i] += val
        elif age_label == "20-24":
            broad_brackets["20-24"] = [p, m, f, l]
        elif age_label == "25-29":
            broad_brackets["25-29"] = [p, m, f, l]
        elif age_label == "30-34":
            broad_brackets["30-34"] = [p, m, f, l]
        elif age_label in ("35-39", "40-44", "45-49", "50-54", "55-59"):
            for i, val in enumerate([p, m, f, l]):
                broad_brackets["35-59"][i] += val
        elif age_label in ("60-64", "65-69", "70-74", "75-79", "80+"):
            for i, val in enumerate([p, m, f, l]):
                broad_brackets["60+"][i] += val
        elif age_label.lower() == "age not stated":
            broad_brackets["Age not stated"] = [p, m, f, l]

    age_breakdown = [
        {"age_group": k, "persons": v[0], "males": v[1], "females": v[2], "literates": v[3]}
        for k, v in broad_brackets.items()
    ]

    sec_and_above = (
        levels["matric_secondary"]["persons"] +
        levels["higher_secondary_intermediate"]["persons"] +
        levels["non_technical_diploma"]["persons"] +
        levels["technical_diploma"]["persons"] +
        levels["graduate_and_above"]["persons"]
    )

    return {
        "status": "available",
        "source_table": "Table C-08 (Educational Level by Age and Sex)",
        "geography_level": table_geo_level,
        "is_state_fallback": fallback,
        "tru": actual_tru,
        "summary": {
            "total_persons": tot_p,
            "total_males": tot_m,
            "total_females": tot_f,
            "illiterates": {"persons": ill_p, "males": ill_m, "females": ill_f},
            "literates": {"persons": lit_p, "males": lit_m, "females": lit_f},
            "levels": levels,
            "metrics": {
                "literacy_rate_percent": round((lit_p / tot_p) * 100, 2) if tot_p > 0 else 0.0,
                "graduate_share_percent": round((levels["graduate_and_above"]["persons"] / tot_p) * 100, 2) if tot_p > 0 else 0.0,
                "secondary_and_above_share_percent": round((sec_and_above / tot_p) * 100, 2) if tot_p > 0 else 0.0,
            }
        },
        "age_distribution": age_breakdown,
    }, None


def _extract_c08a_evidence(geo: Dict[str, Any]) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    level = geo["level"]
    s_code = geo["state_code"]
    d_code = geo["district_code"]
    requested_tru = geo["tru"]

    rows = None
    table_geo_level = level
    fallback = False

    if level == "district" and s_code == 24:
        rows, err = _get_c08a_gujarat_rows()
        target_s = "24"
        target_d = str(d_code)
    else:
        rows, err = _get_c08a_india_rows()
        if level == "district":
            fallback = True
            table_geo_level = "state"
        target_s = str(s_code).zfill(2)
        target_d = "000"

    if rows is None:
        return None, f"C-08A dataset unavailable: {err}"

    area_rows = []
    for r in rows[7:]:
        if len(r) > 5 and str(r[1]).zfill(2) == target_s and str(r[2]).zfill(3) == target_d.zfill(3):
            area_rows.append(r)

    if not area_rows:
        return None, f"No C-08A rows found for State {target_s}, District {target_d}."

    tru_rows = [r for r in area_rows if str(r[4]).strip().lower() == requested_tru.lower()]
    actual_tru = requested_tru
    if not tru_rows:
        tru_rows = [r for r in area_rows if str(r[4]).strip().lower() == "total"]
        actual_tru = "Total"

    if not tru_rows:
        return None, f"No C-08A records matching TRU {requested_tru} or Total."

    total_row = None
    for r in tru_rows:
        if str(r[5]).strip().lower() == "total":
            total_row = r
            break
    if not total_row:
        total_row = tru_rows[0]

    tot_pop_15plus = _safe_int(total_row[6])
    tot_grad = _safe_int(total_row[9])
    tot_grad_m = _safe_int(total_row[10])
    tot_grad_f = _safe_int(total_row[11])

    disciplines = {
        "non_technical_graduate": {"persons": _safe_int(total_row[12]), "males": _safe_int(total_row[13]), "females": _safe_int(total_row[14])},
        "non_technical_post_graduate": {"persons": _safe_int(total_row[15]), "males": _safe_int(total_row[16]), "females": _safe_int(total_row[17])},
        "engineering_and_technology": {"persons": _safe_int(total_row[18]), "males": _safe_int(total_row[19]), "females": _safe_int(total_row[20])},
        "medicine": {"persons": _safe_int(total_row[21]), "males": _safe_int(total_row[22]), "females": _safe_int(total_row[23])},
        "agriculture_and_dairying": {"persons": _safe_int(total_row[24]), "males": _safe_int(total_row[25]), "females": _safe_int(total_row[26])},
        "veterinary": {"persons": _safe_int(total_row[27]), "males": _safe_int(total_row[28]), "females": _safe_int(total_row[29])},
        "teaching": {"persons": _safe_int(total_row[30]), "males": _safe_int(total_row[31]), "females": _safe_int(total_row[32])},
        "other_fields": {"persons": _safe_int(total_row[33]), "males": _safe_int(total_row[34]), "females": _safe_int(total_row[35])},
    }

    age_breakdown = []
    for r in tru_rows:
        grp = str(r[5]).strip()
        if grp.lower() == "total":
            continue
        age_breakdown.append({
            "age_group": grp,
            "total_graduates": _safe_int(r[9]),
            "engineering_and_technology": _safe_int(r[18]),
            "medicine": _safe_int(r[21]),
            "teaching": _safe_int(r[30]),
            "non_technical_graduate": _safe_int(r[12]),
        })

    eng_p = disciplines["engineering_and_technology"]["persons"]
    med_p = disciplines["medicine"]["persons"]
    teach_p = disciplines["teaching"]["persons"]
    agri_p = disciplines["agriculture_and_dairying"]["persons"]

    return {
        "status": "available",
        "source_table": "Table C-08 Appendix (Graduate and Above Educational Level)",
        "geography_level": table_geo_level,
        "is_state_fallback": fallback,
        "tru": actual_tru,
        "summary": {
            "population_15_plus": tot_pop_15plus,
            "total_graduates_and_above": {"persons": tot_grad, "males": tot_grad_m, "females": tot_grad_f},
            "disciplines": disciplines,
            "metrics": {
                "engineering_share_of_graduates_percent": round((eng_p / tot_grad) * 100, 2) if tot_grad > 0 else 0.0,
                "medicine_share_of_graduates_percent": round((med_p / tot_grad) * 100, 2) if tot_grad > 0 else 0.0,
                "teaching_share_of_graduates_percent": round((teach_p / tot_grad) * 100, 2) if tot_grad > 0 else 0.0,
                "agriculture_share_of_graduates_percent": round((agri_p / tot_grad) * 100, 2) if tot_grad > 0 else 0.0,
            }
        },
        "age_distribution": age_breakdown,
    }, None


# ------------------------------------------------------------------
# Primary Tool Function
# ------------------------------------------------------------------
@tool
def run_census_search(
    location: str = "",
    state: str = "",
    district: str = "",
    tru: str = ""
) -> Dict[str, Any]:
    """
    Search official local Census 2011 datasets for demographics, education, and workforce statistics.

    Args:
        location: Full location string, e.g. "Ahmedabad", "Gujarat", "Rural Gujarat", "Pune"
        state: Optional explicit state name
        district: Optional explicit district name
        tru: Optional residence context: 'Total', 'Rural', or 'Urban'

    Returns:
        Structured evidence dictionary with PCA, C-08, and C-08A indicators.
    """
    geo, err = resolve_geography(location=location, state=state, district=district, tru=tru)
    if err or geo is None:
        return {
            "status": "error",
            "source": "Census 2011",
            "source_type": "official_government_dataset",
            "error": err or "Failed to resolve geography.",
        }

    pca_df, pca_err = _load_pca_df()
    if pca_err or pca_df is None:
        return {
            "status": "error",
            "source": "Census 2011",
            "source_type": "official_government_dataset",
            "error": f"Census PCA dataset missing or malformed: {pca_err}",
        }

    pca_res, pca_err = _extract_pca_evidence(geo, pca_df)
    if pca_err:
        return {
            "status": "error",
            "source": "Census 2011",
            "source_type": "official_government_dataset",
            "error": f"PCA extraction error: {pca_err}",
        }

    c08_res, c08_err = _extract_c08_evidence(geo)
    c08a_res, c08a_err = _extract_c08a_evidence(geo)

    evidence = {
        "status": "success",
        "source": "Census 2011",
        "source_type": "official_government_dataset",
        "geography": {
            "state": geo["state_name"],
            "district": geo["district_name"],
            "level": geo["level"],
            "tru": geo["tru"],
            "requested_location": geo["requested_location"],
        },
        "metadata": {
            "census_year": 2011,
            "datasets_consulted": [
                "Primary Census Abstract (PCA)",
                "DDW-0000C-08 / DDW-2400C-08 (Age x Education)",
                "DDW-0000C-08A / DDW-2400C-08A (Higher Education)",
            ]
        },
        "pca": pca_res,
        "education": c08_res if not c08_err else {"status": "error", "error": c08_err},
        "higher_education": c08a_res if not c08a_err else {"status": "error", "error": c08a_err},
    }
    return evidence
