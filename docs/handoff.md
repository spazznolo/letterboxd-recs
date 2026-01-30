# Handoff Notes

Use this log to capture context, decisions, and next-step instructions as tickets are completed.

## Template (copy for each completed ticket)
- Ticket: T?.?
- Date:
- Summary:
- Files touched:
- Decisions:
- Gotchas:
- Next steps:

---

## Completed
- Ticket: T0.1
  Date: 2026-01-22
  Summary: Initialized repo structure and README with project goals, CLI overview, and data sources.
  Files touched: README.md
  Decisions: Kept README focused on scope, CLI, and ToS note; avoided deep usage until ingest exists.
  Gotchas: None.
  Next steps: Begin Sprint 1 ingest modules.

- Ticket: T0.2
  Date: 2026-01-22
  Summary: Added config loader and example config for region, rate limits, graph depth/decay, and weights.
  Files touched: config.example.toml, src/letterboxd_recs/config.py
  Decisions: TOML config with dataclasses and required keys; default config path is `config.toml`.
  Gotchas: `config.toml` must exist or CLI raises FileNotFoundError.
  Next steps: Ensure CLI commands read config and pass through to ingest modules.

- Ticket: T0.3
  Date: 2026-01-22
  Summary: Added SQLite schema and connection helper to create schema idempotently.
  Files touched: src/letterboxd_recs/db/schema.sql, src/letterboxd_recs/db/conn.py
  Decisions: Simple schema with users/films/interactions/features/availability/graph_edges/recommendations.
  Gotchas: None; uses `executescript` each run, so schema file should remain idempotent.
  Next steps: Add data access helpers as ingest work begins.

- Ticket: T0.4
  Date: 2026-01-22
  Summary: Added CLI scaffold for ingest/refresh/recommend/status with placeholder output.
  Files touched: src/letterboxd_recs/cli.py
  Decisions: Typer + Rich; CLI ensures DB exists before running commands.
  Gotchas: Commands are scaffolds; no real ingest logic yet.
  Next steps: Implement ingest pipeline and wire into CLI.

- Ticket: T1.1
  Date: 2026-01-22
  Summary: Implemented Letterboxd HTTP client with rate limiting, retries, and file cache.
  Files touched: src/letterboxd_recs/ingest/letterboxd/client.py, src/letterboxd_recs/util/cache.py
  Decisions: Cache keyed by URL; TTL-based freshness in `FileCache`.
  Gotchas: Cache key replaces URL slashes; collisions possible if URLs differ only by scheme.
  Next steps: If needed, improve cache keys with hashing.

- Ticket: T1.2
  Date: 2026-01-22
  Summary: Added profile parser to extract display name from profile page.
  Files touched: src/letterboxd_recs/ingest/letterboxd/parse.py
  Decisions: Use header selectors `h1.title-2` / `h1.profile-name` as fallbacks.
  Gotchas: If Letterboxd changes profile header markup, display name may be missing.
  Next steps: Validate selectors against real pages when scraping.

- Ticket: T1.3
  Date: 2026-01-22
  Summary: Implemented diary + films page parsing for watched and ratings, with pagination.
  Files touched: src/letterboxd_recs/ingest/letterboxd/parse.py, src/letterboxd_recs/ingest/letterboxd/ingest.py
  Decisions: Diary rows parsed from `tr.diary-entry-row`; films list parsed from `div.film-poster`.
  Gotchas: Rating extraction is heuristic and may miss non-star formats.
  Next steps: Adjust selectors based on real HTML.

- Ticket: T1.4
  Date: 2026-01-22
  Summary: Added likes list parsing and ingestion.
  Files touched: src/letterboxd_recs/ingest/letterboxd/parse.py, src/letterboxd_recs/ingest/letterboxd/ingest.py
  Decisions: Likes derived from poster list and forced `liked=True`.
  Gotchas: If likes page markup differs from poster list, items may be missed.
  Next steps: Validate against sample likes page.

- Ticket: T1.5
  Date: 2026-01-22
  Summary: Added watchlist list parsing and ingestion.
  Files touched: src/letterboxd_recs/ingest/letterboxd/parse.py, src/letterboxd_recs/ingest/letterboxd/ingest.py
  Decisions: Watchlist derived from poster list and forced `watchlist=True`.
  Gotchas: Items in watchlist aren't marked watched; merged items will OR flags.
  Next steps: Validate selectors against real watchlist pages.

- Ticket: T1.6
  Date: 2026-01-22
  Summary: Added SQLite upsert helpers and ingestion flow to persist interactions.
  Files touched: src/letterboxd_recs/db/repo.py, src/letterboxd_recs/ingest/letterboxd/ingest.py, src/letterboxd_recs/cli.py, src/letterboxd_recs/ingest/__init__.py, src/letterboxd_recs/ingest/letterboxd/__init__.py
  Decisions: Upserts preserve existing ratings and OR boolean flags; watch_date uses first non-null.
  Gotchas: Merge logic is heuristic; prefer validation with sample data.
  Next steps: Add tests for parsing + persistence.

- Ticket: N/A (post-sprint maintenance)
  Date: 2026-01-22
  Summary: Added parser tests with fixtures and Cloudflare challenge detection.
  Files touched: tests/test_parsers.py, tests/fixtures/*.html, src/letterboxd_recs/ingest/letterboxd/parse.py, src/letterboxd_recs/ingest/letterboxd/ingest.py, pyproject.toml
  Decisions: Treat Cloudflare challenge pages as hard errors in ingest; tests validate challenge detection.
  Gotchas: Current fixtures are challenge pages for list endpoints; real parsing still needs authenticated/non-blocked HTML.
  Next steps: Capture valid HTML fixtures (logged-in or via export) to test real parsing paths.

- Ticket: N/A (browser scraping + fixtures)
  Date: 2026-01-22
  Summary: Added Playwright browser fetch fallback, optional browser-first refresh, and updated fixtures using Playwright; added browser fetch test (opt-in).
  Files touched: src/letterboxd_recs/ingest/letterboxd/browser.py, src/letterboxd_recs/ingest/letterboxd/ingest.py, src/letterboxd_recs/ingest/letterboxd/client.py, src/letterboxd_recs/ingest/letterboxd/parse.py, tests/test_parsers.py, tests/test_browser_fetch.py, tests/fixtures/*.html, config.example.toml, config.toml, src/letterboxd_recs/db/repo.py
  Decisions: Use Playwright for Cloudflare/403 fallback and for refresh runs (browser-first when refresh=True); cache browser HTML.
  Gotchas: Full ingest is slow due to many pages; watchlist pagination dominates runtime.
  Next steps: Consider a `--max-pages` option or incremental sync to speed dev runs.

- Ticket: T2.1–T2.5
  Date: 2026-01-22
  Summary: Implemented follow-graph ingest with pagination, BFS traversal, graph edge storage, and CLI options; added parser tests.
  Files touched: src/letterboxd_recs/graph/ingest.py, src/letterboxd_recs/ingest/letterboxd/social.py, src/letterboxd_recs/db/repo.py, src/letterboxd_recs/cli.py, tests/test_graph.py
  Decisions: Graph ingest uses BFS up to `max_depth`; optionally ingests followee interactions via existing ingest pipeline.
  Gotchas: Graph ingest can be slow and heavy when ingesting interactions for many followees.
  Next steps: Consider adding limits or batching controls for graph ingestion.
