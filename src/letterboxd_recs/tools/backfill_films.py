from __future__ import annotations

import argparse
import sqlite3
import time
from pathlib import Path

from letterboxd_recs.config import ScrapeConfig
from letterboxd_recs.db.conn import ensure_db
from letterboxd_recs.db import repo
from letterboxd_recs.ingest.letterboxd.client import LetterboxdClient
from letterboxd_recs.ingest.letterboxd.browser import fetch_html as browser_fetch
from letterboxd_recs.ingest.letterboxd.parse import (
    FilmItem,
    is_challenge_page,
    merge_items,
    parse_diary,
    parse_film_page,
    parse_films_list,
    parse_genres_page,
    parse_likes_list,
    parse_watchlist,
)
from letterboxd_recs.util.logging import get_logger

LOG = get_logger(__name__)
BASE_URL = "https://letterboxd.com"


def _parser_for_cache_name(name: str):
    if "_films_diary_" in name:
        return parse_diary
    if "_likes_films_" in name:
        return parse_likes_list
    if "_watchlist_" in name:
        return parse_watchlist
    if "_films_" in name:
        return parse_films_list
    return None


def _load_cached_items(cache_dir: Path) -> dict[str, FilmItem]:
    items: list[FilmItem] = []
    for path in sorted(cache_dir.glob("*.html")):
        parser = _parser_for_cache_name(path.name)
        if not parser:
            continue
        html = path.read_text(encoding="utf-8")
        if is_challenge_page(html):
            LOG.warning("Skipping challenge page: %s", path.name)
            continue
        items.extend(parser(html))
    return merge_items(items)


def _load_missing_genre_items(conn: sqlite3.Connection) -> dict[str, FilmItem]:
    rows = conn.execute(
        """
        SELECT letterboxd_id
        FROM films
        WHERE genres IS NULL OR TRIM(genres) = ''
        """
    ).fetchall()
    items: dict[str, FilmItem] = {}
    for row in rows:
        slug = row[0]
        if not slug:
            continue
        items[slug] = FilmItem(
            slug=slug,
            title=None,
            year=None,
            rating=None,
            liked=False,
            watched=False,
            watch_date=None,
            watchlist=False,
        )
    return items


def _fetch_film_metadata(
    slug: str, client: LetterboxdClient, refresh: bool
) -> tuple[str | None, int | None, list[str]]:
    url = f"{BASE_URL}/film/{slug}/"
    cache_key = client.cache_key(url)
    try:
        if refresh and client.scrape.use_browser:
            content = browser_fetch(
                url, user_agent=client.session.headers.get("User-Agent", ""), timeout_ms=45000
            ).content
            client.write_cache(cache_key, content)
        else:
            result = client.fetch_html(url, cache_key=cache_key, refresh=refresh)
            content = result.content
    except RuntimeError as exc:
        if not client.scrape.use_browser:
            LOG.warning("Failed to fetch %s: %s", slug, exc)
            return None, None, []
        LOG.info("Browser fallback for film %s", slug)
        try:
            content = browser_fetch(
                url, user_agent=client.session.headers.get("User-Agent", ""), timeout_ms=45000
            ).content
            client.write_cache(cache_key, content)
        except Exception as browser_exc:  # noqa: BLE001
            LOG.warning("Browser fetch failed for %s: %s", slug, browser_exc)
            return None, None, []

    if is_challenge_page(content):
        LOG.warning("Challenge page for film %s", slug)
        return None, None, []
    title, year, genres = parse_film_page(content)

    genres_url = f"{BASE_URL}/film/{slug}/genres/"
    genres_key = client.cache_key(genres_url)
    try:
        if refresh and client.scrape.use_browser:
            genres_html = browser_fetch(
                genres_url,
                user_agent=client.session.headers.get("User-Agent", ""),
                timeout_ms=45000,
            ).content
            client.write_cache(genres_key, genres_html)
        else:
            genres_result = client.fetch_html(genres_url, cache_key=genres_key, refresh=refresh)
            genres_html = genres_result.content
    except RuntimeError as exc:
        if client.scrape.use_browser:
            try:
                genres_html = browser_fetch(
                    genres_url,
                    user_agent=client.session.headers.get("User-Agent", ""),
                    timeout_ms=45000,
                ).content
                client.write_cache(genres_key, genres_html)
            except Exception as browser_exc:  # noqa: BLE001
                LOG.warning("Browser fetch failed for genres %s: %s", slug, browser_exc)
                return title, year, genres
        else:
            LOG.warning("Failed to fetch genres %s: %s", slug, exc)
            return title, year, genres

    if not is_challenge_page(genres_html):
        genres = parse_genres_page(genres_html)

    return title, year, genres


def _upsert_film_metadata(
    conn,
    items: dict[str, FilmItem],
    client: LetterboxdClient | None,
    refresh: bool,
) -> int:
    updated = 0
    for item in items.values():
        title = item.title
        year = item.year
        genres: list[str] = []
        if client is not None:
            meta_title, meta_year, meta_genres = _fetch_film_metadata(item.slug, client, refresh)
            title = title or meta_title
            year = year or meta_year
            genres = meta_genres
        if title is None and year is None and not genres:
            continue
        genres_text = ", ".join(genres) if genres else None
        _retry_upsert(conn, item.slug, title, year, genres_text)
        updated += 1
        if updated % 25 == 0:
            conn.commit()
    return updated


def _retry_upsert(
    conn: sqlite3.Connection,
    slug: str,
    title: str | None,
    year: int | None,
    genres_text: str | None,
) -> None:
    for attempt in range(1, 6):
        try:
            repo.upsert_film_metadata(conn, slug, title, year, genres_text)
            return
        except sqlite3.OperationalError as exc:
            if "locked" not in str(exc).lower():
                raise
            wait = 0.5 * attempt
            LOG.warning("DB locked (attempt %s). Retrying in %.1fs", attempt, wait)
            time.sleep(wait)
    repo.upsert_film_metadata(conn, slug, title, year, genres_text)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Backfill film titles/years from cached pages.")
    parser.add_argument("username", help="Letterboxd username used for cache directory.")
    parser.add_argument(
        "--config",
        type=Path,
        default=None,
        help="Path to config.toml (defaults to ./config.toml).",
    )
    parser.add_argument(
        "--db",
        type=Path,
        default=None,
        help="Path to SQLite database (overrides config.toml).",
    )
    parser.add_argument(
        "--cache-dir",
        type=Path,
        default=None,
        help="Base cache dir (overrides config.toml).",
    )
    parser.add_argument(
        "--fetch-film-pages",
        action="store_true",
        help="Fetch film pages to populate genres and missing title/year.",
    )
    parser.add_argument(
        "--missing-genres",
        action="store_true",
        help="Only refresh films missing genres in the database.",
    )
    parser.add_argument(
        "--refresh",
        action="store_true",
        help="Force refresh when fetching film pages.",
    )
    args = parser.parse_args(argv)

    db_path = args.db
    cache_root = args.cache_dir
    scrape = None
    user_agent = None
    if db_path is None or cache_root is None:
        from letterboxd_recs.config import load_config

        cfg = load_config(args.config)
        db_path = Path(cfg.database_path)
        cache_root = Path(cfg.app.cache_dir)
        scrape = cfg.scrape
        user_agent = cfg.app.user_agent

    ensure_db(str(db_path))
    cache_dir = cache_root / "letterboxd" / args.username
    if not cache_dir.exists():
        raise FileNotFoundError(f"Cache dir not found: {cache_dir}")

    with repo.connect(str(db_path)) as conn:
        if args.missing_genres:
            items = _load_missing_genre_items(conn)
            LOG.info("Found %s films missing genres", len(items))
        else:
            LOG.info("Loading cached HTML from %s", cache_dir)
            items = _load_cached_items(cache_dir)
            LOG.info("Parsed %s unique films from cache", len(items))

    client = None
    if args.missing_genres and not args.fetch_film_pages:
        LOG.info("Enabling --fetch-film-pages because --missing-genres was set.")
        args.fetch_film_pages = True

    if args.fetch_film_pages:
        if scrape is None or user_agent is None:
            scrape = ScrapeConfig(
                rate_limit_seconds=1.0, max_retries=3, cache_ttl_days=7, use_browser=False
            )
            user_agent = "letterboxd-recs/0.1"
        client = LetterboxdClient(user_agent, scrape, cache_dir)

    with repo.connect(str(db_path)) as conn:
        updated = _upsert_film_metadata(conn, items, client, args.refresh)
        conn.commit()

    LOG.info("Updated %s film records", updated)


if __name__ == "__main__":
    main()
