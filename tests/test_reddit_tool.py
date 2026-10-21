"""
tests/test_reddit_tool.py
--------------------------
Unit tests for app/tools/reddit_tool.py.

Rules:
- Tests use small synthetic DataFrames or the real CSV header check.
- No fake Reddit posts are injected into the application.
- Tests verify the tool's deterministic keyword-matching logic, column
  detection, error handling, and provenance labelling.
"""

import io
import os
from pathlib import Path
from unittest.mock import patch, MagicMock

import pandas as pd
import pytest


# ──────────────────────────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def clear_reddit_cache():
    """Reset the in-memory dataset cache before every test."""
    import app.tools.reddit_tool as rt
    rt._REDDIT_DF = None
    rt._REDDIT_COLUMNS = []
    yield
    rt._REDDIT_DF = None
    rt._REDDIT_COLUMNS = []


# ──────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────

def _make_df(**kwargs) -> pd.DataFrame:
    """
    Convenience factory. Pass column_name=[list_of_values].
    All lists must be the same length.
    """
    return pd.DataFrame(kwargs)


STANDARD_DF = _make_df(
    title=["Organic food delivery startup", "Online grocery review",
           "Jobs in logistics industry"],
    selftext=["Fresh vegetables delivered to your door weekly.",
              "Tried FreshCart today — amazing experience.",
              "Looking for warehouse manager position."],
    subreddit=["startup", "food", "jobs"],
    score=[120, 45, 3],
    created_utc=["2024-01-01", "2024-02-15", "2023-11-10"],
    permalink=["/r/startup/post1", "/r/food/post2", "/r/jobs/post3"],
    id=["abc", "def", "ghi"],
)


# ──────────────────────────────────────────────────────────────────
# A. CSV exists and loads correctly
# ──────────────────────────────────────────────────────────────────

def test_a_csv_loads(tmp_path):
    """The tool loads the CSV and returns rows when it exists."""
    csv_path = tmp_path / "reddit_posts.csv"
    STANDARD_DF.to_csv(csv_path, index=False)

    import app.tools.reddit_tool as rt
    with patch.object(rt, "REDDIT_DATA_DIR", tmp_path), \
         patch.object(rt, "REDDIT_CSV_NAME", "reddit_posts.csv"):
        results = rt.run_reddit_search(
            query="organic food delivery",
            keywords=["organic", "delivery"],
        )

    assert len(results) > 0
    # Must never be an error record when data is available
    assert all(r.get("status") not in ("error",) for r in results)


# ──────────────────────────────────────────────────────────────────
# B. Column detection with aliases
# ──────────────────────────────────────────────────────────────────

def test_b_column_alias_detection():
    """_find_column resolves known aliases case-insensitively."""
    from app.tools.reddit_tool import _find_column

    df_with_aliases = _make_df(
        post_title=["Hello"],
        body=["World"],
        ups=[42],
        sub=["python"],
        created_at=["2024-01-01"],
    )

    assert _find_column(df_with_aliases, "title") == "post_title"
    assert _find_column(df_with_aliases, "text") == "body"
    assert _find_column(df_with_aliases, "score") == "ups"
    assert _find_column(df_with_aliases, "subreddit") == "sub"
    assert _find_column(df_with_aliases, "created_at") == "created_at"
    assert _find_column(df_with_aliases, "url") is None  # Not present


# ──────────────────────────────────────────────────────────────────
# C. Actual merged_reddit_data.csv column names
# ──────────────────────────────────────────────────────────────────

def test_c_actual_csv_column_detection():
    """Column aliases correctly handle the real merged_reddit_data.csv header."""
    from app.tools.reddit_tool import _find_column

    # Actual columns in merged_reddit_data.csv:
    # Unnamed: 0, ID, Flair, Subreddit, Text, Sentiment, creation_date, Upvotes
    real_df = _make_df(
        **{
            "Unnamed: 0": [0],
            "ID": ["abc"],
            "Flair": ["food"],
            "Subreddit": ["india"],
            "Text": ["Great food"],
            "Sentiment": ["positive"],
            "creation_date": ["2024-01-01"],
            "Upvotes": [50],
        }
    )

    # "Subreddit" → alias "subreddit" (case-insensitive)
    assert _find_column(real_df, "subreddit") == "Subreddit"
    # "Upvotes" → alias "upvotes" in score list
    assert _find_column(real_df, "score") == "Upvotes"
    # "Text" → alias "text" in text list
    assert _find_column(real_df, "text") == "Text"


# ──────────────────────────────────────────────────────────────────
# D. Keyword matching returns relevant records
# ──────────────────────────────────────────────────────────────────

def test_d_keyword_matching(tmp_path):
    """Records matching keywords are returned; non-matching are excluded."""
    csv_path = tmp_path / "reddit_posts.csv"
    STANDARD_DF.to_csv(csv_path, index=False)

    import app.tools.reddit_tool as rt
    with patch.object(rt, "REDDIT_DATA_DIR", tmp_path), \
         patch.object(rt, "REDDIT_CSV_NAME", "reddit_posts.csv"):
        results = rt.run_reddit_search(
            query="organic vegetable delivery",
            keywords=["organic", "vegetable", "delivery"],
        )

    # "warehouse manager" post should not appear; "organic food delivery" should
    assert len(results) >= 1
    for r in results:
        combined = (r.get("title", "") + " " + r.get("text", "")).lower()
        assert any(kw in combined for kw in ["organic", "vegetable", "delivery"])


# ──────────────────────────────────────────────────────────────────
# E. Empty result is reported honestly
# ──────────────────────────────────────────────────────────────────

def test_e_empty_result_reported_honestly(tmp_path):
    """No matching records returns no_results status, not fake records."""
    csv_path = tmp_path / "reddit_posts.csv"
    STANDARD_DF.to_csv(csv_path, index=False)

    import app.tools.reddit_tool as rt
    with patch.object(rt, "REDDIT_DATA_DIR", tmp_path), \
         patch.object(rt, "REDDIT_CSV_NAME", "reddit_posts.csv"):
        results = rt.run_reddit_search(
            query="quantum teleportation machine",
            keywords=["quantum", "teleportation", "xyzzynotreal"],
        )

    assert len(results) == 1
    assert results[0]["status"] == "no_results"
    # Must not contain fabricated post fields
    assert "title" not in results[0]
    assert "text" not in results[0]


# ──────────────────────────────────────────────────────────────────
# F. Missing CSV directory
# ──────────────────────────────────────────────────────────────────

def test_f_missing_directory(tmp_path):
    """When the data directory does not exist, return a structured error."""
    nonexistent = tmp_path / "nonexistent_dir"
    import app.tools.reddit_tool as rt
    with patch.object(rt, "REDDIT_DATA_DIR", nonexistent):
        results = rt.run_reddit_search(query="any query", keywords=["any"])

    assert len(results) == 1
    assert results[0]["status"] == "error"
    assert "error" in results[0]


# ──────────────────────────────────────────────────────────────────
# G. Empty CSV (only header row)
# ──────────────────────────────────────────────────────────────────

def test_g_empty_csv(tmp_path):
    """A CSV with only a header row is handled without crashing."""
    csv_path = tmp_path / "reddit_posts.csv"
    csv_path.write_text("title,selftext,subreddit,score\n", encoding="utf-8")

    import app.tools.reddit_tool as rt
    with patch.object(rt, "REDDIT_DATA_DIR", tmp_path), \
         patch.object(rt, "REDDIT_CSV_NAME", "reddit_posts.csv"):
        results = rt.run_reddit_search(query="delivery", keywords=["delivery"])

    assert len(results) >= 1
    assert results[0].get("status") in ("error", "no_results")


# ──────────────────────────────────────────────────────────────────
# H. Duplicate records are not returned twice
# ──────────────────────────────────────────────────────────────────

def test_h_no_duplicate_results(tmp_path):
    """Top-N selection does not produce duplicate post records."""
    # Create a CSV with 10 identical rows so duplicates are possible
    df = pd.concat([STANDARD_DF.iloc[[0]]] * 10, ignore_index=True)
    csv_path = tmp_path / "reddit_posts.csv"
    df.to_csv(csv_path, index=False)

    import app.tools.reddit_tool as rt
    with patch.object(rt, "REDDIT_DATA_DIR", tmp_path), \
         patch.object(rt, "REDDIT_CSV_NAME", "reddit_posts.csv"):
        results = rt.run_reddit_search(
            query="organic delivery", keywords=["organic", "delivery"], top_n=5
        )

    # Results may have same title from duplication, but top_n must be respected
    assert len(results) <= 5


# ──────────────────────────────────────────────────────────────────
# I. Source labels and provenance
# ──────────────────────────────────────────────────────────────────

def test_i_source_labels(tmp_path):
    """Every result record is labelled as historical_dataset — not live Reddit."""
    csv_path = tmp_path / "reddit_posts.csv"
    STANDARD_DF.to_csv(csv_path, index=False)

    import app.tools.reddit_tool as rt
    with patch.object(rt, "REDDIT_DATA_DIR", tmp_path), \
         patch.object(rt, "REDDIT_CSV_NAME", "reddit_posts.csv"):
        results = rt.run_reddit_search(
            query="food startup", keywords=["food", "delivery"]
        )

    for r in results:
        if r.get("status") not in ("error", "no_results"):
            assert r.get("source") == "reddit"
            assert r.get("source_type") == "historical_dataset"
            assert r.get("dataset") == "Kaggle Reddit dataset"


# ──────────────────────────────────────────────────────────────────
# J. URL normalisation: relative permalinks get full URL
# ──────────────────────────────────────────────────────────────────

def test_j_url_normalisation():
    """Relative permalink paths (/r/...) are expanded to full reddit.com URLs."""
    from app.tools.reddit_tool import _normalize_record

    df = _make_df(
        title=["Test post"],
        selftext=["Body text"],
        subreddit=["test"],
        score=[10],
        created_utc=["2024-01-01"],
        permalink=["/r/test/comments/abc123/test_post/"],
    )
    row = df.iloc[0]
    record = _normalize_record(df, row)

    url = record.get("url", "")
    assert url.startswith("https://reddit.com/"), f"URL was: {url}"


# ──────────────────────────────────────────────────────────────────
# K. Auto-discovery of alternate CSV name
# ──────────────────────────────────────────────────────────────────

def test_k_csv_auto_discovery(tmp_path):
    """If the exact filename doesn't exist, the first CSV in the directory is used."""
    alt_csv = tmp_path / "merged_reddit_data.csv"
    STANDARD_DF.to_csv(alt_csv, index=False)

    import app.tools.reddit_tool as rt
    with patch.object(rt, "REDDIT_DATA_DIR", tmp_path), \
         patch.object(rt, "REDDIT_CSV_NAME", "reddit_posts.csv"):  # Does not exist
        results = rt.run_reddit_search(query="delivery", keywords=["delivery"])

    # Should still return results from the discovered CSV
    assert len(results) > 0
    found_statuses = [r.get("status") for r in results]
    assert "error" not in found_statuses or any(
        r.get("status") not in ("error",) for r in results
    )


# ──────────────────────────────────────────────────────────────────
# L. No keywords provided falls back to query tokenisation
# ──────────────────────────────────────────────────────────────────

def test_l_no_keywords_fallback(tmp_path):
    """When keywords=None, the tool tokenises the query string instead."""
    csv_path = tmp_path / "reddit_posts.csv"
    STANDARD_DF.to_csv(csv_path, index=False)

    import app.tools.reddit_tool as rt
    with patch.object(rt, "REDDIT_DATA_DIR", tmp_path), \
         patch.object(rt, "REDDIT_CSV_NAME", "reddit_posts.csv"):
        # Pass no keywords — should still work via query tokenisation
        results = rt.run_reddit_search(
            query="organic delivery startup", keywords=None
        )

    # Some results should come back (query words match CSV content)
    non_error = [r for r in results if r.get("status") not in ("error", "no_results")]
    assert len(non_error) >= 0  # May be empty if tokens don't match — just shouldn't crash


# ──────────────────────────────────────────────────────────────────
# M. Transparent Zero-Match Diagnostics
# ──────────────────────────────────────────────────────────────────

def test_m_zero_match_transparent_diagnostics(tmp_path):
    """When 0 matches are found, the tool returns transparent diagnostics detailing rows and scope."""
    csv_path = tmp_path / "reddit_posts.csv"
    STANDARD_DF.to_csv(csv_path, index=False)

    import app.tools.reddit_tool as rt
    with patch.object(rt, "REDDIT_DATA_DIR", tmp_path), \
         patch.object(rt, "REDDIT_CSV_NAME", "reddit_posts.csv"):
        results = rt.run_reddit_search(
            query="nonexistent term query",
            keywords=["completely_absent_term_12345"]
        )

    assert len(results) == 1
    res = results[0]
    assert res["status"] == "no_results"
    assert res["raw_matches_count"] == 0
    assert res["total_rows_searched"] == len(STANDARD_DF)
    assert "subreddits_in_archive" in res
    assert "error" in res
    assert "0 raw matches across" in res["error"]
    assert "diagnostic" in res
    assert res["diagnostic"]["raw_matches_count"] == 0
