from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable
from urllib.parse import urljoin

from letterboxd_recs.config import Config
from letterboxd_recs.db import repo
from letterboxd_recs.db.conn import ensure_db
from letterboxd_recs.ingest.letterboxd.client import LetterboxdClient
from letterboxd_recs.ingest.letterboxd.browser import fetch_html as browser_fetch
from letterboxd_recs.ingest.letterboxd.parse import (
    is_challenge_page,
    merge_items,
    parse_diary,
    parse_films_list,
    parse_likes_list,
    parse_next_page,
    parse_profile,
    parse_watchlist,
)
from letterboxd_recs.util.logging import get_logger
from letterboxd_recs.util.ratelimit import sleep_seconds

LOG = get_logger(__name__)
BASE_URL = "https://letterboxd.com"


@dataclass(frozen=True)
class IngestResult:
    username: str
    films_seen: int
    likes: int
    watchlist: int


def ingest_user(
    username: str,
    cfg: Config,
    refresh: bool = False,
    include_diary: bool = True,
    include_films: bool = True,
    include_likes: bool = True,
    include_watchlist: bool = True,
) -> IngestResult:
    ensure_db(cfg.database_path)
    cache_dir = Path(cfg.app.cache_dir) / "letterboxd" / username
    client = LetterboxdClient(cfg.app.user_agent, cfg.scrape, cache_dir)

    profile_url = _user_url(username)
    profile_html = _fetch_page(
        client,
        profile_url,
        cache_key=f"profile_{username}",
        refresh=refresh,
    )
    if is_challenge_page(profile_html):
        raise RuntimeError("Blocked by Cloudflare challenge on profile page.")
    profile = parse_profile(username, profile_html)

    with repo.connect(cfg.database_path) as conn:
        user_id = repo.upsert_user(conn, profile)
        items = []

        if include_diary:
            items.extend(_collect_diary(username, client, refresh))
        if include_films:
            items.extend(_collect_films(username, client, refresh))
        if include_likes:
            items.extend(_collect_likes(username, client, refresh))
        if include_watchlist:
            items.extend(_collect_watchlist(username, client, refresh))

        merged = merge_items(items)
        repo.upsert_interactions(conn, user_id, merged.values())

    return IngestResult(
        username=username,
        films_seen=sum(1 for i in merged.values() if i.watched),
        likes=sum(1 for i in merged.values() if i.liked),
        watchlist=sum(1 for i in merged.values() if i.watchlist),
    )


def _collect_diary(username: str, client: LetterboxdClient, refresh: bool) -> list:
    url = _user_url(username, "films/diary/")
    return _collect_paginated(url, client, refresh, parse_diary)


def _collect_films(username: str, client: LetterboxdClient, refresh: bool) -> list:
    url = _user_url(username, "films/by/date/")
    max_pages = 1 if refresh else client.scrape.max_pages
    return _collect_paginated(
        url,
        client,
        refresh,
        parse_films_list,
        max_pages=max_pages,
        browser_first=client.scrape.use_browser and not refresh,
    )


def _collect_likes(username: str, client: LetterboxdClient, refresh: bool) -> list:
    url = _user_url(username, "likes/films/")
    return _collect_paginated(url, client, refresh, parse_likes_list)


def _collect_watchlist(username: str, client: LetterboxdClient, refresh: bool) -> list:
    url = _user_url(username, "watchlist/")
    max_pages = 1 if refresh else client.scrape.max_pages
    return _collect_paginated(
        url,
        client,
        refresh,
        parse_watchlist,
        max_pages=max_pages,
        browser_first=client.scrape.use_browser and not refresh,
    )


def _collect_paginated(
    url: str,
    client: LetterboxdClient,
    refresh: bool,
    parser,
    max_pages: int | None = None,
    browser_first: bool = False,
) -> list:
    items = []
    page_url = url
    page = 1
    while page_url:
        if max_pages is not None and page > max_pages:
            LOG.info("Reached max_pages=%s for %s", max_pages, url)
            break
        LOG.info("Scrape page %s", page_url)
        cache_key = client.cache_key(page_url)
        html = _fetch_page(
            client,
            page_url,
            cache_key=cache_key,
            refresh=refresh,
        )
        if is_challenge_page(html):
            raise RuntimeError("Blocked by Cloudflare challenge while scraping.")
        items.extend(parser(html))
        next_rel = parse_next_page(html)
        page_url = urljoin(BASE_URL, next_rel) if next_rel else None
        page += 1
        sleep_seconds(client.scrape.rate_limit_seconds)
    return items


def _user_url(username: str, path: str | None = None) -> str:
    if not path:
        return f"{BASE_URL}/{username}/"
    return f"{BASE_URL}/{username}/{path}"


def _fetch_page(
    client: LetterboxdClient,
    url: str,
    cache_key: str,
    refresh: bool,
    browser_first: bool = False,
) -> str:
    if client.scrape.use_browser:
        html = browser_fetch(url, user_agent=client.session.headers.get("User-Agent", "")).content
        client.write_cache(cache_key, html)
        return html

    try:
        result = client.fetch_html(url, cache_key=cache_key, refresh=refresh)
        html = result.content
    except RuntimeError:
        if not client.scrape.use_browser:
            raise
        html = browser_fetch(url, user_agent=client.session.headers.get("User-Agent", "")).content
        client.write_cache(cache_key, html)

    if is_challenge_page(html) and client.scrape.use_browser:
        html = browser_fetch(url, user_agent=client.session.headers.get("User-Agent", "")).content
        client.write_cache(cache_key, html)

    return html
