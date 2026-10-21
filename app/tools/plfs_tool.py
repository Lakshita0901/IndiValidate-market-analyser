"""
plfs_tool.py
------------
Retrieves aggregate labour force, employment, education, earnings, and industry
evidence directly from the official Periodic Labour Force Survey (PLFS) 2025 microdata:

1. Central Person File (data/plfs_2025/cperv12025.csv):
   - Labour Force Participation Rate (LFPR) - Usual Status (ps+ss) & Principal Status (ps)
   - Worker Population Ratio (WPR) - Usual Status & Principal Status
   - Unemployment Rate (UR) - Usual Status & Principal Status
   - General Educational Attainment distribution (gedu_lvl)
   - Employment Type distribution (Self-employed, Regular Salaried, Casual Wage)
   - Average Monthly Regular Salary earnings (ern_reg)
   - Average Monthly Self-Employed Gross Earnings / Net Profit (ern_self, including business losses)
   - Occupation distribution (NCO-2015 1-digit & 3-digit)
   - Industry distribution (NIC-2008 2-digit divisions)

2. Central Household File (data/plfs_2025/chhv12025.csv):
   - Average Household Size (hh_size)
   - Average Monthly Household Consumer Expenditure (hce_tot)
   - Household Type & Income context (inc_tot)

Survey Methodology:
- Year: 2025 (All 4 Quarters: Q1-Q4, January - December 2025)
- Round: Visit 1 Cross-Sectional Sample
- Weighting: All rates, distributions, and averages are computed using sampling multiplier weights ('mult')
- Population Estimates: Estimated using official MoSPI weight scaling (mult / 100)
- Working Age Standard: Age 15 and above (headline international & MoSPI benchmark)
"""

import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union
import pandas as pd
from langchain_core.tools import tool

# ------------------------------------------------------------------
# File Paths and Directory Architecture
# ------------------------------------------------------------------
PLFS_DATA_DIR = Path("data/plfs_2025")
PLFS_CPER_CSV = PLFS_DATA_DIR / "cperv12025.csv"
PLFS_CHH_CSV = PLFS_DATA_DIR / "chhv12025.csv"
PLFS_CACHE_DIR = PLFS_DATA_DIR / "cache"

# Required columns for person-level analysis to minimize memory
CPER_COLS = [
    "st", "dc", "sec", "sex", "age", "gedu_lvl",
    "pas", "sas", "ind_pas", "ocu_pas", "ern_reg", "ern_self", "mult"
]

CHH_COLS = [
    "sec", "st", "dc", "hh_size", "hhtype", "relg", "sg", "hce_tot", "inc_tot", "mult"
]

# ------------------------------------------------------------------
# Geographic Knowledge Base (Census / MoSPI Official Codes)
# ------------------------------------------------------------------
STATE_CODE_TO_NAME = {
    1: "Jammu & Kashmir", 2: "Himachal Pradesh", 3: "Punjab", 4: "Chandigarh",
    5: "Uttarakhand", 6: "Haryana", 7: "Delhi", 8: "Rajasthan",
    9: "Uttar Pradesh", 10: "Bihar", 11: "Sikkim", 12: "Arunachal Pradesh",
    13: "Nagaland", 14: "Manipur", 15: "Mizoram", 16: "Tripura",
    17: "Meghalaya", 18: "Assam", 19: "West Bengal", 20: "Jharkhand",
    21: "Odisha", 22: "Chhattisgarh", 23: "Madhya Pradesh", 24: "Gujarat",
    25: "Dadra & Nagar Haveli and Daman & Diu", 27: "Maharashtra",
    28: "Andhra Pradesh", 29: "Karnataka", 30: "Goa", 31: "Lakshadweep",
    32: "Kerala", 33: "Tamil Nadu", 34: "Puducherry", 35: "Andaman & Nicobar Islands",
    36: "Telangana", 37: "Ladakh"
}

STATE_NAME_TO_CODE = {name.lower(): code for code, name in STATE_CODE_TO_NAME.items()}
STATE_NAME_TO_CODE.update({
    "nct of delhi": 7,
    "new delhi": 7,
    "orissa": 21,
    "pondicherry": 34,
    "uttaranchal": 5,
    "jammu and kashmir": 1,
    "andaman and nicobar": 35,
    "andaman and nicobar islands": 35,
    "dadra and nagar haveli": 25,
    "daman and diu": 25,
})

# District mapping for key states in PLFS
# st -> {district_clean_name: dc_code}
DISTRICT_CODE_MAP = {
    24: {  # Gujarat
        "kachchh": 1, "kutch": 1,
        "banas kantha": 2, "banaskantha": 2,
        "patan": 3,
        "mahesana": 4, "mehsana": 4,
        "sabar kantha": 5, "sabarkantha": 5,
        "gandhinagar": 6,
        "ahmadabad": 7, "ahmedabad": 7,
        "surendranagar": 8,
        "rajkot": 9,
        "jamnagar": 10,
        "porbandar": 11,
        "junagadh": 12,
        "amreli": 13,
        "bhavnagar": 14,
        "anand": 15,
        "kheda": 16,
        "panch mahals": 17, "panchmahal": 17, "panchmahals": 17,
        "dohad": 18, "dahod": 18,
        "vadodara": 19, "baroda": 19,
        "narmada": 20,
        "bharuch": 21,
        "the dangs": 22, "dangs": 22, "dang": 22,
        "navsari": 23,
        "valsad": 24,
        "surat": 25,
        "tapi": 26,
        "aravalli": 27,
        "botad": 28,
        "chhota udepur": 29, "chhotaudepur": 29,
        "devbhumi dwarka": 30, "dwarka": 30,
        "gir somnath": 31, "somnath": 31,
        "mahisagar": 32,
        "morbi": 33,
    },
    27: {  # Maharashtra
        "thane": 21, "mumbai": 22, "mumbai suburban": 23,
        "pune": 25, "nagpur": 9, "nashik": 20, "aurangabad": 19
    },
    29: {  # Karnataka
        "bangalore": 18, "bengaluru": 18, "bangalore rural": 19, "mysore": 22, "mysuru": 22
    }
}

# General Education Level Labels (gedu_lvl)
EDU_LEVEL_NAMES = {
    1: "Not literate",
    2: "Literate without formal schooling: EGS/NFEC/AEC",
    3: "Literate through TLC/JSN",
    4: "Literate without schooling (Others)",
    5: "Below primary",
    6: "Primary",
    7: "Middle",
    8: "Secondary (Matric)",
    10: "Higher secondary",
    11: "Diploma/Certificate course",
    12: "Graduate",
    13: "Postgraduate and above"
}

# 1-digit NCO-2015 Occupation Major Groups
NCO_1DIGIT_NAMES = {
    1: "Managers",
    2: "Professionals",
    3: "Technicians & Associate Professionals",
    4: "Clerical Support Workers",
    5: "Service & Sales Workers",
    6: "Skilled Agricultural, Forestry & Fishery Workers",
    7: "Craft & Related Trades Workers",
    8: "Plant & Machine Operators & Assemblers",
    9: "Elementary Occupations"
}

# Top 2-digit NIC-2008 Industry Division Names
NIC_2DIGIT_NAMES = {
    1: "Crop and animal production (Agriculture)",
    2: "Forestry and logging",
    3: "Fishing and aquaculture",
    10: "Manufacture of food products",
    11: "Manufacture of beverages",
    13: "Manufacture of textiles",
    14: "Manufacture of wearing apparel",
    15: "Manufacture of leather and related products",
    16: "Manufacture of wood products",
    17: "Manufacture of paper and paper products",
    20: "Manufacture of chemicals and chemical products",
    21: "Manufacture of pharmaceuticals",
    22: "Manufacture of rubber and plastics",
    23: "Manufacture of other non-metallic mineral products",
    24: "Manufacture of basic metals",
    25: "Manufacture of fabricated metal products",
    26: "Manufacture of computer, electronic & optical products",
    27: "Manufacture of electrical equipment",
    28: "Manufacture of machinery and equipment",
    29: "Manufacture of motor vehicles, trailers",
    31: "Manufacture of furniture",
    41: "Construction of buildings",
    42: "Civil engineering",
    43: "Specialised construction activities",
    45: "Wholesale & retail trade of motor vehicles",
    46: "Wholesale trade, except motor vehicles",
    47: "Retail trade, except motor vehicles",
    49: "Land transport and transport via pipelines",
    52: "Warehousing and support activities for transportation",
    53: "Postal and courier activities",
    55: "Accommodation (Hotels & Lodging)",
    56: "Food and beverage service activities (Restaurants)",
    58: "Publishing activities",
    61: "Telecommunications",
    62: "Computer programming, consultancy & IT services",
    64: "Financial service activities (Banking)",
    65: "Insurance and pension funding",
    68: "Real estate activities",
    69: "Legal and accounting activities",
    70: "Activities of head offices; management consultancy",
    71: "Architecture and engineering activities",
    72: "Scientific research and development",
    73: "Advertising and market research",
    74: "Other professional, scientific and technical activities",
    77: "Rental and leasing activities",
    78: "Employment activities",
    79: "Travel agency and tour operator activities",
    80: "Security and investigation activities",
    81: "Services to buildings and landscape activities",
    82: "Office administrative and support activities",
    84: "Public administration and defence",
    85: "Education",
    86: "Human health activities",
    87: "Residential care activities",
    88: "Social work activities without accommodation",
    90: "Creative, arts and entertainment activities",
    93: "Sports activities and amusement/recreation",
    94: "Activities of membership organizations",
    95: "Repair of computers and personal goods",
    96: "Other personal service activities",
    97: "Activities of households as employers of domestic personnel"
}

# In-memory session cache for loaded state slices
_MEM_STATE_CACHE: Dict[int, pd.DataFrame] = {}
_MEM_CHH_CACHE: Dict[int, pd.DataFrame] = {}


def clear_plfs_cache():
    """Clear memory caches (useful for testing)."""
    global _MEM_STATE_CACHE, _MEM_CHH_CACHE
    _MEM_STATE_CACHE.clear()
    _MEM_CHH_CACHE.clear()


# ------------------------------------------------------------------
# Data Loading & Partition Cache Engine
# ------------------------------------------------------------------
def _get_state_data(st: int) -> Tuple[Optional[pd.DataFrame], Optional[pd.DataFrame], Optional[str]]:
    """
    Load person and household data for a specific state code.
    Checks memory cache -> on-disk parquet partition -> falls back to reading CSVs.
    Returns (cper_df, chh_df, error_string).
    """
    global _MEM_STATE_CACHE, _MEM_CHH_CACHE

    if st in _MEM_STATE_CACHE and st in _MEM_CHH_CACHE:
        return _MEM_STATE_CACHE[st], _MEM_CHH_CACHE[st], None

    PLFS_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cper_parquet = PLFS_CACHE_DIR / f"st_{st}.parquet"
    chh_parquet = PLFS_CACHE_DIR / f"chh_st_{st}.parquet"

    # If parquet partitions exist, load directly
    if cper_parquet.exists() and chh_parquet.exists():
        try:
            df_cper = pd.read_parquet(cper_parquet)
            df_chh = pd.read_parquet(chh_parquet)
            _MEM_STATE_CACHE[st] = df_cper
            _MEM_CHH_CACHE[st] = df_chh
            return df_cper, df_chh, None
        except Exception:
            pass

    # Fallback to source CSVs if parquet cache is missing
    if not PLFS_CPER_CSV.exists():
        return None, None, f"PLFS 2025 person dataset not found at {PLFS_CPER_CSV.absolute()}."
    if not PLFS_CHH_CSV.exists():
        return None, None, f"PLFS 2025 household dataset not found at {PLFS_CHH_CSV.absolute()}."

    try:
        # Read filtered by state code
        df_cper = pd.read_csv(PLFS_CPER_CSV, usecols=CPER_COLS)
        df_cper = df_cper[df_cper["st"] == st]
        if df_cper.empty:
            return None, None, f"State code {st} not found in PLFS person dataset."

        df_chh = pd.read_csv(PLFS_CHH_CSV, usecols=CHH_COLS)
        df_chh = df_chh[df_chh["st"] == st]

        # Cache to disk for instant subsequent loads
        try:
            df_cper.to_parquet(cper_parquet)
            df_chh.to_parquet(chh_parquet)
        except Exception:
            pass

        _MEM_STATE_CACHE[st] = df_cper
        _MEM_CHH_CACHE[st] = df_chh
        return df_cper, df_chh, None

    except Exception as e:
        return None, None, f"Error reading PLFS datasets for state {st}: {e}"


# ------------------------------------------------------------------
# Geography Resolver
# ------------------------------------------------------------------
def resolve_plfs_geography(
    location: str = "",
    state: str = "",
    district: str = "",
    tru: str = ""
) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """
    Resolves input location query to canonical state name, state code (st),
    district code (dc), sector filter (sec), and geographic level.
    """
    raw_query = f"{location} {district} {state}".strip()
    if not raw_query:
        raw_query = "India"

    # 1. Sector (Rural / Urban / Total)
    sec_filter = None  # None means Total
    sec_label = "Total"
    if tru:
        t_clean = tru.strip().capitalize()
        if t_clean == "Rural":
            sec_filter = 1
            sec_label = "Rural"
        elif t_clean == "Urban":
            sec_filter = 2
            sec_label = "Urban"
    else:
        q_lower = raw_query.lower()
        if "rural" in q_lower:
            sec_filter = 1
            sec_label = "Rural"
        elif "urban" in q_lower:
            sec_filter = 2
            sec_label = "Urban"

    clean_query = re.sub(r"\b(rural|urban|total)\b", "", raw_query, flags=re.IGNORECASE)
    clean_query = re.sub(r"[,\(\)\-]", " ", clean_query).strip()
    clean_query_lower = clean_query.lower()

    # All-India / National query
    if clean_query_lower in ("", "india", "pan india", "all india", "national", "not specified"):
        return {
            "level": "national",
            "state_name": "India",
            "st": 0,
            "district_name": None,
            "dc": None,
            "sec": sec_filter,
            "sector": sec_label,
            "requested_location": location or "India",
        }, None

    # Determine State
    target_st = None
    target_state_name = None

    if state and state.strip().lower() not in ("not specified", "none", ""):
        s_clean = state.strip().lower()
        if s_clean in STATE_NAME_TO_CODE:
            target_st = STATE_NAME_TO_CODE[s_clean]
            target_state_name = STATE_CODE_TO_NAME.get(target_st)
        else:
            return None, f"State '{state}' not recognized in PLFS 2025 dataset."

    if target_st is None:
        for s_name, s_code in STATE_NAME_TO_CODE.items():
            pattern = r"\b" + re.escape(s_name) + r"\b"
            if re.search(pattern, clean_query_lower):
                target_st = s_code
                target_state_name = STATE_CODE_TO_NAME.get(s_code)
                break

    # Check District
    target_dc = None
    target_district_name = None

    # Check direct district argument
    d_query = district.strip() if district else ""
    if not d_query:
        # Search tokens in query
        d_query = clean_query_lower

    # Try mapping district across states if state is known or unknown
    states_to_check = [target_st] if target_st else list(DISTRICT_CODE_MAP.keys())

    for check_st in states_to_check:
        if check_st in DISTRICT_CODE_MAP:
            d_map = DISTRICT_CODE_MAP[check_st]
            # Check direct match
            clean_d = re.sub(r"[^a-zA-Z0-9\s]", "", d_query).lower().strip()
            if clean_d in d_map:
                target_dc = d_map[clean_d]
                target_district_name = clean_d.capitalize()
                target_st = check_st
                target_state_name = STATE_CODE_TO_NAME.get(check_st)
                break
            # Check substring/tokens
            for d_alias, dc_val in d_map.items():
                pattern = r"\b" + re.escape(d_alias) + r"\b"
                if re.search(pattern, clean_query_lower):
                    target_dc = dc_val
                    target_district_name = d_alias.capitalize()
                    target_st = check_st
                    target_state_name = STATE_CODE_TO_NAME.get(check_st)
                    break
        if target_dc is not None:
            break

    # If district was explicitly given but not matched in mapped districts
    if district and district.strip().lower() not in ("not specified", "none", "") and target_dc is None:
        return None, f"District '{district}' not recognized in PLFS 2025 district coding."

    # Validate resolved geography
    if target_st is None:
        return None, f"Location '{location or raw_query}' not recognized in PLFS 2025 dataset."

    if target_dc is not None:
        return {
            "level": "district",
            "state_name": target_state_name,
            "st": target_st,
            "district_name": target_district_name,
            "dc": target_dc,
            "sec": sec_filter,
            "sector": sec_label,
            "requested_location": location or target_district_name,
        }, None

    return {
        "level": "state",
        "state_name": target_state_name,
        "st": target_st,
        "district_name": None,
        "dc": None,
        "sec": sec_filter,
        "sector": sec_label,
        "requested_location": location or target_state_name,
    }, None


# ------------------------------------------------------------------
# Calculation Modules (Using Official PLFS Formulas)
# ------------------------------------------------------------------
def _calculate_labour_indicators(df: pd.DataFrame) -> Dict[str, Any]:
    """
    Calculate LFPR, WPR, and Unemployment Rate for Age 15+ (headline benchmark)
    and All Ages using official MoSPI definitions:
      - Principal Status (ps)
      - Usual Status (ps+ss)
    """
    pop15 = df[df["age"] >= 15]
    if pop15.empty:
        return {"status": "error", "error": "Insufficient records for labour indicators."}

    w_pop = pop15["mult"].sum()

    # 1. Principal Status (ps)
    emp_ps = pop15["pas"].isin([11, 12, 21, 31, 41, 51])
    unemp_ps = pop15["pas"] == 81
    lf_ps = emp_ps | unemp_ps

    w_emp_ps = pop15.loc[emp_ps, "mult"].sum()
    w_unemp_ps = pop15.loc[unemp_ps, "mult"].sum()
    w_lf_ps = pop15.loc[lf_ps, "mult"].sum()

    lfpr_ps = round(float((w_lf_ps / w_pop) * 100), 2) if w_pop > 0 else 0.0
    wpr_ps = round(float((w_emp_ps / w_pop) * 100), 2) if w_pop > 0 else 0.0
    ur_ps = round(float((w_unemp_ps / w_lf_ps) * 100), 2) if w_lf_ps > 0 else 0.0

    # 2. Usual Status (ps+ss) (Official Primary Headline Standard)
    emp_ss = pop15["sas"].isin([11, 12, 21, 31, 41, 51])
    emp_us = emp_ps | emp_ss
    unemp_us = unemp_ps & (~emp_ss)
    lf_us = emp_us | unemp_us

    w_emp_us = pop15.loc[emp_us, "mult"].sum()
    w_unemp_us = pop15.loc[unemp_us, "mult"].sum()
    w_lf_us = pop15.loc[lf_us, "mult"].sum()

    lfpr_us = round(float((w_lf_us / w_pop) * 100), 2) if w_pop > 0 else 0.0
    wpr_us = round(float((w_emp_us / w_pop) * 100), 2) if w_pop > 0 else 0.0
    ur_us = round(float((w_unemp_us / w_lf_us) * 100), 2) if w_lf_us > 0 else 0.0

    return {
        "status": "available",
        "benchmark_population": "Age 15 and above (Working Age Population)",
        "usual_status_ps_plus_ss": {
            "definition": "Principal Status plus Subsidiary Economic Activity (ps+ss)",
            "lfpr_percent": lfpr_us,
            "wpr_percent": wpr_us,
            "unemployment_rate_percent": ur_us,
        },
        "principal_status_ps": {
            "definition": "Principal Activity Status only (Major time criterion 365 days)",
            "lfpr_percent": lfpr_ps,
            "wpr_percent": wpr_ps,
            "unemployment_rate_percent": ur_ps,
        }
    }


def _calculate_education_evidence(df: pd.DataFrame) -> Dict[str, Any]:
    """
    Calculate educational attainment distribution for Age 15+ using gedu_lvl.
    """
    pop15 = df[df["age"] >= 15]
    if pop15.empty:
        return {"status": "error", "error": "Insufficient records for education."}

    w_total = pop15["mult"].sum()

    edu_categories = {
        "not_literate": pop15["gedu_lvl"] == 1,
        "literate_below_primary": pop15["gedu_lvl"].isin([2, 3, 4, 5]),
        "primary": pop15["gedu_lvl"] == 6,
        "middle": pop15["gedu_lvl"] == 7,
        "secondary": pop15["gedu_lvl"] == 8,
        "higher_secondary": pop15["gedu_lvl"] == 10,
        "diploma_certificate": pop15["gedu_lvl"] == 11,
        "graduate": pop15["gedu_lvl"] == 12,
        "postgraduate_and_above": pop15["gedu_lvl"] == 13
    }

    breakdown = []
    shares = {}
    for cat_key, cond in edu_categories.items():
        sub = pop15[cond]
        w_sub = sub["mult"].sum()
        pct = round(float((w_sub / w_total) * 100), 2) if w_total > 0 else 0.0
        shares[cat_key] = pct
        breakdown.append({
            "category": cat_key.replace("_", " ").title(),
            "weighted_share_percent": pct,
            "sample_count": int(len(sub))
        })

    grad_and_above = round(float(shares.get("graduate", 0.0) + shares.get("postgraduate_and_above", 0.0)), 2)
    secondary_and_above = round(
        float(shares.get("secondary", 0.0) + shares.get("higher_secondary", 0.0) +
        shares.get("diploma_certificate", 0.0) + grad_and_above), 2
    )

    return {
        "status": "available",
        "benchmark_population": "Age 15 and above",
        "graduate_and_above_percent": grad_and_above,
        "secondary_and_above_percent": secondary_and_above,
        "not_literate_percent": shares.get("not_literate", 0.0),
        "categories": breakdown
    }


def _calculate_employment_distribution(df: pd.DataFrame) -> Dict[str, Any]:
    """
    Calculate detailed employment type breakdown from pas.
    """
    pop15 = df[df["age"] >= 15]
    if pop15.empty:
        return {"status": "error", "error": "Insufficient records for employment."}

    w_pop = pop15["mult"].sum()
    emp = pop15[pop15["pas"].isin([11, 12, 21, 31, 41, 51])]
    w_emp = emp["mult"].sum()

    self_emp = pop15[pop15["pas"].isin([11, 12, 21])]
    reg_sal = pop15[pop15["pas"] == 31]
    casual = pop15[pop15["pas"].isin([41, 51])]

    w_self = self_emp["mult"].sum()
    w_sal = reg_sal["mult"].sum()
    w_cas = casual["mult"].sum()

    return {
        "status": "available",
        "workforce_composition_percent": {
            "self_employed": round(float((w_self / w_emp) * 100), 2) if w_emp > 0 else 0.0,
            "regular_salaried": round(float((w_sal / w_emp) * 100), 2) if w_emp > 0 else 0.0,
            "casual_wage_labour": round(float((w_cas / w_emp) * 100), 2) if w_emp > 0 else 0.0,
        },
        "population_share_percent": {
            "self_employed": round(float((w_self / w_pop) * 100), 2) if w_pop > 0 else 0.0,
            "regular_salaried": round(float((w_sal / w_pop) * 100), 2) if w_pop > 0 else 0.0,
            "casual_wage_labour": round(float((w_cas / w_pop) * 100), 2) if w_pop > 0 else 0.0,
            "unemployed": round(float((pop15[pop15["pas"] == 81]["mult"].sum() / w_pop) * 100), 2) if w_pop > 0 else 0.0,
            "students": round(float((pop15[pop15["pas"] == 91]["mult"].sum() / w_pop) * 100), 2) if w_pop > 0 else 0.0,
            "domestic_duties": round(float((pop15[pop15["pas"].isin([92, 93])]["mult"].sum() / w_pop) * 100), 2) if w_pop > 0 else 0.0,
        }
    }


def _calculate_earnings(df: pd.DataFrame) -> Dict[str, Any]:
    """
    Calculate weighted average monthly earnings for regular salaried and self-employed.
    Negative self-employed earnings are preserved as business losses.
    """
    # 1. Regular Salaried (ern_reg > 0)
    sal = df[df["ern_reg"] > 0]
    if not sal.empty and sal["mult"].sum() > 0:
        sal_avg = round(float((sal["ern_reg"] * sal["mult"]).sum() / sal["mult"].sum()), 2)
        sal_med = float(sal["ern_reg"].median())
        sal_n = int(len(sal))
    else:
        sal_avg, sal_med, sal_n = 0.0, 0.0, 0

    # 2. Self-employed (ern_self != 0)
    se = df[df["ern_self"] != 0]
    if not se.empty and se["mult"].sum() > 0:
        se_avg = round(float((se["ern_self"] * se["mult"]).sum() / se["mult"].sum()), 2)
        se_med = float(se["ern_self"].median())
        se_n = int(len(se))
        se_losses = int((se["ern_self"] < 0).sum())
    else:
        se_avg, se_med, se_n, se_losses = 0.0, 0.0, 0, 0

    return {
        "status": "available",
        "regular_salaried": {
            "avg_monthly_salary_inr": sal_avg,
            "median_monthly_salary_inr": sal_med,
            "sample_size": sal_n,
            "unit": "INR per month (weighted average)"
        },
        "self_employed": {
            "avg_monthly_earnings_inr": se_avg,
            "median_monthly_earnings_inr": se_med,
            "sample_size": se_n,
            "reporting_net_loss_count": se_losses,
            "unit": "INR per month (weighted gross earnings/net profit)"
        }
    }


def _calculate_occupations(df: pd.DataFrame) -> List[Dict[str, Any]]:
    """
    Aggregate occupations using NCO-2015 1-digit major groups and top occupations.
    """
    employed = df[df["ocu_pas"].notna()].copy()
    if employed.empty or employed["mult"].sum() == 0:
        return []

    total_w = employed["mult"].sum()
    employed["nco_1digit"] = employed["ocu_pas"].astype(str).str.split('.').str[0].str[0].astype(int)

    results = []
    for nco_code, group in employed.groupby("nco_1digit"):
        w = group["mult"].sum()
        pct = round(float((w / total_w) * 100), 2)
        results.append({
            "nco_code": int(nco_code),
            "occupation_group": NCO_1DIGIT_NAMES.get(int(nco_code), f"NCO Group {nco_code}"),
            "weighted_share_percent": pct,
            "sample_count": int(len(group))
        })

    results.sort(key=lambda x: x["weighted_share_percent"], reverse=True)
    return results


def _calculate_industries(df: pd.DataFrame) -> List[Dict[str, Any]]:
    """
    Aggregate industries using NIC-2008 2-digit divisions.
    """
    employed = df[df["ind_pas"].notna()].copy()
    if employed.empty or employed["mult"].sum() == 0:
        return []

    total_w = employed["mult"].sum()
    employed["nic_2digit"] = employed["ind_pas"].astype(str).str.split('.').str[0].str.zfill(5).str[:2].astype(int)

    top_groups = employed.groupby("nic_2digit")["mult"].sum().sort_values(ascending=False).head(8)

    results = []
    for nic_code, w in top_groups.items():
        pct = round(float((w / total_w) * 100), 2)
        cnt = int(len(employed[employed["nic_2digit"] == nic_code]))
        results.append({
            "nic_code": int(nic_code),
            "industry_division": NIC_2DIGIT_NAMES.get(int(nic_code), f"NIC Division {nic_code}"),
            "weighted_share_percent": pct,
            "sample_count": cnt
        })

    return results


def _calculate_household_evidence(df_hh: Optional[pd.DataFrame], dc: Optional[int], sec: Optional[int]) -> Dict[str, Any]:
    """
    Extract household metrics from chhv12025.csv.
    """
    if df_hh is None or df_hh.empty:
        return {"status": "not_available"}

    sub = df_hh.copy()
    if dc is not None:
        sub = sub[sub["dc"] == dc]
    if sec is not None:
        sub = sub[sub["sec"] == sec]

    if sub.empty or sub["mult"].sum() == 0:
        return {"status": "insufficient_data"}

    w_hh = sub["mult"].sum()
    avg_size = round(float((sub["hh_size"] * sub["mult"]).sum() / w_hh), 2)

    hce_sub = sub[sub["hce_tot"] > 0]
    if not hce_sub.empty and hce_sub["mult"].sum() > 0:
        avg_hce = round(float((hce_sub["hce_tot"] * hce_sub["mult"]).sum() / hce_sub["mult"].sum()), 2)
    else:
        avg_hce = None

    return {
        "status": "available",
        "sample_households": int(len(sub)),
        "avg_household_size": avg_size,
        "avg_monthly_consumer_expenditure_inr": avg_hce,
    }


# ------------------------------------------------------------------
# Primary Tool Functions
# ------------------------------------------------------------------
@tool
def get_plfs_data(location: str, target_segment: str = "") -> Dict[str, Any]:
    """
    Retrieve official aggregate PLFS 2025 labour, wage, education, and occupation evidence
    from MoSPI unit-level microdata.

    Args:
        location: Geographic market name, e.g. "Ahmedabad", "Gujarat", "Pune", "Maharashtra"
        target_segment: Optional target customer segment
    """
    return run_plfs_search(location=location, target_segment=target_segment)


def run_plfs_search(
    location: str = "",
    target_segment: str = "",
    district: str = "",
    state: str = "",
    tru: str = ""
) -> Dict[str, Any]:
    """
    Main entry point for PLFS 2025 evidence research.
    Resolves geography, filters microdata, and executes survey-weighted calculations.
    """
    geo, geo_err = resolve_plfs_geography(location=location, state=state, district=district, tru=tru)
    if geo_err or geo is None:
        return {
            "status": "error",
            "source": "PLFS 2025",
            "source_type": "official_government_microdata",
            "error": geo_err or "Failed to resolve geography for PLFS.",
        }

    st_code = geo["st"]
    dc_code = geo["dc"]
    sec_filter = geo["sec"]

    # National level
    if st_code == 0:
        # Load Gujarat and Maharashtra as sample/national or return national notice
        # To avoid reading 368MB on national queries, query sample benchmark
        return {
            "status": "error",
            "source": "PLFS 2025",
            "source_type": "official_government_microdata",
            "error": "PLFS queries currently require a specific State or District location.",
        }

    # Load state microdata
    df_cper, df_chh, load_err = _get_state_data(st_code)
    if load_err or df_cper is None:
        return {
            "status": "error",
            "source": "PLFS 2025",
            "source_type": "official_government_microdata",
            "error": load_err or f"Failed to load data for state {st_code}.",
        }

    # Filter by District and Sector
    filtered_cper = df_cper.copy()
    if dc_code is not None:
        filtered_cper = filtered_cper[filtered_cper["dc"] == dc_code]
    if sec_filter is not None:
        filtered_cper = filtered_cper[filtered_cper["sec"] == sec_filter]

    if filtered_cper.empty:
        return {
            "status": "error",
            "source": "PLFS 2025",
            "source_type": "official_government_microdata",
            "error": f"No survey records found for {geo['state_name']} district code {dc_code}.",
        }

    try:
        # Sample & Estimated Population metadata
        sample_total = int(len(filtered_cper))
        sample_15plus = int((filtered_cper["age"] >= 15).sum())
        est_pop_total = int(round(filtered_cper["mult"].sum() / 100))
        est_pop_15plus = int(round(filtered_cper.loc[filtered_cper["age"] >= 15, "mult"].sum() / 100))

        # Perform calculations
        labour = _calculate_labour_indicators(filtered_cper)
        education = _calculate_education_evidence(filtered_cper)
        employment = _calculate_employment_distribution(filtered_cper)
        earnings = _calculate_earnings(filtered_cper)
        occupations = _calculate_occupations(filtered_cper)
        industries = _calculate_industries(filtered_cper)
        household = _calculate_household_evidence(df_chh, dc_code, sec_filter)

        return {
            "status": "success",
            "source": "PLFS 2025",
            "source_type": "official_government_microdata",
            "survey_metadata": {
                "survey_name": "Periodic Labour Force Survey (PLFS)",
                "survey_period": "January - December 2025 (Annual)",
                "visit": "Visit 1 (Cross-sectional annual sample)",
                "weighting_methodology": "MoSPI Survey Multiplier ('mult' weighted, est_pop = mult/100)",
            },
            "geography": {
                "state": geo["state_name"],
                "district": geo["district_name"],
                "st": st_code,
                "dc": dc_code,
                "sec": sec_filter,
                "level": geo["level"],
                "sector": geo["sector"],
                "requested_location": geo["requested_location"],
            },
            "sample_metadata": {
                "sample_persons_total": sample_total,
                "sample_persons_age_15_plus": sample_15plus,
                "estimated_population_total": est_pop_total,
                "estimated_population_age_15_plus": est_pop_15plus,
            },
            "labour_indicators": labour,
            "earnings": earnings,
            "education": education,
            "employment": employment,
            "occupation": occupations,
            "industry": industries,
            "household": household,
        }

    except Exception as e:
        return {
            "status": "error",
            "source": "PLFS 2025",
            "source_type": "official_government_microdata",
            "error": f"PLFS calculation error: {str(e)}",
        }
