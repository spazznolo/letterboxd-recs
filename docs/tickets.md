# Project Tickets

## Sprint 0 — Repo + Foundations
- [x] T0.1: Initialize repo structure and README (owner: core)
  - Define goals, CLI commands, and data sources.
- [x] T0.2: Add config system and example config
  - Include region, rate limits, graph depth/decay, weights.
- [x] T0.3: Add SQLite schema + connection helpers
  - Ensure idempotent schema creation.
- [x] T0.4: Add CLI scaffold (ingest/refresh/recommend/status)

## Sprint 1 — Letterboxd Ingest (User)
- [x] T1.1: Implement HTTP client with rate-limit + retry + cache
  - Cache per user, TTL-based.
- [x] T1.2: Scrape profile basics (username, display name)
- [x] T1.3: Scrape diary/films pages for watched + ratings
- [x] T1.4: Scrape likes
- [x] T1.5: Scrape watchlist
- [x] T1.6: Persist all user interactions into SQLite

## Sprint 2 — Social Graph Ingest
- [x] T2.1: Scrape followees list (pagination)
- [x] T2.2: Build BFS traversal to depth D with decay
- [x] T2.3: Ingest followees’ interactions (watched/liked/watchlist)
- [x] T2.4: Store graph edges in SQLite
- [x] T2.5: Add `--max-depth` and `--refresh` overrides to CLI

## Sprint 3 — Film Metadata + Availability
- [ ] T3.1: Scrape film metadata (genres, directors, cast, year)
- [ ] T3.2: Normalize and store metadata in `film_features`
- [ ] T3.3: Scrape Letterboxd availability (region CA)
- [ ] T3.4: Store availability in `availability` table

## Sprint 4 — Recommender v1 (Content + Social)
- [ ] T4.1: Build user profile vector from ratings/likes
- [ ] T4.2: Implement content-based scoring
- [ ] T4.3: Implement social-graph scoring (decayed aggregation)
- [ ] T4.4: Blend scores and persist recommendations
- [ ] T4.5: CLI output: sorted by score/provider, min-score filter

## Sprint 5 — Quality + UX
- [ ] T5.1: Add explainability (why recommended)
- [ ] T5.2: Add diversity/novelty penalty (optional)
- [ ] T5.3: Add export to CSV/JSON
- [ ] T5.4: Add status reporting (counts, last fetched, cache stats)
- [ ] T5.5: Add docs: tuning and architecture updates

## Sprint 6 — Hardening
- [ ] T6.1: Add tests for parsers and scoring
- [ ] T6.2: Add failure-safe retries + backoff logging
- [ ] T6.3: Add ToS/ethical scraping notes + opt-out
