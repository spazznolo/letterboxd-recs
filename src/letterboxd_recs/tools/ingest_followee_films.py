from __future__ import annotations

import argparse
from pathlib import Path

from letterboxd_recs.config import load_config
from letterboxd_recs.db import repo
from letterboxd_recs.db.conn import ensure_db
from letterboxd_recs.ingest.letterboxd.ingest import ingest_user
from letterboxd_recs.tools import backfill_films
from letterboxd_recs.util.logging import get_logger

LOG = get_logger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Ingest films for followees already saved in users/graph_edges."
    )
    parser.add_argument(
        "username",
        nargs="?",
        default=None,
        help="Root username used to build follow graph (required unless --refresh is set).",
    )
    parser.add_argument("--config", type=Path, default=None, help="Path to config.toml.")
    parser.add_argument("--min-followers", type=int, default=100)
    parser.add_argument("--min-watched", type=int, default=100)
    parser.add_argument("--limit", type=int, default=None, help="Limit number of followees to ingest.")
    parser.add_argument(
        "--refresh",
        action="store_true",
        help="Refresh all users in the database (films/watchlist only).",
    )
    parser.add_argument(
        "--only-missing",
        action="store_true",
        help="Only ingest followees with zero interactions (not scraped yet).",
    )
    parser.add_argument(
        "--backfill",
        action="store_true",
        help="Run film metadata backfill after ingesting followees.",
    )
    parser.add_argument(
        "--backfill-refresh",
        action="store_true",
        help="Force refresh when fetching film pages in backfill.",
    )
    args = parser.parse_args()

    cfg = load_config(args.config)
    ensure_db(cfg.database_path)

    with repo.connect(cfg.database_path) as conn:
        if args.refresh:
            followees = repo.select_all_usernames(conn)
        else:
            if not args.username:
                raise SystemExit("username is required unless --refresh is set")
            if args.only_missing:
                followees = repo.select_missing_followees(
                    conn,
                    root_username=args.username,
                    min_followers=args.min_followers,
                    min_watched=args.min_watched,
                )
            else:
                followees = repo.select_followees_for_ingest(
                    conn,
                    root_username=args.username,
                    min_followers=args.min_followers,
                    min_watched=args.min_watched,
                )

    if args.limit:
        followees = followees[: args.limit]

    LOG.info("Ingesting %s followees", len(followees))
    for idx, uname in enumerate(followees, start=1):
        LOG.info("(%s/%s) ingest %s", idx, len(followees), uname)
        try:
            ingest_user(
                uname,
                cfg,
                refresh=args.refresh,
                include_diary=False,
                include_films=True,
                include_likes=False,
                include_watchlist=True,
            )
        except Exception as exc:  # noqa: BLE001
            LOG.warning("Failed ingest for %s: %s", uname, exc)

    if args.backfill:
        LOG.info("Running backfill for film metadata (genres)")
        if not args.username:
            raise SystemExit("username is required for backfill without a root user")
        backfill_args = [
            args.username,
            "--fetch-film-pages",
        ]
        if args.backfill_refresh:
            backfill_args.append("--refresh")
        backfill_films.main(backfill_args)


if __name__ == "__main__":
    main()
