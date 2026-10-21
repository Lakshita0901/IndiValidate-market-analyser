# Reddit Dataset Directory

This directory holds the local Kaggle Reddit dataset used for evidence search.

## Required file

```
data/reddit/reddit_posts.csv
```

## How to download

1. Create a free Kaggle account at https://www.kaggle.com
2. Download **any** of these Reddit post datasets:

| Dataset | URL | Notes |
|---------|-----|-------|
| Reddit Posts (general) | https://www.kaggle.com/datasets/not-just-r/reddit-posts | Good general coverage |
| Top Reddit Posts | https://www.kaggle.com/datasets/tusharsharma/top-reddit-posts-and-comments | Data science subreddits |
| Reddit dataset Oct 2021 | https://www.kaggle.com/datasets/pavellex/reddit-dataset | Large general dataset |
| Reddit Climate Change | https://www.kaggle.com/datasets/pavellexyr/the-reddit-climate-change-dataset | Domain-specific |

Or search for more: https://www.kaggle.com/search?q=reddit+posts

3. After downloading, place the main CSV file here as:
   ```
   data/reddit/reddit_posts.csv
   ```

## Column detection

The tool auto-detects available columns. It works with any dataset that has:
- A title column (`title`, `post_title`, etc.)
- A body column (`selftext`, `body`, `text`, etc.)
- A subreddit column (`subreddit`, `sub`, etc.)

You do NOT need to rename columns manually.

## Search method (Phase 1)

The tool uses **keyword matching** (not embeddings).
It searches the combined title + body text for the keywords extracted by the idea analysis stage.
Posts are ranked by number of keyword matches, then by upvote score.

Semantic/embedding-based search will be added in the RAG stage.

## Important note

This is **historical data**. Evidence records are labeled:
```
source_type = "historical_dataset"
```

They are NOT live Reddit posts.
