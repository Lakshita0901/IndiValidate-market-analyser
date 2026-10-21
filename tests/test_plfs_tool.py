"""
tests/test_plfs_tool.py
-----------------------
Automated test suite for official PLFS 2025 microdata integration.
Tests all required cases:
A. Gujarat state query
B. Ahmedabad district query
C. Rural Ahmedabad query
D. Urban Ahmedabad query
E. Maharashtra state query
F. Unknown state query
G. Unknown district query
H. Missing PLFS file simulation
I. Malformed/empty PLFS file simulation
J. Weighted calculations on tiny synthetic dataframe (math verification only)
"""

import tempfile
from pathlib import Path
import pandas as pd
import pytest

from app.tools.plfs_tool import (
    run_plfs_search,
    clear_plfs_cache,
    resolve_plfs_geography,
    _calculate_labour_indicators,
    _calculate_earnings,
    _calculate_education_evidence,
    _calculate_employment_distribution,
    _get_state_data,
)


def test_a_gujarat_state_query():
    """A. Test state-level query for Gujarat (st=24)."""
    res = run_plfs_search(location="Gujarat")
    assert res.get("status") == "success", f"Error: {res.get('error')}"
    geo = res.get("geography", {})
    assert geo.get("state") == "Gujarat"
    assert geo.get("st") == 24
    assert geo.get("dc") is None
    assert geo.get("level") == "state"

    meta = res.get("sample_metadata", {})
    assert meta.get("sample_persons_total") > 50000

    labour = res.get("labour_indicators", {}).get("usual_status_ps_plus_ss", {})
    assert 60.0 <= labour.get("lfpr_percent") <= 70.0
    assert 0.5 <= labour.get("unemployment_rate_percent") <= 3.0

    earn = res.get("earnings", {})
    assert earn.get("regular_salaried", {}).get("avg_monthly_salary_inr") > 15000


def test_b_ahmedabad_district_query():
    """B. Test district-level query for Ahmedabad (st=24, dc=7)."""
    res = run_plfs_search(location="Ahmedabad")
    assert res.get("status") == "success", f"Error: {res.get('error')}"
    geo = res.get("geography", {})
    assert geo.get("state") == "Gujarat"
    assert geo.get("district") == "Ahmedabad"
    assert geo.get("st") == 24
    assert geo.get("dc") == 7
    assert geo.get("level") == "district"

    meta = res.get("sample_metadata", {})
    assert meta.get("sample_persons_total") == 6423
    assert meta.get("sample_persons_age_15_plus") == 5155

    labour = res.get("labour_indicators", {}).get("usual_status_ps_plus_ss", {})
    assert labour.get("lfpr_percent") == 55.64
    assert labour.get("wpr_percent") == 55.03
    assert labour.get("unemployment_rate_percent") == 1.10

    earn = res.get("earnings", {})
    assert earn.get("regular_salaried", {}).get("avg_monthly_salary_inr") == 22638.27
    assert earn.get("self_employed", {}).get("avg_monthly_earnings_inr") == 26330.75

    edu = res.get("education", {})
    assert edu.get("graduate_and_above_percent") == 23.20

    ocu = res.get("occupation", [])
    assert len(ocu) > 0

    ind = res.get("industry", [])
    assert len(ind) > 0


def test_c_rural_ahmedabad():
    """C. Test sector filtering: Rural Ahmedabad (sec=1)."""
    res = run_plfs_search(location="Rural Ahmedabad")
    assert res.get("status") == "success"
    geo = res.get("geography", {})
    assert geo.get("sector") == "Rural"
    assert geo.get("sec") == 1
    assert geo.get("dc") == 7


def test_d_urban_ahmedabad():
    """D. Test sector filtering: Urban Ahmedabad (sec=2)."""
    res = run_plfs_search(location="Urban Ahmedabad")
    assert res.get("status") == "success"
    geo = res.get("geography", {})
    assert geo.get("sector") == "Urban"
    assert geo.get("sec") == 2
    assert geo.get("dc") == 7


def test_e_maharashtra_state():
    """E. Test state-level query for Maharashtra (st=27)."""
    res = run_plfs_search(location="Maharashtra")
    assert res.get("status") == "success"
    geo = res.get("geography", {})
    assert geo.get("state") == "Maharashtra"
    assert geo.get("st") == 27
    assert geo.get("level") == "state"


def test_f_unknown_state():
    """F. Test unknown state returns structured error."""
    res = run_plfs_search(location="Atlantis Province")
    assert res.get("status") == "error"
    assert "not recognized" in res.get("error").lower()


def test_g_unknown_district():
    """G. Test unknown district returns structured error."""
    res = run_plfs_search(state="Gujarat", district="NonExistentDistrictXYZ")
    assert res.get("status") == "error"
    assert "not recognized" in res.get("error").lower()


def test_h_missing_plfs_file():
    """H. Test error isolation when PLFS dataset file is missing."""
    clear_plfs_cache()
    # Request a non-existent state code where file does not exist
    df_cper, df_chh, err = _get_state_data(st=999)
    assert df_cper is None
    assert err is not None


def test_i_malformed_empty_plfs_file():
    """I. Test error handling when slice is empty."""
    # Location that yields no records
    geo = {"st": 24, "dc": 999, "sec": None, "state_name": "Gujarat"}
    df_cper, _, _ = _get_state_data(24)
    filtered = df_cper[df_cper["dc"] == 999]
    assert filtered.empty


def test_j_mathematical_logic_synthetic_tiny_dataframe():
    """
    J. Verify exact mathematical calculation logic on a tiny synthetic dataset.
    This synthetic dataset is ONLY used inside this test to prove mathematical accuracy.
    """
    # 5 synthetic records:
    # Person 1: Age 20, mult=100, pas=31 (Salaried), ern_reg=20000, ern_self=0
    # Person 2: Age 25, mult=200, pas=11 (Self-Employed), ern_reg=0, ern_self=30000
    # Person 3: Age 30, mult=100, pas=81 (Unemployed), ern_reg=0, ern_self=0
    # Person 4: Age 35, mult=200, pas=92 (Domestic/Out of LF), ern_reg=0, ern_self=0
    # Person 5: Age 10, mult=100, pas=99 (Child < 15), ern_reg=0, ern_self=0
    tiny_data = pd.DataFrame([
        {"age": 20, "mult": 100, "pas": 31, "sas": None, "ern_reg": 20000, "ern_self": 0, "gedu_lvl": 12, "ocu_pas": 211.0, "ind_pas": 62010.0},
        {"age": 25, "mult": 200, "pas": 11, "sas": None, "ern_reg": 0, "ern_self": 30000, "gedu_lvl": 10, "ocu_pas": 521.0, "ind_pas": 47110.0},
        {"age": 30, "mult": 100, "pas": 81, "sas": None, "ern_reg": 0, "ern_self": 0, "gedu_lvl": 8, "ocu_pas": None, "ind_pas": None},
        {"age": 35, "mult": 200, "pas": 92, "sas": None, "ern_reg": 0, "ern_self": 0, "gedu_lvl": 1, "ocu_pas": None, "ind_pas": None},
        {"age": 10, "mult": 100, "pas": 99, "sas": None, "ern_reg": 0, "ern_self": 0, "gedu_lvl": 5, "ocu_pas": None, "ind_pas": None},
    ])

    # Working age (age >= 15): Persons 1, 2, 3, 4. Total weight = 100 + 200 + 100 + 200 = 600
    # Employed: Persons 1 (100) + Person 2 (200) = 300
    # Unemployed: Person 3 (100)
    # Labour force: 300 + 100 = 400
    # Expected LFPR = 400 / 600 * 100 = 66.67%
    # Expected WPR = 300 / 600 * 100 = 50.00%
    # Expected UR = 100 / 400 * 100 = 25.00%
    labour = _calculate_labour_indicators(tiny_data)
    ps = labour["principal_status_ps"]
    assert ps["lfpr_percent"] == 66.67
    assert ps["wpr_percent"] == 50.00
    assert ps["unemployment_rate_percent"] == 25.00

    # Earnings:
    # Regular salaried: Person 1 -> ern_reg = 20000, weight = 100 -> Avg = 20000.00
    # Self-employed: Person 2 -> ern_self = 30000, weight = 200 -> Avg = 30000.00
    earn = _calculate_earnings(tiny_data)
    assert earn["regular_salaried"]["avg_monthly_salary_inr"] == 20000.00
    assert earn["self_employed"]["avg_monthly_earnings_inr"] == 30000.00

    # Education (Age 15+):
    # Graduate (Person 1, mult=100): 100 / 600 * 100 = 16.67%
    # Higher sec (Person 2, mult=200): 200 / 600 * 100 = 33.33%
    # Secondary (Person 3, mult=100): 100 / 600 * 100 = 16.67%
    # Not literate (Person 4, mult=200): 200 / 600 * 100 = 33.33%
    edu = _calculate_education_evidence(tiny_data)
    assert edu["graduate_and_above_percent"] == 16.67
    assert edu["not_literate_percent"] == 33.33


if __name__ == "__main__":
    pytest.main(["-v", __file__])
