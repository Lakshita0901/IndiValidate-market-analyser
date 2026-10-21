"""
reddit_tool.py
--------------
Searches a local Kaggle Reddit dataset for posts relevant to a market idea.

Source type: historical_dataset
Dataset: Kaggle Reddit dataset (user-provided)

Expected file location:
    data/reddit/reddit_posts.csv

How to get the dataset
-----------------------
Download any of these from Kaggle (free account required):
    https://www.kaggle.com/datasets/pavellexyr/the-reddit-climate-change-dataset
    https://www.kaggle.com/datasets/reddit/reddit-comments-may-2015
    https://www.kaggle.com/datasets/unanimad/reddit-rwallstreetbets
    https://www.kaggle.com/datasets/not-just-r/reddit-posts

Or search: https://www.kaggle.com/search?q=reddit+posts

After downloading:
    1. Place any reddit posts CSV file as: data/reddit/reddit_posts.csv
    2. The tool auto-detects available columns — no manual config needed.

IMPORTANT: This is historical data. It is labeled source_type = "historical_dataset".
Do NOT describe results as live Reddit data.

Search method: Deterministic keyword matching (Phase 1).
Semantic search via embeddings will be added in the RAG stage.
"""

import os
import re
import pandas as pd
from pathlib import Path

# ------------------------------------------------------------------
# Dataset location
# The tool checks here first. If not found, returns a structured error.
# ------------------------------------------------------------------
REDDIT_DATA_DIR = Path("data/reddit")
REDDIT_CSV_NAME = "reddit_posts.csv"

# Cache the loaded dataframe in memory so we don't re-read on every call
_REDDIT_DF: pd.DataFrame | None = None
_REDDIT_COLUMNS: list[str] = []


# ------------------------------------------------------------------
# Column name normalization
# Different Kaggle Reddit datasets use different column names.
# We map known variations to our canonical internal names.
# ------------------------------------------------------------------
COLUMN_ALIASES = {
    # title of the post
    "title": ["title", "post_title", "headline"],

    # body/text of the post
    "text": ["selftext", "body", "text", "content", "post_body", "self_text"],

    # subreddit name
    "subreddit": ["subreddit", "subreddit_name", "sub", "community"],

    # upvote score
    "score": ["score", "ups", "upvotes", "vote_score"],

    # creation timestamp
    "created_at": ["created_utc", "created_at", "timestamp", "date", "post_date", "time"],

    # permalink or URL
    "url": ["permalink", "url", "link", "post_url", "full_link"],

    # post ID
    "post_id": ["id", "post_id", "name"],
}


def _find_column(df: pd.DataFrame, canonical: str) -> str | None:
    """
    Find the actual column name in df that matches a canonical field name.
    Returns the first match, or None if not found.
    """
    aliases = COLUMN_ALIASES.get(canonical, [canonical])
    df_cols_lower = {c.lower(): c for c in df.columns}
    for alias in aliases:
        if alias.lower() in df_cols_lower:
            return df_cols_lower[alias.lower()]
    return None


def _load_dataset() -> tuple[pd.DataFrame | None, str | None]:
    """
    Load the Reddit dataset CSV into a DataFrame.
    Returns (dataframe, error_message).
    If successful, error_message is None.
    If failed, dataframe is None.

    Caches the result in _REDDIT_DF so subsequent calls don't re-read disk.
    """
    global _REDDIT_DF, _REDDIT_COLUMNS

    # Return cached copy if already loaded
    if _REDDIT_DF is not None:
        return _REDDIT_DF, None

    # Check directory exists
    if not REDDIT_DATA_DIR.exists():
        return None, (
            f"Reddit dataset directory not found: {REDDIT_DATA_DIR.absolute()}. "
            f"Create it and place a Kaggle Reddit CSV as '{REDDIT_CSV_NAME}'."
        )

    # Find CSV file — use the expected name, or the first CSV found
    csv_path = REDDIT_DATA_DIR / REDDIT_CSV_NAME
    if not csv_path.exists():
        # Try finding any CSV in the directory
        csv_files = list(REDDIT_DATA_DIR.glob("*.csv"))
        if not csv_files:
            return None, (
                f"No CSV file found in {REDDIT_DATA_DIR.absolute()}. "
                f"Download a Reddit dataset from Kaggle and place it as "
                f"data/reddit/{REDDIT_CSV_NAME}. "
                "See data/reddit/README.md for download links."
            )
        csv_path = csv_files[0]
        print(f"    [Reddit] Using CSV: {csv_path.name} (expected: {REDDIT_CSV_NAME})")

    # Load the CSV
    try:
        # Use low_memory=False to prevent dtype warnings on large files
        # nrows=200000 keeps memory reasonable for large Kaggle datasets
        df = pd.read_csv(csv_path, low_memory=False, nrows=200_000)
        df.columns = [str(c).strip() for c in df.columns]

        detected = list(df.columns)
        print(f"    [Reddit] Detected columns: {detected}")
        print(f"    [Reddit] Loaded {len(df):,} rows from {csv_path.name}")

        _REDDIT_DF = df
        _REDDIT_COLUMNS = detected
        return df, None

    except Exception as e:
        return None, f"Failed to load Reddit CSV: {e}"


def _build_search_text(df: pd.DataFrame) -> pd.Series:
    """
    Combine title and text body into a single searchable string per row.
    Uses whichever columns are available.
    """
    title_col = _find_column(df, "title")
    text_col = _find_column(df, "text")

    parts = []
    if title_col:
        parts.append(df[title_col].fillna("").astype(str))
    if text_col:
        parts.append(df[text_col].fillna("").astype(str))

    if not parts:
        # Fallback: use all string columns
        str_cols = df.select_dtypes(include="object").columns
        for col in str_cols[:3]:
            parts.append(df[col].fillna("").astype(str))

    if not parts:
        return pd.Series([""] * len(df))

    combined = parts[0]
    for part in parts[1:]:
        combined = combined + " " + part

    return combined.str.lower()


def _keyword_match_score(text: str, keywords: list[str]) -> int:
    """
    Count how many keywords appear in the text.
    Returns the count (higher = more relevant).
    Uses whole-word matching where practical.
    """
    count = 0
    text_lower = text.lower()
    for kw in keywords:
        kw_clean = kw.strip().lower()
        if not kw_clean:
            continue
        # Use word-boundary aware matching for short keywords to prevent substring false positives
        if len(kw_clean) <= 4:
            pattern = r"\b" + re.escape(kw_clean) + r"\b"
            if re.search(pattern, text_lower):
                count += 1
        else:
            pattern = re.escape(kw_clean)
            if re.search(pattern, text_lower):
                count += 1
    return count


def _normalize_record(df: pd.DataFrame, row: pd.Series) -> dict:
    """
    Extract and normalize a single DataFrame row into our standard evidence format.
    Only includes fields that actually exist in the dataset.
    """
    record = {
        "source": "reddit",
        "source_type": "historical_dataset",
        "dataset": "Kaggle Reddit dataset",
    }

    title_col = _find_column(df, "title")
    text_col = _find_column(df, "text")
    subreddit_col = _find_column(df, "subreddit")
    score_col = _find_column(df, "score")
    created_col = _find_column(df, "created_at")
    url_col = _find_column(df, "url")

    if title_col:
        record["title"] = str(row.get(title_col, ""))[:300]

    if text_col:
        body = str(row.get(text_col, "")).strip()
        # Truncate long posts — we only need enough for evidence context
        record["text"] = body[:400] + "..." if len(body) > 400 else body

    if subreddit_col:
        record["subreddit"] = str(row.get(subreddit_col, ""))

    if score_col:
        try:
            record["score"] = int(float(row.get(score_col, 0)))
        except (ValueError, TypeError):
            record["score"] = 0

    if created_col:
        record["created_at"] = str(row.get(created_col, ""))

    if url_col:
        url_val = str(row.get(url_col, ""))
        # Some datasets store only the permalink path, not the full URL
        if url_val and not url_val.startswith("http"):
            url_val = f"https://reddit.com{url_val}"
        record["url"] = url_val

    return record


def run_reddit_search(query: str, keywords: list | None = None, top_n: int = 8) -> list:
    """
    Search the local Kaggle Reddit dataset for posts matching the given keywords.

    Parameters
    ----------
    query : str
        The main search query (usually the business idea or a concise description).
    keywords : list | None
        List of keyword strings extracted by the idea analysis stage.
        If provided, these are used for matching. Otherwise, query is tokenized.
    top_n : int
        Maximum number of results to return.

    Returns
    -------
    list of evidence record dicts, or a list with a single error dict if unavailable.
    """
    # ------------------------------------------------------------------
    # Step 1: Load dataset
    # ------------------------------------------------------------------
    df, error = _load_dataset()
    if error:
        return [{
            "source": "reddit",
            "source_type": "historical_dataset",
            "status": "error",
            "error": error,
            "how_to_fix": (
                "Download a Reddit posts dataset from Kaggle. "
                "Example: https://www.kaggle.com/search?q=reddit+posts "
                "Place the CSV at: data/reddit/reddit_posts.csv"
            )
        }]

    # ------------------------------------------------------------------
    # Step 2: Build keyword list for matching
    # ------------------------------------------------------------------
    search_terms: list[str] = []
    if keywords:
        for kw in keywords:
            if kw and str(kw).strip():
                clean_kw = str(kw).strip().lower()
                if clean_kw not in search_terms:
                    search_terms.append(clean_kw)
                # If kw is a multi-word phrase, also include meaningful constituent terms
                words = re.findall(r"\b[a-zA-Z0-9_-]{3,}\b", clean_kw)
                stopwords = {
                    "and", "the", "for", "with", "from", "that", "this", "into",
                    "your", "about", "have", "more", "service", "booking"
                }
                for w in words:
                    w_lower = w.lower()
                    if w_lower not in stopwords and w_lower not in search_terms:
                        search_terms.append(w_lower)
    else:
        # Fallback: tokenize the query string
        search_terms = [w for w in query.lower().split() if len(w) > 3]

    if not search_terms:
        return [{
            "source": "reddit",
            "source_type": "historical_dataset",
            "status": "error",
            "error": "No search terms available. Provide keywords or a non-empty query."
        }]

    # ------------------------------------------------------------------
    # Step 3: Build searchable text column and score each row
    # ------------------------------------------------------------------
    search_text = _build_search_text(df)

    # Score each row by counting keyword matches
    scores = search_text.apply(lambda text: _keyword_match_score(text, search_terms))

    # Only keep rows with at least 1 match
    matched_mask = scores > 0
    raw_matches_count = int(matched_mask.sum())

    if raw_matches_count == 0:
        sub_col = _find_column(df, "subreddit")
        subs_list = []
        if sub_col and sub_col in df.columns:
            subs_list = [str(s) for s in df[sub_col].dropna().value_counts().head(6).index.tolist()]
        subs_str = f"r/{', r/'.join(subs_list)}" if subs_list else "unspecified communities"

        return [{
            "source": "reddit",
            "source_type": "historical_dataset",
            "status": "no_results",
            "raw_matches_count": 0,
            "total_rows_searched": len(df),
            "subreddits_in_archive": subs_list,
            "error": (
                f"No posts found matching keywords: {search_terms[:5]} (0 raw matches across {len(df):,} archive rows). "
                f"Archive covers: {subs_str}. Topic terms may not be present in this historical dataset."
            ),
            "keywords_searched": search_terms[:8],
            "diagnostic": {
                "raw_matches_count": 0,
                "total_rows_searched": len(df),
                "subreddits_in_archive": subs_list,
                "filter_rejection_count": 0,
            }
        }]

    # Sort by match score descending, then by upvote score if available
    matched_df = df[matched_mask].copy()
    matched_df["_match_score"] = scores[matched_mask]

    score_col = _find_column(df, "score")
    if score_col:
        try:
            matched_df["_upvote_score"] = pd.to_numeric(matched_df[score_col], errors="coerce").fillna(0)
            matched_df = matched_df.sort_values(
                ["_match_score", "_upvote_score"], ascending=[False, False]
            )
        except Exception:
            matched_df = matched_df.sort_values("_match_score", ascending=False)
    else:
        matched_df = matched_df.sort_values("_match_score", ascending=False)

    # Take top_n results
    top_rows = matched_df.head(top_n)

    # ------------------------------------------------------------------
    # Step 4: Normalize and return
    # ------------------------------------------------------------------
    results = []
    for _, row in top_rows.iterrows():
        record = _normalize_record(df, row)
        record["relevance_query"] = query
        record["raw_matches_count"] = raw_matches_count
        record["keywords_matched"] = [
            kw for kw in search_terms
            if kw in (record.get("title", "") + " " + record.get("text", "")).lower()
        ]
        results.append(record)

    return results
