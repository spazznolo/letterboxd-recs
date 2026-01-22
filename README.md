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

## CLI (planned)
- `letterboxd-recs ingest USERNAME`
- `letterboxd-recs refresh USERNAME --availability`
- `letterboxd-recs recommend USERNAME --sort score|provider --min-score X`
- `letterboxd-recs status USERNAME`

## Notes
- Scraping can violate site ToS. Use responsibly and keep rate limits conservative.
- Availability is sourced from Letterboxd availability pages (region configurable; default CA).

## Docs
- `docs/architecture.md`
- `docs/tuning.md`
