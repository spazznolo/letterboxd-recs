# letterboxd-recs

Personalized Letterboxd recommendations using a hybrid of content-based scoring and a decayed social-graph signal (followees → followees-of-followees).

## What it does
- Ingests a Letterboxd profile, ratings, likes, watchlist, and follow graph.
- Builds a user profile from metadata + ratings.
- Scores unseen films using content similarity and social influence.
- Exposes a CLI to ingest and recommend.

## Quickstart
```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .

cp config.example.toml config.toml
letterboxd-recs ingest <username>
letterboxd-recs recommend <username>
```

## CLI
All commands read `config.toml` in the repo root.

- `letterboxd-recs ingest USERNAME [--refresh] [--max-depth N] [--graph/--no-graph] [--graph-interactions/--no-graph-interactions] [--graph-only]`  
  Ingests the target user (profile, diary, films, likes, watchlist). If `--graph` is enabled, it also ingests the follow graph up to `max_depth`. Use `--graph-interactions` to ingest followees’ watched/liked/watchlist data (heavy). Default is **off**. Use `--graph-only` to skip scraping the user’s own diary/films and only fetch followees + graph edges.
- `letterboxd-recs recommend USERNAME [--limit N] [--min-score X]`  
  Prints social-only recommendations (followee-based) using current weights in `config.toml`.
- `letterboxd-recs similarities USERNAME [--limit N]`  
  Prints followee similarity scores with Jaccard + rating alignment components.
- `letterboxd-recs refresh USERNAME --availability`  
  Placeholder for availability refresh (not implemented yet).
- `letterboxd-recs recommend USERNAME --sort score|provider --min-score X`  
  Placeholder for recommendation output (not implemented yet).
- `letterboxd-recs status USERNAME`  
  Placeholder for status summary (not implemented yet).

### Followee film ingest
Ingest films for followees who pass thresholds (followers/watchcount):
```bash
.venv/bin/python -m letterboxd_recs.tools.ingest_followee_films spazznolo --refresh
```

Only ingest missing (no interactions yet):
```bash
.venv/bin/python -m letterboxd_recs.tools.ingest_followee_films spazznolo --refresh --only-missing
```

Run metadata backfill after followee ingest:
```bash
.venv/bin/python -m letterboxd_recs.tools.ingest_followee_films spazznolo --refresh --backfill --backfill-refresh
```

## SQL quickstart
Run from the repo root:

```bash
sqlite3 letterboxd_recs.sqlite
```

Common queries:
```sql
-- counts
SELECT COUNT(*) FROM users;
SELECT COUNT(*) FROM films;
SELECT COUNT(*) FROM interactions;

-- followees that pass thresholds
SELECT u.username, u.display_name, u.follower_count, u.following_count, u.watched_count
FROM users u
JOIN graph_edges g ON g.dst_user_id = u.id
WHERE g.src_user_id = (SELECT id FROM users WHERE username = 'spazznolo')
  AND u.follower_count >= 100
  AND u.watched_count >= 100
ORDER BY u.follower_count DESC, u.watched_count DESC;

-- user stats
SELECT username, follower_count, following_count, watched_count
FROM users
WHERE username = 'spazznolo';

-- watched vs watchlist
SELECT COUNT(*) AS watched FROM interactions WHERE watched = 1;
SELECT COUNT(*) AS watchlist_only FROM interactions WHERE watchlist = 1 AND watched = 0;

-- rating distribution
SELECT rating, COUNT(*) FROM interactions
WHERE rating IS NOT NULL
GROUP BY rating
ORDER BY rating DESC;
```

## Recommender config
Social scoring (configurable in `config.toml`):
```toml
[social]
watched_weight = 1.0
watchlist_weight = 0.5
time_weight_min = 0.25
time_weight_years = 25

[social_similarity]
jaccard_weight = 0.6
rating_weight = 0.4
rating_prior = 0.5
rating_k = 10
default_similarity = 0.5

[social_ratings]
negative_min = -1.0
negative_max = -0.1
positive_min = 0.1
positive_max = 1.0
unrated = 0.25
watchlist_multiplier = 0.5
```

Notes:
- time weight is exponential with a 25-year half-life (clamped by `time_weight_min`)
- ratings <= 2.5 are negative; ratings >= 3.0 are positive
- unrated watched films use `unrated`
- watchlist-only uses `unrated * watchlist_multiplier`

## Notes
- Scraping can violate site ToS. Use responsibly and keep rate limits conservative.
- Availability is sourced from Letterboxd availability pages (region configurable; default CA).

## Docs
- `docs/architecture.md`
- `docs/tuning.md`
