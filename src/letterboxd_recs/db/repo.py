from __future__ import annotations

import sqlite3
from typing import Iterable

from letterboxd_recs.ingest.letterboxd.parse import FilmItem, Profile


def connect(path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def upsert_user(conn: sqlite3.Connection, profile: Profile) -> int:
    conn.execute(
        """
        INSERT INTO users (username, display_name, fetched_at)
        VALUES (?, ?, datetime('now'))
        ON CONFLICT(username) DO UPDATE SET
            display_name = COALESCE(excluded.display_name, users.display_name),
            fetched_at = datetime('now')
        """,
        (profile.username, profile.display_name),
    )
    row = conn.execute("SELECT id FROM users WHERE username = ?", (profile.username,)).fetchone()
    return int(row[0])


def upsert_film(conn: sqlite3.Connection, item: FilmItem) -> int:
    title = item.title or item.slug
    conn.execute(
        """
        INSERT INTO films (letterboxd_id, title, year)
        VALUES (?, ?, ?)
        ON CONFLICT(letterboxd_id) DO UPDATE SET
            title = COALESCE(excluded.title, films.title),
            year = COALESCE(excluded.year, films.year)
        """,
        (item.slug, title, item.year),
    )
    row = conn.execute(
        "SELECT id FROM films WHERE letterboxd_id = ?",
        (item.slug,),
    ).fetchone()
    return int(row[0])


def upsert_interaction(
    conn: sqlite3.Connection,
    user_id: int,
    film_id: int,
    item: FilmItem,
) -> None:
    conn.execute(
        """
        INSERT INTO interactions (
            user_id, film_id, rating, liked, watched, watchlist, watch_date
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(user_id, film_id) DO UPDATE SET
            rating = COALESCE(excluded.rating, interactions.rating),
            liked = CASE WHEN excluded.liked > interactions.liked THEN excluded.liked ELSE interactions.liked END,
            watched = CASE WHEN excluded.watched > interactions.watched THEN excluded.watched ELSE interactions.watched END,
            watchlist = CASE WHEN excluded.watchlist > interactions.watchlist THEN excluded.watchlist ELSE interactions.watchlist END,
            watch_date = COALESCE(excluded.watch_date, interactions.watch_date)
        """,
        (
            user_id,
            film_id,
            item.rating,
            int(item.liked),
            int(item.watched),
            int(item.watchlist),
            item.watch_date,
        ),
    )


def upsert_interactions(
    conn: sqlite3.Connection,
    user_id: int,
    items: Iterable[FilmItem],
) -> None:
    for item in items:
        film_id = upsert_film(conn, item)
        upsert_interaction(conn, user_id, film_id, item)
