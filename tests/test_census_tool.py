"""
tests/test_census_tool.py
-------------------------
Automated test suite for Census 2011 evidence tool.
Tests all requirements:
1. Gujarat state query
2. Ahmedabad district query
3. A rural/urban query
4. Missing district (state-only query)
5. Unknown district
6. Missing Census file
7. Malformed/empty dataset
8. Non-Gujarat district fallback to state level
9. National / unspecified location query
"""

from pathlib import Path
import tempfile
import pytest

from app.tools.census_tool import (
    run_census_search,
    clear_cache,
    resolve_geography,
    _load_pca_df,
    _load_excel_rows,
)


def test_1_gujarat_state_query():
    """Test state-only query for Gujarat."""
    clear_cache()
    res = run_census_search.invoke({"location": "Gujarat"})
    assert res.get("status") == "success", f"Failed: {res.get('error')}"
    geo = res.get("geography", {})
    assert geo.get("state") == "Gujarat"
    assert geo.get("district") is None
    assert geo.get("level") == "state"

    pca = res.get("pca", {})
    assert pca.get("status") == "available"
    # Gujarat total population 2011 is 60,439,692
    assert pca.get("population", {}).get("total") == 60439692
    assert pca.get("population", {}).get("male") == 31491260
    assert pca.get("population", {}).get("female") == 28948432

    c08 = res.get("education", {})
    assert c08.get("status") == "available"
    assert c08.get("summary", {}).get("literates", {}).get("persons") == 41093358

    c08a = res.get("higher_education", {})
    assert c08a.get("status") == "available"
    assert c08a.get("summary", {}).get("disciplines", {}).get("engineering_and_technology", {}).get("persons") == 322179


def test_2_ahmedabad_district_query():
    """Test district query for Ahmedabad."""
    clear_cache()
    res = run_census_search.invoke({"location": "Ahmedabad"})
    assert res.get("status") == "success", f"Failed: {res.get('error')}"
    geo = res.get("geography", {})
    assert geo.get("state") == "Gujarat"
    assert geo.get("district") == "Ahmadabad"
    assert geo.get("level") == "district"

    pca = res.get("pca", {})
    assert pca.get("population", {}).get("total") == 7214225
    assert pca.get("households") == 1510134
    assert pca.get("workers", {}).get("total_workers") == 2594952

    c08 = res.get("education", {})
    assert c08.get("is_state_fallback") is False
    assert c08.get("summary", {}).get("levels", {}).get("graduate_and_above", {}).get("persons") == 817630

    c08a = res.get("higher_education", {})
    assert c08a.get("summary", {}).get("disciplines", {}).get("medicine", {}).get("persons") == 26190
    assert c08a.get("summary", {}).get("disciplines", {}).get("engineering_and_technology", {}).get("persons") == 86953


def test_3_rural_urban_query():
    """Test residence context filtering (Rural & Urban)."""
    clear_cache()
    # Urban query
    res_urban = run_census_search.invoke({"location": "Ahmedabad (Urban)"})
    assert res_urban.get("status") == "success"
    assert res_urban.get("geography", {}).get("tru") == "Urban"
    assert res_urban.get("education", {}).get("summary", {}).get("total_persons") == 6063047

    # Rural query
    res_rural = run_census_search.invoke({"location": "Rural Gujarat"})
    assert res_rural.get("status") == "success"
    assert res_rural.get("geography", {}).get("tru") == "Rural"
    assert res_rural.get("education", {}).get("summary", {}).get("total_persons") == 34694609


def test_4_missing_district_state_only():
    """Test query with state provided and missing district parameter."""
    clear_cache()
    res = run_census_search.invoke({"state": "Maharashtra", "district": ""})
    assert res.get("status") == "success"
    geo = res.get("geography", {})
    assert geo.get("state") == "Maharashtra"
    assert geo.get("district") is None
    assert geo.get("level") == "state"
    assert res.get("pca", {}).get("population", {}).get("total") == 112374333


def test_5_unknown_district():
    """Test query with an unknown / invalid district name."""
    clear_cache()
    res = run_census_search.invoke({"location": "Atlantis City"})
    assert res.get("status") == "error"
    assert "not recognized" in res.get("error").lower() or "not found" in res.get("error").lower()


def test_6_missing_census_file():
    """Test behavior when a dataset file does not exist."""
    clear_cache()
    dummy_path = Path("data/census/pca/non_existent_file.csv")
    df, err = _load_pca_df(pca_path=dummy_path)
    assert df is None
    assert err is not None
    assert "not found" in err.lower() or "empty" in err.lower()
    clear_cache()


def test_7_malformed_empty_dataset():
    """Test behavior when a dataset file is empty or corrupted."""
    clear_cache()
    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
        f.write("col_a,col_b\n")
        temp_path = Path(f.name)

    try:
        df, err = _load_pca_df(pca_path=temp_path)
        assert df is None
        assert err is not None
        assert "empty or malformed" in err.lower()
    finally:
        if temp_path.exists():
            temp_path.unlink()
        clear_cache()


def test_8_non_gujarat_district_fallback():
    """Test district outside Gujarat falls back gracefully to state-level C-08."""
    clear_cache()
    res = run_census_search.invoke({"location": "Pune"})
    assert res.get("status") == "success"
    geo = res.get("geography", {})
    assert geo.get("district") == "Pune"
    assert geo.get("state") == "Maharashtra"

    # PCA has exact Pune district data
    assert res.get("pca", {}).get("geography_level") == "district"
    assert res.get("pca", {}).get("population", {}).get("total") == 9429408

    # C-08 & C-08A fall back to Maharashtra state level
    c08 = res.get("education", {})
    assert c08.get("geography_level") == "state"
    assert c08.get("is_state_fallback") is True


def test_9_national_query():
    """Test India / Pan India / Unspecified query."""
    clear_cache()
    res = run_census_search.invoke({"location": "India"})
    assert res.get("status") == "success"
    geo = res.get("geography", {})
    assert geo.get("state") == "India"
    assert geo.get("level") == "national"
    assert res.get("pca", {}).get("population", {}).get("total") == 1210854977
    assert res.get("education", {}).get("summary", {}).get("total_persons") == 1210854977


if __name__ == "__main__":
    pytest.main(["-v", __file__])
