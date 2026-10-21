"""
trends_tool.py
--------------
Fetches real Google Trends data for keywords related to a market idea.

IMPORTANT: Google does NOT have a public REST API for Trends data.
The official Trends API is in alpha/limited access.
We use `pytrends` (the standard community library) as a practical implementation.

This entire implementation is isolated inside this file.
Later, you can replace the pytrends internals with the official Google Trends API
without touching any other file in the project.

pytrends docs: https://github.com/GeneralMills/pytrends

NOTE: Google Trends data is RELATIVE SEARCH INTEREST (0-100 scale).
It does NOT represent absolute search counts.
We never say "X people searched for this."
We say "Relative search interest = Y (scale 0-100)."

Configuration (via environment variables, all optional):
    TRENDS_MAX_KEYWORDS      Max keywords to query per run.        Default: 3
    TRENDS_INTER_REQUEST_S   Sleep seconds between requests.       Default: 8
    TRENDS_MAX_RETRIES       Max retry attempts on transient err.  Default: 3
    TRENDS_BACKOFF_BASE_S    Base wait for first retry (seconds).  Default: 15
    TRENDS_BACKOFF_MAX_S     Hard cap on a single retry wait.      Default: 120
    TRENDS_CACHE_TTL_S       Cache time-to-live in seconds.        Default: 3600
    TRENDS_CACHE_DIR         Dir for on-disk response cache.       Default: data/trends_cache

Install: pip install pytrends
"""

import json
import math
import os
import random
import time
from hashlib import sha256
from pathlib import Path

from langchain_core.tools import tool


# ------------------------------------------------------------------
# Configuration — read from environment with safe defaults.
# Never log the actual values.
# ------------------------------------------------------------------

def _env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except (ValueError, TypeError):
        return default


TRENDS_MAX_KEYWORDS: int = _env_int("TRENDS_MAX_KEYWORDS", 3)
TRENDS_INTER_REQUEST_S: int = _env_int("TRENDS_INTER_REQUEST_S", 8)
TRENDS_MAX_RETRIES: int = _env_int("TRENDS_MAX_RETRIES", 3)
TRENDS_BACKOFF_BASE_S: int = _env_int("TRENDS_BACKOFF_BASE_S", 15)
TRENDS_BACKOFF_MAX_S: int = _env_int("TRENDS_BACKOFF_MAX_S", 120)
TRENDS_CACHE_TTL_S: int = _env_int("TRENDS_CACHE_TTL_S", 3600)
TRENDS_CACHE_DIR: Path = Path(os.environ.get("TRENDS_CACHE_DIR", "data/trends_cache"))

# In-process throttle: timestamp of the last outgoing request.
_LAST_REQUEST_TIME: float = 0.0


# ------------------------------------------------------------------
# On-disk TTL cache
# Key: SHA-256 of (keyword, geo, timeframe).
# File: data/trends_cache/<key>.json  → {stored_at, result}
# Failures (status="error"/"no_data") are NEVER cached.
# ------------------------------------------------------------------

def _cache_key(keyword: str, geo: str, timeframe: str) -> str:
    raw = f"{keyword.lower().strip()}|{geo}|{timeframe}"
    return sha256(raw.encode()).hexdigest()


def _cache_read(keyword: str, geo: str, timeframe: str):
    """Return cached result dict if valid and not expired, else None."""
    TRENDS_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    key = _cache_key(keyword, geo, timeframe)
    cache_file = TRENDS_CACHE_DIR / f"{key}.json"
    if not cache_file.exists():
        return None
    try:
        data = json.loads(cache_file.read_text(encoding="utf-8"))
        age = time.time() - data.get("stored_at", 0)
        if age > TRENDS_CACHE_TTL_S:
            cache_file.unlink(missing_ok=True)
            return None
        result = data.get("result")
        if result is not None:
            result = dict(result)
            result["cache_hit"] = True
            result["cache_age_seconds"] = int(age)
            result.setdefault(
                "retrieval_note",
                (f"Served from local cache (age {int(age)}s / TTL {TRENDS_CACHE_TTL_S}s). "
                 "Observations cover the original date_labels period — not current."),
            )
        return result
    except Exception:
        return None


def _cache_write(keyword: str, geo: str, timeframe: str, result: dict) -> None:
    """Persist a successful result to disk. Never cache errors or no_data."""
    if result.get("status") in ("error", "no_data"):
        return
    TRENDS_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    key = _cache_key(keyword, geo, timeframe)
    cache_file = TRENDS_CACHE_DIR / f"{key}.json"
    try:
        payload = {"stored_at": time.time(), "result": result}
        cache_file.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    except Exception:
        pass  # Non-fatal


def _cache_invalidate(keyword: str, geo: str, timeframe: str) -> None:
    """Remove a specific cache entry (used in tests)."""
    key = _cache_key(keyword, geo, timeframe)
    (TRENDS_CACHE_DIR / f"{key}.json").unlink(missing_ok=True)


# ------------------------------------------------------------------
# Request throttle
# ------------------------------------------------------------------

def _throttle_wait() -> None:
    """Ensure at least TRENDS_INTER_REQUEST_S seconds between outgoing requests."""
    global _LAST_REQUEST_TIME
    now = time.time()
    elapsed = now - _LAST_REQUEST_TIME
    if elapsed < TRENDS_INTER_REQUEST_S:
        time.sleep(TRENDS_INTER_REQUEST_S - elapsed)
    _LAST_REQUEST_TIME = time.time()


# ------------------------------------------------------------------
# Retry helpers
# ------------------------------------------------------------------

def _backoff_wait(attempt: int, retry_after=None) -> float:
    """
    Exponential back-off with jitter.
      wait = min(TRENDS_BACKOFF_MAX_S, base * 2^attempt) + uniform jitter [0, base/2]
    If Retry-After header value is present, honour it (still capped at max).
    """
    if retry_after is not None:
        try:
            base_wait = min(int(retry_after), TRENDS_BACKOFF_MAX_S)
        except (TypeError, ValueError):
            base_wait = min(TRENDS_BACKOFF_BASE_S * (2 ** attempt), TRENDS_BACKOFF_MAX_S)
    else:
        base_wait = min(TRENDS_BACKOFF_BASE_S * (2 ** attempt), TRENDS_BACKOFF_MAX_S)
    jitter = random.uniform(0, TRENDS_BACKOFF_BASE_S / 2)
    return base_wait + jitter


def _parse_retry_after(exc) -> int | None:
    """Extract Retry-After header value from a pytrends exception."""
    try:
        header = exc.response.headers.get("Retry-After", "")
        if header:
            return int(header)
    except (AttributeError, ValueError, TypeError):
        pass
    return None


def _extract_status_code(exc) -> int:
    try:
        return exc.response.status_code
    except AttributeError:
        return 0


# ------------------------------------------------------------------
# Trend direction helper
# ------------------------------------------------------------------

def _get_trend_direction(values: list) -> str:
    """
    Determine the general trend direction from a time series of relative interest values.

    Returns "rising", "falling", or "stable".
    """
    if not values or len(values) < 4:
        return "unknown"
    n = len(values)
    first_quarter = values[:n // 4]
    last_quarter = values[-(n // 4):]
    avg_start = sum(first_quarter) / len(first_quarter)
    avg_end = sum(last_quarter) / len(last_quarter)
    if avg_end > avg_start * 1.10:
        return "rising"
    elif avg_end < avg_start * 0.90:
        return "falling"
    else:
        return "stable"


# ------------------------------------------------------------------
# Core fetch: cache → throttle → request → retry on transient errors
# ------------------------------------------------------------------

def _fetch_single_keyword_trend(keyword: str, geo: str, timeframe: str) -> dict:
    """
    Fetch Google Trends data for a single keyword with:
      - Disk cache (TTL-based, never caches failures)
      - Per-process request throttle
      - Bounded exponential-backoff retries with jitter for 429 and 5xx
      - Structured error classification: rate_limited / http_error /
        network_error / library_missing / no_data / unexpected

    Never returns mock or fabricated data.
    """
    # 1. Cache check
    cached = _cache_read(keyword, geo, timeframe)
    if cached is not None:
        return cached

    # 2. Import pytrends lazily
    try:
        from pytrends import exceptions as pt_exc
        from pytrends.request import TrendReq
    except ImportError:
        return {
            "source": "google_trends",
            "keyword": keyword,
            "status": "error",
            "error_type": "library_missing",
            "error": "pytrends library not installed. Run: pip install pytrends",
        }

    last_error = None
    attempt = 0

    while attempt <= TRENDS_MAX_RETRIES:
        try:
            _throttle_wait()

            pytrends = TrendReq(hl="en-US", tz=330, timeout=(10, 25))
            pytrends.build_payload(
                kw_list=[keyword],
                cat=0,
                timeframe=timeframe,
                geo=geo,
                gprop="",
            )
            df = pytrends.interest_over_time()

            if df is None or df.empty:
                return {
                    "source": "google_trends",
                    "keyword": keyword,
                    "geo": geo,
                    "time_range": timeframe,
                    "status": "no_data",
                    "error": f"No Google Trends data available for keyword: '{keyword}'",
                }

            if "isPartial" in df.columns:
                df = df.drop(columns=["isPartial"])

            values = (
                df[keyword].tolist() if keyword in df.columns else df.iloc[:, 0].tolist()
            )
            compact_values = [round(float(v), 1) for v in values]
            date_labels = [str(d.date()) for d in df.index.tolist()]

            result = {
                "source": "google_trends",
                "keyword": keyword,
                "geo": geo,
                "time_range": timeframe,
                "relative_interest_note": (
                    "Scale 0-100. 100 = peak popularity in period. "
                    "Not absolute search volume."
                ),
                "relative_interest": compact_values,
                "date_labels": date_labels,
                "trend_direction": _get_trend_direction(compact_values),
                "latest_value": compact_values[-1] if compact_values else 0,
                "peak_value": max(compact_values) if compact_values else 0,
                "average_value": (
                    round(sum(compact_values) / len(compact_values), 1)
                    if compact_values else 0
                ),
                "cache_hit": False,
                "retrieval_note": f"Fresh fetch (attempt {attempt + 1}).",
            }
            _cache_write(keyword, geo, timeframe, result)
            return result

        except pt_exc.TooManyRequestsError as e:
            last_error = e
            retry_after = _parse_retry_after(e)
            attempt += 1
            if attempt > TRENDS_MAX_RETRIES:
                break
            time.sleep(_backoff_wait(attempt - 1, retry_after))

        except pt_exc.ResponseError as e:
            last_error = e
            status_code = _extract_status_code(e)
            if status_code in (500, 502, 503, 504):
                attempt += 1
                if attempt > TRENDS_MAX_RETRIES:
                    break
                time.sleep(_backoff_wait(attempt - 1, None))
            else:
                return {
                    "source": "google_trends",
                    "keyword": keyword,
                    "geo": geo,
                    "status": "error",
                    "error_type": "http_error",
                    "error": f"Google Trends HTTP error for '{keyword}': {e}",
                }

        except OSError as e:
            # Network-level failures: DNS, timeout, connection refused
            last_error = e
            attempt += 1
            if attempt > TRENDS_MAX_RETRIES:
                break
            time.sleep(_backoff_wait(attempt - 1, None))

        except Exception as e:
            return {
                "source": "google_trends",
                "keyword": keyword,
                "geo": geo,
                "status": "error",
                "error_type": "unexpected",
                "error": f"Google Trends fetch failed for '{keyword}': {e}",
            }

    # Retries exhausted
    try:
        from pytrends import exceptions as pt_exc
        is_429 = isinstance(last_error, pt_exc.TooManyRequestsError)
    except ImportError:
        is_429 = False
    error_type = "rate_limited" if is_429 else "network_error"
    return {
        "source": "google_trends",
        "keyword": keyword,
        "geo": geo,
        "status": "error",
        "error_type": error_type,
        "error": (
            f"Google Trends fetch failed for '{keyword}' after "
            f"{TRENDS_MAX_RETRIES} retries: {last_error}"
        ),
        "retries_attempted": TRENDS_MAX_RETRIES,
    }


# ------------------------------------------------------------------
# Geography mapping
# ------------------------------------------------------------------

def _map_location_to_geo(location: str) -> str:
    """
    Map an Indian city or state name to a Google Trends geo code.

    Google Trends supports country-level (e.g., 'IN') and sub-region level (e.g., 'IN-MH').
    We map known Indian states to their codes. Cities get mapped to their state.

    If location is unknown, we fall back to 'IN' (all India).
    """
    location_lower = location.lower().strip()

    # Direct country / "not specified" fallback
    if not location or location_lower in ("not specified", "india", "pan india", "all india"):
        return "IN"

    # Google Trends sub-region codes for Indian states
    STATE_GEO_CODES = {
        "andhra pradesh": "IN-AP",
        "arunachal pradesh": "IN-AR",
        "assam": "IN-AS",
        "bihar": "IN-BR",
        "chhattisgarh": "IN-CT",
        "goa": "IN-GA",
        "gujarat": "IN-GJ",
        "haryana": "IN-HR",
        "himachal pradesh": "IN-HP",
        "jharkhand": "IN-JH",
        "karnataka": "IN-KA",
        "kerala": "IN-KL",
        "madhya pradesh": "IN-MP",
        "maharashtra": "IN-MH",
        "manipur": "IN-MN",
        "meghalaya": "IN-ML",
        "mizoram": "IN-MZ",
        "nagaland": "IN-NL",
        "odisha": "IN-OR",
        "punjab": "IN-PB",
        "rajasthan": "IN-RJ",
        "sikkim": "IN-SK",
        "tamil nadu": "IN-TN",
        "telangana": "IN-TG",
        "tripura": "IN-TR",
        "uttar pradesh": "IN-UP",
        "uttarakhand": "IN-UT",
        "west bengal": "IN-WB",
        "delhi": "IN-DL",
        "jammu and kashmir": "IN-JK",
        "ladakh": "IN-LA",
        "chandigarh": "IN-CH",
        "puducherry": "IN-PY",
    }

    # City to state mapping (common Indian cities)
    CITY_TO_STATE = {
        "mumbai": "maharashtra",
        "pune": "maharashtra",
        "nagpur": "maharashtra",
        "nashik": "maharashtra",
        "bangalore": "karnataka",
        "bengaluru": "karnataka",
        "mysuru": "karnataka",
        "mysore": "karnataka",
        "hyderabad": "telangana",
        "chennai": "tamil nadu",
        "coimbatore": "tamil nadu",
        "kolkata": "west bengal",
        "ahmedabad": "gujarat",
        "surat": "gujarat",
        "vadodara": "gujarat",
        "jaipur": "rajasthan",
        "jodhpur": "rajasthan",
        "lucknow": "uttar pradesh",
        "kanpur": "uttar pradesh",
        "agra": "uttar pradesh",
        "varanasi": "uttar pradesh",
        "patna": "bihar",
        "bhopal": "madhya pradesh",
        "indore": "madhya pradesh",
        "bhubaneswar": "odisha",
        "kochi": "kerala",
        "thiruvananthapuram": "kerala",
        "guwahati": "assam",
        "chandigarh": "chandigarh",
        "new delhi": "delhi",
        "noida": "uttar pradesh",
        "gurgaon": "haryana",
        "gurugram": "haryana",
        "faridabad": "haryana",
        "amritsar": "punjab",
        "ludhiana": "punjab",
        "raipur": "chhattisgarh",
        "ranchi": "jharkhand",
        "vijayawada": "andhra pradesh",
        "visakhapatnam": "andhra pradesh",
    }

    # Try direct state match first
    if location_lower in STATE_GEO_CODES:
        return STATE_GEO_CODES[location_lower]

    # Try city → state mapping
    if location_lower in CITY_TO_STATE:
        state = CITY_TO_STATE[location_lower]
        return STATE_GEO_CODES.get(state, "IN")

    # Partial match for state names
    for state_name, geo_code in STATE_GEO_CODES.items():
        if state_name in location_lower or location_lower in state_name:
            return geo_code

    # Fallback: use all-India
    return "IN"


# ------------------------------------------------------------------
# Public API
# ------------------------------------------------------------------

@tool
def search_google_trends(keyword: str, location: str = "") -> dict:
    """
    Fetch real Google Trends data for a keyword.

    Returns relative search interest (scale 0-100, NOT absolute search counts).
    Uses an on-disk TTL cache.  On failure, returns a structured error record.
    Never returns fabricated data.

    Parameters
    ----------
    keyword  : the search keyword (e.g., "organic vegetable delivery")
    location : optional location string (e.g., "Ahmedabad", "Gujarat")
    """
    geo = _map_location_to_geo(location)
    timeframe = "today 12-m"
    return _fetch_single_keyword_trend(keyword, geo, timeframe)


def run_trends_search(keywords: list, location: str = "") -> list:
    """
    Fetch Google Trends for multiple keywords.
    Called directly by the research node (not via the LangChain tool wrapper).

    - Limits to TRENDS_MAX_KEYWORDS (env, default 3).
    - Checks disk cache before every network request.
    - Throttles between requests using TRENDS_INTER_REQUEST_S.
    - Continues to the next keyword if one fails; partial results are preserved.
    - Never invents data.

    Returns a list of evidence records (successes and/or structured errors).
    """
    geo = _map_location_to_geo(location)
    timeframe = "today 12-m"

    keywords_to_process = [k for k in (keywords or []) if k][:TRENDS_MAX_KEYWORDS]

    if not keywords_to_process:
        return [{
            "source": "google_trends",
            "status": "error",
            "error_type": "no_keywords",
            "error": "No keywords provided for Google Trends search.",
        }]

    results = []
    for keyword in keywords_to_process:
        result = _fetch_single_keyword_trend(keyword, geo, timeframe)
        results.append(result)

    return results
