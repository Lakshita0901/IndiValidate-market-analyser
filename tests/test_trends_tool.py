"""
tests/test_trends_tool.py
--------------------------
Unit tests for app/tools/trends_tool.py.

Rules:
- Mocked HTTP responses are used ONLY inside these unit tests.
- No mock data is used in the actual application.
- No real Google Trends requests are made during the test suite.
- Each test verifies behaviour independently.
"""

import json
import time
import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch, PropertyMock
import pandas as pd
import pytest


# ──────────────────────────────────────────────────────────────────
# Helpers to build fake DataFrames and pytrends exceptions
# ──────────────────────────────────────────────────────────────────

def _make_trend_df(keyword: str = "test keyword", n: int = 12) -> pd.DataFrame:
    """Return a minimal interest-over-time DataFrame."""
    dates = pd.date_range("2024-01-01", periods=n, freq="MS")
    values = [50 + i for i in range(n)]   # Gently rising series
    df = pd.DataFrame({keyword: values}, index=dates)
    return df


def _make_fake_response(status_code=429, retry_after=None):
    """Build a minimal fake requests.Response-like object."""
    resp = MagicMock()
    resp.status_code = status_code
    headers = {}
    if retry_after is not None:
        headers["Retry-After"] = str(retry_after)
    resp.headers = headers
    return resp


def _make_429_exception():
    """Create a pytrends TooManyRequestsError."""
    from pytrends import exceptions as pt_exc
    resp = _make_fake_response(429)
    exc = pt_exc.TooManyRequestsError("Too Many Requests", response=resp)
    return exc


def _make_429_with_retry_after(seconds: int = 5):
    from pytrends import exceptions as pt_exc
    resp = _make_fake_response(429, retry_after=seconds)
    exc = pt_exc.TooManyRequestsError("Too Many Requests", response=resp)
    return exc


def _make_server_error(status_code: int = 503):
    from pytrends import exceptions as pt_exc
    resp = _make_fake_response(status_code)
    exc = pt_exc.ResponseError("Server Error", response=resp)
    return exc


# Patch path: pytrends is imported inside the function at runtime, so we
# must patch it at its canonical location.
_TRENDREQ_PATH = "pytrends.request.TrendReq"


# ──────────────────────────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def isolated_cache(tmp_path, monkeypatch):
    """
    Redirect cache writes to a temp directory and reset the in-process
    throttle timestamp so tests run without artificial delays.
    """
    import app.tools.trends_tool as tt
    monkeypatch.setattr(tt, "TRENDS_CACHE_DIR", tmp_path)
    monkeypatch.setattr(tt, "TRENDS_INTER_REQUEST_S", 0)   # No real throttle in tests
    monkeypatch.setattr(tt, "_LAST_REQUEST_TIME", 0.0)
    monkeypatch.setattr(tt, "TRENDS_BACKOFF_BASE_S", 0)     # Instant backoff in tests
    monkeypatch.setattr(tt, "TRENDS_MAX_RETRIES", 3)
    yield tmp_path
# ──────────────────────────────────────────────────────────────────
# A. Successful response
# ──────────────────────────────────────────────────────────────────

def test_a_successful_response(isolated_cache):
    """A successful Trends response returns a valid evidence record."""
    kw = "organic delivery"
    df = _make_trend_df(kw)

    with patch(_TRENDREQ_PATH) as MockTR:
        instance = MockTR.return_value
        instance.interest_over_time.return_value = df

        from app.tools.trends_tool import _fetch_single_keyword_trend
        result = _fetch_single_keyword_trend(kw, "IN-GJ", "today 12-m")

    assert result.get("status") != "error", f"Unexpected error: {result}"
    assert result["keyword"] == kw
    assert result["geo"] == "IN-GJ"
    assert isinstance(result["relative_interest"], list)
    assert len(result["relative_interest"]) == 12
    assert result["trend_direction"] in ("rising", "falling", "stable", "unknown")
    assert result.get("cache_hit") is False


# ──────────────────────────────────────────────────────────────────
# B. HTTP 429 followed by success
# ──────────────────────────────────────────────────────────────────

def test_b_429_then_success(isolated_cache):
    """A 429 on the first attempt is retried and succeeds on the second."""
    kw = "vegetable box"
    df = _make_trend_df(kw)
    exc = _make_429_exception()

    call_count = {"n": 0}

    def side_effect():
        call_count["n"] += 1
        if call_count["n"] == 1:
            raise exc
        return df

    with patch(_TRENDREQ_PATH) as MockTR:
        instance = MockTR.return_value
        instance.interest_over_time.side_effect = side_effect

        from app.tools.trends_tool import _fetch_single_keyword_trend
        result = _fetch_single_keyword_trend(kw, "IN", "today 12-m")

    assert result.get("status") != "error", f"Should have succeeded on retry: {result}"
    assert call_count["n"] == 2


# ──────────────────────────────────────────────────────────────────
# C. HTTP 429 after all retries exhausted
# ──────────────────────────────────────────────────────────────────

def test_c_429_all_retries_exhausted(isolated_cache, monkeypatch):
    """When all retries are exhausted, return a structured rate_limited error."""
    import app.tools.trends_tool as tt
    monkeypatch.setattr(tt, "TRENDS_MAX_RETRIES", 2)

    kw = "farm produce"
    exc = _make_429_exception()

    with patch(_TRENDREQ_PATH) as MockTR:
        instance = MockTR.return_value
        instance.interest_over_time.side_effect = exc

        from app.tools.trends_tool import _fetch_single_keyword_trend
        result = _fetch_single_keyword_trend(kw, "IN", "today 12-m")

    assert result["status"] == "error"
    assert result["error_type"] == "rate_limited"
    assert result["retries_attempted"] == 2
    # Must NOT contain fabricated data
    assert "relative_interest" not in result


# ──────────────────────────────────────────────────────────────────
# D. Retry-After header respected
# ──────────────────────────────────────────────────────────────────

def test_d_retry_after_respected(isolated_cache, monkeypatch):
    """Retry-After header value is extracted and used as base wait (capped)."""
    import app.tools.trends_tool as tt
    monkeypatch.setattr(tt, "TRENDS_BACKOFF_MAX_S", 200)

    from app.tools.trends_tool import _backoff_wait, _parse_retry_after
    exc = _make_429_with_retry_after(seconds=30)

    retry_after = _parse_retry_after(exc)
    assert retry_after == 30

    # Wait should be at least the retry-after value (before jitter when base=0)
    wait = _backoff_wait(0, retry_after=retry_after)
    assert wait >= 30


# ──────────────────────────────────────────────────────────────────
# E. Temporary server error (5xx) retried
# ──────────────────────────────────────────────────────────────────

def test_e_server_error_retried(isolated_cache):
    """A 503 error is retried and if second attempt succeeds, returns data."""
    kw = "home delivery food"
    df = _make_trend_df(kw)
    exc = _make_server_error(503)

    call_count = {"n": 0}

    def side_effect():
        call_count["n"] += 1
        if call_count["n"] == 1:
            raise exc
        return df

    with patch(_TRENDREQ_PATH) as MockTR:
        instance = MockTR.return_value
        instance.interest_over_time.side_effect = side_effect

        from app.tools.trends_tool import _fetch_single_keyword_trend
        result = _fetch_single_keyword_trend(kw, "IN", "today 12-m")

    assert result.get("status") != "error"
    assert call_count["n"] == 2


# ──────────────────────────────────────────────────────────────────
# F. Network failure (OSError)
# ──────────────────────────────────────────────────────────────────

def test_f_network_failure(isolated_cache, monkeypatch):
    """OSError (e.g. DNS failure) after all retries returns network_error."""
    import app.tools.trends_tool as tt
    monkeypatch.setattr(tt, "TRENDS_MAX_RETRIES", 2)

    kw = "grocery subscription"

    with patch(_TRENDREQ_PATH) as MockTR:
        instance = MockTR.return_value
        instance.interest_over_time.side_effect = OSError("Name or service not known")

        from app.tools.trends_tool import _fetch_single_keyword_trend
        result = _fetch_single_keyword_trend(kw, "IN", "today 12-m")

    assert result["status"] == "error"
    assert result["error_type"] == "network_error"
    assert "relative_interest" not in result


# ──────────────────────────────────────────────────────────────────
# G. Empty result (no_data)
# ──────────────────────────────────────────────────────────────────

def test_g_empty_result(isolated_cache):
    """An empty DataFrame is reported as no_data, not an error."""
    kw = "very obscure niche product"

    with patch(_TRENDREQ_PATH) as MockTR:
        instance = MockTR.return_value
        instance.interest_over_time.return_value = pd.DataFrame()

        from app.tools.trends_tool import _fetch_single_keyword_trend
        result = _fetch_single_keyword_trend(kw, "IN", "today 12-m")

    assert result["status"] == "no_data"
    assert "relative_interest" not in result
    # no_data must NOT be cached
    from app.tools.trends_tool import _cache_read
    assert _cache_read(kw, "IN", "today 12-m") is None


# ──────────────────────────────────────────────────────────────────
# H. Cache hit
# ──────────────────────────────────────────────────────────────────

def test_h_cache_hit(isolated_cache):
    """A second call for the same keyword uses the on-disk cache (no network)."""
    kw = "tiffin delivery"
    df = _make_trend_df(kw)

    with patch(_TRENDREQ_PATH) as MockTR:
        instance = MockTR.return_value
        instance.interest_over_time.return_value = df

        from app.tools.trends_tool import _fetch_single_keyword_trend
        first = _fetch_single_keyword_trend(kw, "IN", "today 12-m")
        assert first.get("cache_hit") is False

        # Second call — must NOT call TrendReq again
        second = _fetch_single_keyword_trend(kw, "IN", "today 12-m")

    assert second.get("cache_hit") is True
    assert second.get("keyword") == kw
    assert second.get("status") != "error"
    # TrendReq was only instantiated once (during the first call)
    assert MockTR.call_count == 1


# ──────────────────────────────────────────────────────────────────
# I. Cache expiration
# ──────────────────────────────────────────────────────────────────

def test_i_cache_expiration(isolated_cache, monkeypatch):
    """An expired cache entry triggers a fresh network request."""
    import app.tools.trends_tool as tt

    kw = "fresh produce"
    df = _make_trend_df(kw)

    # Write a cache file with stored_at in the past (beyond TTL)
    from app.tools.trends_tool import _cache_key
    key = _cache_key(kw, "IN", "today 12-m")
    cache_file = isolated_cache / f"{key}.json"
    stale_result = {
        "source": "google_trends", "keyword": kw,
        "relative_interest": [1] * 12, "cache_hit": False,
    }
    cache_file.write_text(
        json.dumps({"stored_at": time.time() - 999999, "result": stale_result}),
        encoding="utf-8",
    )

    with patch(_TRENDREQ_PATH) as MockTR:
        instance = MockTR.return_value
        instance.interest_over_time.return_value = df

        from app.tools.trends_tool import _fetch_single_keyword_trend
        result = _fetch_single_keyword_trend(kw, "IN", "today 12-m")

    # Must have made a fresh request
    assert MockTR.call_count == 1
    assert result.get("cache_hit") is False


# ──────────────────────────────────────────────────────────────────
# J. Partial success across multiple keywords
# ──────────────────────────────────────────────────────────────────

def test_j_partial_success_multiple_keywords(isolated_cache, monkeypatch):
    """
    When one keyword succeeds and one fails, run_trends_search returns
    both the successful result and the structured error for the failed one.
    """
    import app.tools.trends_tool as tt
    monkeypatch.setattr(tt, "TRENDS_MAX_KEYWORDS", 3)
    monkeypatch.setattr(tt, "TRENDS_MAX_RETRIES", 0)  # Fail fast

    kw_ok = "organic food"
    kw_fail = "unknown niche"
    df_ok = _make_trend_df(kw_ok)

    call_map = {kw_ok: df_ok, kw_fail: _make_429_exception()}

    def side_effect():
        # We can't easily inspect which keyword was requested without build_payload,
        # so we track calls in order.
        side_effect.calls = getattr(side_effect, "calls", 0) + 1
        if side_effect.calls % 2 == 1:
            return df_ok
        raise _make_429_exception()

    side_effect.calls = 0

    with patch(_TRENDREQ_PATH) as MockTR:
        instance = MockTR.return_value
        instance.interest_over_time.side_effect = side_effect

        from app.tools.trends_tool import run_trends_search
        results = run_trends_search([kw_ok, kw_fail], location="")

    assert len(results) == 2
    statuses = [r.get("status") for r in results]
    assert "error" in statuses       # The failed keyword has a structured error
    successes = [r for r in results if r.get("status") != "error"]
    assert len(successes) >= 1


# ──────────────────────────────────────────────────────────────────
# K. No fabricated values on failure
# ──────────────────────────────────────────────────────────────────

def test_k_no_fabricated_values_on_failure(isolated_cache, monkeypatch):
    """An error result must not contain relative_interest or trend_direction."""
    import app.tools.trends_tool as tt
    monkeypatch.setattr(tt, "TRENDS_MAX_RETRIES", 0)

    kw = "grocery app"
    exc = _make_429_exception()

    with patch(_TRENDREQ_PATH) as MockTR:
        instance = MockTR.return_value
        instance.interest_over_time.side_effect = exc

        from app.tools.trends_tool import _fetch_single_keyword_trend
        result = _fetch_single_keyword_trend(kw, "IN", "today 12-m")

    assert result["status"] == "error"
    assert "relative_interest" not in result
    assert "trend_direction" not in result


# ──────────────────────────────────────────────────────────────────
# L. Geography mapping
# ──────────────────────────────────────────────────────────────────

def test_l_geo_mapping():
    """Location strings map correctly to Google Trends geo codes."""
    from app.tools.trends_tool import _map_location_to_geo

    assert _map_location_to_geo("Ahmedabad") == "IN-GJ"
    assert _map_location_to_geo("Gujarat") == "IN-GJ"
    assert _map_location_to_geo("Mumbai") == "IN-MH"
    assert _map_location_to_geo("Maharashtra") == "IN-MH"
    assert _map_location_to_geo("Not specified") == "IN"
    assert _map_location_to_geo("") == "IN"
    assert _map_location_to_geo("India") == "IN"


# ──────────────────────────────────────────────────────────────────
# M. Keyword limit respected
# ──────────────────────────────────────────────────────────────────

def test_m_keyword_limit(isolated_cache, monkeypatch):
    """run_trends_search processes at most TRENDS_MAX_KEYWORDS keywords."""
    import app.tools.trends_tool as tt
    monkeypatch.setattr(tt, "TRENDS_MAX_KEYWORDS", 2)

    many_keywords = ["kw1", "kw2", "kw3", "kw4", "kw5"]
    call_count = {"n": 0}

    def side_effect():
        call_count["n"] += 1
        return _make_trend_df("kw")

    with patch(_TRENDREQ_PATH) as MockTR:
        instance = MockTR.return_value
        instance.interest_over_time.side_effect = side_effect

        from app.tools.trends_tool import run_trends_search
        results = run_trends_search(many_keywords, location="")

    assert len(results) == 2
    assert call_count["n"] == 2


# ──────────────────────────────────────────────────────────────────
# N. Backoff formula correctness
# ──────────────────────────────────────────────────────────────────

def test_n_backoff_formula(monkeypatch):
    """_backoff_wait returns values within expected range."""
    import app.tools.trends_tool as tt
    monkeypatch.setattr(tt, "TRENDS_BACKOFF_BASE_S", 10)
    monkeypatch.setattr(tt, "TRENDS_BACKOFF_MAX_S", 200)

    from app.tools.trends_tool import _backoff_wait

    # attempt=0: 10*2^0 = 10 + jitter [0..5] → [10, 15]
    for _ in range(20):
        w = _backoff_wait(0)
        assert 10 <= w <= 15 + 0.001, f"attempt=0 wait {w} out of range"

    # attempt=2: 10*2^2 = 40 + jitter [0..5] → [40, 45]
    for _ in range(20):
        w = _backoff_wait(2)
        assert 40 <= w <= 45 + 0.001, f"attempt=2 wait {w} out of range"

    # attempt=10: capped at 200 + jitter [0..5] → [200, 205]
    for _ in range(10):
        w = _backoff_wait(10)
        assert 200 <= w <= 205 + 0.001, f"attempt=10 wait {w} out of range"
