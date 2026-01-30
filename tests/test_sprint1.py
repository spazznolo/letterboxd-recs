import os

import pytest
import requests

from letterboxd_recs.db import repo
from letterboxd_recs.db.conn import ensure_db
from letterboxd_recs.ingest.letterboxd import ingest
from letterboxd_recs.ingest.letterboxd.client import LetterboxdClient
from letterboxd_recs.ingest.letterboxd.parse import FilmItem, Profile, merge_items, parse_next_page
from letterboxd_recs.util.cache import FileCache
from letterboxd_recs.config import ScrapeConfig


def test_merge_items_prefers_non_null_and_or_flags() -> None:
    first = FilmItem(
        slug="film-a",
        title="Film A",
        year=1999,
        rating=4.0,
        liked=False,
        watched=True,
        watch_date="2020-01-01",
        watchlist=False,
    )
    second = FilmItem(
        slug="film-a",
        title=None,
        year=None,
        rating=None,
        liked=True,
        watched=False,
        watch_date=None,
        watchlist=True,
    )

    merged = merge_items([first, second])["film-a"]

    assert merged.title == "Film A"
    assert merged.year == 1999
    assert merged.rating == 4.0
    assert merged.liked is True
    assert merged.watched is True
    assert merged.watch_date == "2020-01-01"
    assert merged.watchlist is True


def test_parse_next_page_variants() -> None:
    html = "<a class='next' href='/user/films/page/2/'></a>"
    assert parse_next_page(html) == "/user/films/page/2/"

    html = "<a rel='next' href='https://letterboxd.com/u/films/page/3/'></a>"
    assert parse_next_page(html) == "https://letterboxd.com/u/films/page/3/"

    assert parse_next_page("<div>No pagination</div>") is None


def test_cache_entry_freshness(tmp_path) -> None:
    cache = FileCache(tmp_path)
    entry = cache.entry("sample.txt")
    entry.write_text("hello")
    assert entry.is_fresh(1) is True

    stale_time = entry.path.stat().st_mtime - (2 * 86400)
    os.utime(entry.path, (stale_time, stale_time))
    assert entry.is_fresh(1) is False


def test_letterboxd_client_cache_hit_skips_fetch(tmp_path, monkeypatch) -> None:
    scrape = ScrapeConfig(rate_limit_seconds=0, max_retries=1, cache_ttl_days=30, use_browser=False)
    client = LetterboxdClient("letterboxd-recs/0.1", scrape, tmp_path)
    entry = client.cache.entry("profile_test.html")
    entry.write_text("cached")

    def fail_get(*_args, **_kwargs):
        raise AssertionError("network fetch should not happen on cache hit")

    monkeypatch.setattr(client.session, "get", fail_get)

    result = client.fetch_html("https://letterboxd.com/test/", cache_key="profile_test")
    assert result.from_cache is True
    assert result.content == "cached"


def test_letterboxd_client_refresh_forces_fetch(tmp_path, monkeypatch) -> None:
    scrape = ScrapeConfig(rate_limit_seconds=0, max_retries=1, cache_ttl_days=30, use_browser=False)
    client = LetterboxdClient("letterboxd-recs/0.1", scrape, tmp_path)
    entry = client.cache.entry("profile_test.html")
    entry.write_text("cached")

    class DummyResponse:
        def __init__(self, text: str) -> None:
            self.text = text

        def raise_for_status(self) -> None:
            return None

    monkeypatch.setattr(client.session, "get", lambda *_args, **_kwargs: DummyResponse("fresh"))

    result = client.fetch_html("https://letterboxd.com/test/", cache_key="profile_test", refresh=True)
    assert result.from_cache is False
    assert result.content == "fresh"
    assert entry.read_text() == "fresh"


def test_letterboxd_client_retries_then_succeeds(tmp_path, monkeypatch) -> None:
    scrape = ScrapeConfig(rate_limit_seconds=0.1, max_retries=2, cache_ttl_days=0, use_browser=False)
    client = LetterboxdClient("letterboxd-recs/0.1", scrape, tmp_path)

    calls = {"count": 0}

    class DummyResponse:
        def __init__(self, text: str) -> None:
            self.text = text

        def raise_for_status(self) -> None:
            return None

    def flaky_get(*_args, **_kwargs):
        calls["count"] += 1
        if calls["count"] == 1:
            raise requests.RequestException("boom")
        return DummyResponse("ok")

    monkeypatch.setattr(client.session, "get", flaky_get)
    monkeypatch.setattr("letterboxd_recs.ingest.letterboxd.client.time.sleep", lambda *_: None)

    assert client._fetch_with_retries("https://letterboxd.com/test") == "ok"
    assert calls["count"] == 2


def test_repo_upsert_interaction_merges_flags(tmp_path) -> None:
    db_path = tmp_path / "test.sqlite"
    ensure_db(str(db_path))

    with repo.connect(str(db_path)) as conn:
        user_id = repo.upsert_user(conn, Profile(username="spazz", display_name="Spazz"))
        item = FilmItem(
            slug="film-a",
            title="Film A",
            year=2001,
            rating=4.0,
            liked=False,
            watched=True,
            watch_date="2020-01-01",
            watchlist=False,
        )
        film_id = repo.upsert_film(conn, item)
        repo.upsert_interaction(conn, user_id, film_id, item)

        update = FilmItem(
            slug="film-a",
            title=None,
            year=None,
            rating=None,
            liked=True,
            watched=False,
            watch_date=None,
            watchlist=True,
        )
        repo.upsert_interaction(conn, user_id, film_id, update)

        row = conn.execute(
            """
            SELECT rating, liked, watched, watchlist, watch_date
            FROM interactions
            WHERE user_id = ? AND film_id = ?
            """,
            (user_id, film_id),
        ).fetchone()

    assert row["rating"] == 4.0
    assert row["liked"] == 1
    assert row["watched"] == 1
    assert row["watchlist"] == 1
    assert row["watch_date"] == "2020-01-01"


def test_collect_paginated_calls_parser_and_stops(monkeypatch) -> None:
    html_pages = {
        "https://letterboxd.com/user/films/": """
        <div class='film-poster' data-film-slug='film-a'></div>
        <a class='next' href='/user/films/page/2/'></a>
        """,
        "https://letterboxd.com/user/films/page/2/": """
        <div class='film-poster' data-film-slug='film-b'></div>
        """,
    }

    def fake_fetch(_client, url, cache_key, refresh):
        return html_pages[url]

    calls = []

    def parser(html: str):
        calls.append(html.strip())
        return [html.strip()]

    class DummyScrape:
        rate_limit_seconds = 0.0

    class DummyClient:
        scrape = DummyScrape()

        @staticmethod
        def cache_key(url: str) -> str:
            return url.replace("/", "_")

    monkeypatch.setattr(ingest, "_fetch_page", fake_fetch)
    monkeypatch.setattr(ingest, "sleep_seconds", lambda *_: None)

    items = ingest._collect_paginated(
        "https://letterboxd.com/user/films/",
        DummyClient(),
        refresh=False,
        parser=parser,
    )

    assert len(items) == 2
    assert len(calls) == 2
