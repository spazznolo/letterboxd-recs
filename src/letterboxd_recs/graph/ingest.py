from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from pathlib import Path

from letterboxd_recs.config import Config
from letterboxd_recs.db import repo
from letterboxd_recs.db.conn import ensure_db
from letterboxd_recs.ingest.letterboxd.client import LetterboxdClient
from letterboxd_recs.ingest.letterboxd.ingest import ingest_user
from letterboxd_recs.ingest.letterboxd.parse import is_challenge_page, parse_next_page
from letterboxd_recs.ingest.letterboxd.social import FolloweeSummary, parse_following_entries
from letterboxd_recs.util.logging import get_logger
from letterboxd_recs.util.ratelimit import sleep_seconds

LOG = get_logger(__name__)
BASE_URL = "https://letterboxd.com"


@dataclass(frozen=True)
class GraphIngestResult:
    username: str
    nodes: int
    edges: int


def ingest_follow_graph(
    username: str,
    cfg: Config,
    refresh: bool = False,
    max_depth: int | None = None,
    ingest_interactions: bool = True,
) -> GraphIngestResult:
    ensure_db(cfg.database_path)
    depth_limit = max_depth if max_depth is not None else cfg.graph.max_depth
    cache_dir = Path(cfg.app.cache_dir) / "letterboxd" / username
    client = LetterboxdClient(cfg.app.user_agent, cfg.scrape, cache_dir)

    with repo.connect(cfg.database_path) as conn:
        root_id = repo.ensure_user(conn, username)
        visited: set[str] = {username}
        edges_added = 0

        queue: deque[tuple[str, int]] = deque([(username, 0)])
        while queue:
            current, depth = queue.popleft()
            if depth >= depth_limit:
                continue

            followees = _collect_followees(current, client, refresh)
            for followee in followees:
                if not _passes_filters(followee):
                    continue

                if followee.username not in visited:
                    visited.add(followee.username)
                    queue.append((followee.username, depth + 1))
                    if ingest_interactions:
                        try:
                            ingest_user(followee.username, cfg, refresh=False)
                        except Exception as exc:  # noqa: BLE001
                            LOG.warning("Failed ingest for %s: %s", followee.username, exc)

                src_id = repo.ensure_user(conn, current)
                dst_id = repo.upsert_user_stats(
                    conn,
                    followee.username,
                    followee.display_name,
                    followee.followers,
                    followee.following,
                    followee.watched,
                )
                repo.upsert_graph_edge(conn, src_id, dst_id, depth + 1)
                edges_added += 1

            conn.commit()

    return GraphIngestResult(username=username, nodes=len(visited), edges=edges_added)


def _collect_followees(username: str, client: LetterboxdClient, refresh: bool) -> list[FolloweeSummary]:
    url = f"{BASE_URL}/{username}/following/"
    followees: list[FolloweeSummary] = []
    page_url = url

    while page_url:
        cache_key = client.cache_key(page_url)
        html = _fetch_following_page(client, page_url, cache_key, refresh)

        followees.extend(parse_following_entries(html))
        next_rel = parse_next_page(html)
        page_url = f"{BASE_URL}{next_rel}" if next_rel else None
        sleep_seconds(client.scrape.rate_limit_seconds)

    deduped: dict[str, FolloweeSummary] = {}
    for entry in followees:
        if entry.username not in deduped:
            deduped[entry.username] = entry
    return list(deduped.values())


def _passes_filters(entry: FolloweeSummary) -> bool:
    followers = entry.followers or 0
    watched = entry.watched or 0
    return followers >= 100 and watched >= 100


def _fetch_following_page(
    client: LetterboxdClient,
    url: str,
    cache_key: str,
    refresh: bool,
) -> str:
    if refresh and client.scrape.use_browser:
        from letterboxd_recs.ingest.letterboxd.browser import fetch_html as browser_fetch

        html = browser_fetch(url, user_agent=client.session.headers.get("User-Agent", "")).content
        client.write_cache(cache_key, html)
        return html

    try:
        html = client.fetch_html(url, cache_key=cache_key, refresh=refresh).content
    except RuntimeError:
        from letterboxd_recs.ingest.letterboxd.browser import fetch_html as browser_fetch

        html = browser_fetch(url, user_agent=client.session.headers.get("User-Agent", "")).content
        client.write_cache(cache_key, html)

    if is_challenge_page(html):
        from letterboxd_recs.ingest.letterboxd.browser import fetch_html as browser_fetch

        html = browser_fetch(url, user_agent=client.session.headers.get("User-Agent", "")).content
        client.write_cache(cache_key, html)

    return html
