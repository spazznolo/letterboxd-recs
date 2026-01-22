# Architecture

## Modules
- ingest/letterboxd: scraping + parsing of profile, films, ratings, watchlist, and follow graph
- graph: BFS traversal of follow graph with decayed influence weights
- features: metadata aggregation and user profile vectors
- models: content, social, and blend scorers
- availability: Letterboxd availability parsing (region CA)
- db: SQLite schema + data access
- cli: user-facing commands

## Data flow
1) Ingest user data into SQLite
2) Build user profile vectors
3) Compute social graph scores
4) Blend into final recommendations
5) Output ranked list

## Social graph signal
- Traverse follow graph to depth D
- Weight each hop with decay^hop
- Aggregate interactions (liked, rated, watched, watchlist)
