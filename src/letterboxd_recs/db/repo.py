from __future__ import annotations

import re
import sqlite3
from typing import Iterable

from letterboxd_recs.ingest.letterboxd.parse import FilmItem, Profile


def connect(path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA busy_timeout = 5000")
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


def ensure_user(conn: sqlite3.Connection, username: str) -> int:
    conn.execute(
        """
        INSERT INTO users (username, fetched_at)
        VALUES (?, datetime('now'))
        ON CONFLICT(username) DO UPDATE SET
            fetched_at = datetime('now')
        """,
        (username,),
    )
    row = conn.execute("SELECT id FROM users WHERE username = ?", (username,)).fetchone()
    return int(row[0])


def upsert_user_stats(
    conn: sqlite3.Connection,
    username: str,
    display_name: str | None,
    followers: int | None,
    following: int | None,
    watched: int | None,
) -> int:
    conn.execute(
        """
        INSERT INTO users (
            username, display_name, follower_count, following_count, watched_count, fetched_at
        )
        VALUES (?, ?, ?, ?, ?, datetime('now'))
        ON CONFLICT(username) DO UPDATE SET
            display_name = COALESCE(excluded.display_name, users.display_name),
            follower_count = COALESCE(excluded.follower_count, users.follower_count),
            following_count = COALESCE(excluded.following_count, users.following_count),
            watched_count = COALESCE(excluded.watched_count, users.watched_count),
            fetched_at = datetime('now')
        """,
        (username, display_name, followers, following, watched),
    )
    row = conn.execute("SELECT id FROM users WHERE username = ?", (username,)).fetchone()
    return int(row[0])


def upsert_film(conn: sqlite3.Connection, item: FilmItem) -> int:
    title = item.title or item.slug
    conn.execute(
        """
        INSERT INTO films (letterboxd_id, title, year, genres)
        VALUES (?, ?, ?, NULL)
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


def upsert_film_metadata(
    conn: sqlite3.Connection,
    slug: str,
    title: str | None,
    year: int | None,
    genres: str | None,
) -> None:
    insert_title = title or slug
    conn.execute(
        """
        INSERT INTO films (letterboxd_id, title, year, genres)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(letterboxd_id) DO UPDATE SET
            title = COALESCE(excluded.title, films.title),
            year = COALESCE(excluded.year, films.year),
            genres = COALESCE(excluded.genres, films.genres)
        """,
        (slug, insert_title, year, genres),
    )


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
            item.liked,
            item.watched,
            item.watchlist,
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


def upsert_graph_edge(conn: sqlite3.Connection, src_id: int, dst_id: int, depth: int) -> None:
    conn.execute(
        """
        INSERT INTO graph_edges (src_user_id, dst_user_id, depth)
        VALUES (?, ?, ?)
        ON CONFLICT(src_user_id, dst_user_id) DO UPDATE SET
            depth = MIN(excluded.depth, graph_edges.depth)
        """,
        (src_id, dst_id, depth),
    )


def select_followees_for_ingest(
    conn: sqlite3.Connection,
    root_username: str,
    min_followers: int,
    min_watched: int,
) -> list[str]:
    rows = conn.execute(
        """
        SELECT u.username
        FROM graph_edges g
        JOIN users u ON u.id = g.dst_user_id
        WHERE g.src_user_id = (SELECT id FROM users WHERE username = ?)
          AND COALESCE(u.follower_count, 0) >= ?
          AND COALESCE(u.watched_count, 0) >= ?
        ORDER BY u.follower_count DESC, u.watched_count DESC
        """,
        (root_username, min_followers, min_watched),
    ).fetchall()
    return [row[0] for row in rows]


def select_missing_followees(
    conn: sqlite3.Connection,
    root_username: str,
    min_followers: int,
    min_watched: int,
) -> list[str]:
    rows = conn.execute(
        """
        SELECT u.username
        FROM graph_edges g
        JOIN users u ON u.id = g.dst_user_id
        LEFT JOIN interactions i ON i.user_id = u.id
        WHERE g.src_user_id = (SELECT id FROM users WHERE username = ?)
          AND COALESCE(u.follower_count, 0) >= ?
          AND COALESCE(u.watched_count, 0) >= ?
        GROUP BY u.id
        HAVING COUNT(i.film_id) = 0
        ORDER BY u.follower_count DESC, u.watched_count DESC
        """,
        (root_username, min_followers, min_watched),
    ).fetchall()
    return [row[0] for row in rows]


def select_social_rows(conn: sqlite3.Connection, root_username: str):
    return conn.execute(
        """
        SELECT
            f.id AS film_id,
            f.title AS title,
            f.year AS year,
            f.genres AS genres,
            i.watched AS watched,
            i.watchlist AS watchlist,
            i.rating AS rating,
            u.watched_count AS watched_count,
            i.user_id AS followee_id
        FROM users u
        JOIN interactions i ON i.user_id = u.id
        JOIN films f ON f.id = i.film_id
        WHERE i.user_id != (SELECT id FROM users WHERE username = ?)
          AND (i.watched = 1 OR i.watchlist = 1)
          AND f.id NOT IN (
              SELECT film_id FROM interactions
              WHERE user_id = (SELECT id FROM users WHERE username = ?)
                AND watched = 1
          )
        """,
        (root_username, root_username),
    ).fetchall()


def select_similarity_rows(conn: sqlite3.Connection, root_username: str):
    return conn.execute(
        """
        SELECT
            i2.user_id AS followee_id,
            COUNT(*) AS overlap,
            SUM(CASE WHEN i1.rating IS NOT NULL AND i2.rating IS NOT NULL THEN 1 ELSE 0 END) AS rated_overlap,
            AVG(CASE WHEN i1.rating IS NOT NULL AND i2.rating IS NOT NULL THEN ABS(i1.rating - i2.rating) END) AS avg_diff
        FROM interactions i1
        JOIN interactions i2 ON i1.film_id = i2.film_id
        WHERE i1.user_id = (SELECT id FROM users WHERE username = ?)
          AND i2.user_id != (SELECT id FROM users WHERE username = ?)
          AND i1.watched = 1
          AND i2.watched = 1
        GROUP BY i2.user_id
        """,
        (root_username, root_username),
    ).fetchall()


def select_user_watchlist(conn: sqlite3.Connection, username: str):
    return conn.execute(
        """
        SELECT
            f.id AS film_id,
            f.title AS title,
            f.year AS year,
            f.genres AS genres
        FROM interactions i
        JOIN films f ON f.id = i.film_id
        WHERE i.user_id = (SELECT id FROM users WHERE username = ?)
          AND i.watchlist = 1
          AND i.watched = 0
        """,
        (username,),
    ).fetchall()


def select_all_usernames(conn: sqlite3.Connection) -> list[str]:
    rows = conn.execute("SELECT username FROM users ORDER BY username").fetchall()
    return [row[0] for row in rows]


def select_user_id(conn: sqlite3.Connection, username: str) -> int | None:
    row = conn.execute("SELECT id FROM users WHERE username = ?", (username,)).fetchone()
    if not row:
        return None
    return int(row[0])


def select_user_rating_stats(
    conn: sqlite3.Connection, user_ids: list[int]
) -> dict[int, tuple[float, float] | None]:
    if not user_ids:
        return {}
    placeholders = ",".join("?" for _ in user_ids)
    rows = conn.execute(
        f"""
        SELECT user_id,
               AVG(rating) AS mean_rating,
               AVG(rating * rating) AS mean_sq,
               COUNT(*) AS n
        FROM interactions
        WHERE rating IS NOT NULL
          AND user_id IN ({placeholders})
        GROUP BY user_id
        """,
        user_ids,
    ).fetchall()
    stats: dict[int, tuple[float, float] | None] = {}
    for row in rows:
        user_id = int(row[0])
        mean = float(row[1])
        mean_sq = float(row[2])
        n = int(row[3])
        if n < 2:
            stats[user_id] = None
            continue
        variance = max(0.0, mean_sq - mean * mean)
        std = variance ** 0.5
        if std == 0.0:
            stats[user_id] = None
        else:
            stats[user_id] = (mean, std)
    return stats


def select_shared_ratings(
    conn: sqlite3.Connection, root_id: int, followee_ids: list[int]
) -> list[tuple[int, float, float]]:
    if not followee_ids:
        return []
    placeholders = ",".join("?" for _ in followee_ids)
    rows = conn.execute(
        f"""
        SELECT i2.user_id, i1.rating, i2.rating
        FROM interactions i1
        JOIN interactions i2 ON i1.film_id = i2.film_id
        WHERE i1.user_id = ?
          AND i2.user_id IN ({placeholders})
          AND i1.watched = 1
          AND i2.watched = 1
          AND i1.rating IS NOT NULL
          AND i2.rating IS NOT NULL
        """,
        (root_id, *followee_ids),
    ).fetchall()
    return [(int(r[0]), float(r[1]), float(r[2])) for r in rows]


def select_shared_rated_films(
    conn: sqlite3.Connection, root_id: int, followee_id: int
) -> list[tuple[str, int | None, float, float]]:
    rows = conn.execute(
        """
        SELECT f.title, f.year, i1.rating, i2.rating
        FROM interactions i1
        JOIN interactions i2 ON i1.film_id = i2.film_id
        JOIN films f ON f.id = i1.film_id
        WHERE i1.user_id = ?
          AND i2.user_id = ?
          AND i1.watched = 1
          AND i2.watched = 1
          AND i1.rating IS NOT NULL
          AND i2.rating IS NOT NULL
        """,
        (root_id, followee_id),
    ).fetchall()
    return [(str(r[0]), r[1], float(r[2]), float(r[3])) for r in rows]


def select_watched_count(conn: sqlite3.Connection, username: str) -> int:
    row = conn.execute(
        """
        SELECT COALESCE(u.watched_count, (
            SELECT COUNT(*) FROM interactions WHERE user_id = u.id AND watched = 1
        ))
        FROM users u
        WHERE u.username = ?
        """,
        (username,),
    ).fetchone()
    return int(row[0]) if row and row[0] is not None else 0


def select_followee_watched_count(conn: sqlite3.Connection, user_id: int) -> int:
    row = conn.execute(
        """
        SELECT COALESCE(u.watched_count, (
            SELECT COUNT(*) FROM interactions WHERE user_id = u.id AND watched = 1
        ))
        FROM users u
        WHERE u.id = ?
        """,
        (user_id,),
    ).fetchone()
    return int(row[0]) if row and row[0] is not None else 0


def select_followee_watched_counts(conn: sqlite3.Connection, user_ids: list[int]) -> dict[int, int]:
    if not user_ids:
        return {}
    placeholders = ",".join("?" for _ in user_ids)
    rows = conn.execute(
        f"""
        SELECT u.id,
               COALESCE(u.watched_count, (
                   SELECT COUNT(*) FROM interactions WHERE user_id = u.id AND watched = 1
               )) AS watched_count
        FROM users u
        WHERE u.id IN ({placeholders})
        """,
        user_ids,
    ).fetchall()
    return {int(row[0]): int(row[1] or 0) for row in rows}


def select_user_names(conn: sqlite3.Connection, user_ids: list[int]) -> dict[int, tuple[str, str | None]]:
    if not user_ids:
        return {}
    placeholders = ",".join("?" for _ in user_ids)
    rows = conn.execute(
        f"""
        SELECT id, username, display_name
        FROM users
        WHERE id IN ({placeholders})
        """,
        user_ids,
    ).fetchall()
    return {int(row[0]): (row[1], row[2]) for row in rows}


def select_film_slugs(conn: sqlite3.Connection, film_ids: list[int]) -> dict[int, str]:
    if not film_ids:
        return {}
    placeholders = ",".join("?" for _ in film_ids)
    rows = conn.execute(
        f"""
        SELECT id, letterboxd_id
        FROM films
        WHERE id IN ({placeholders})
          AND letterboxd_id IS NOT NULL
        """,
        film_ids,
    ).fetchall()
    return {int(row[0]): str(row[1]) for row in rows}


def upsert_film_availability_flags(
    conn: sqlite3.Connection,
    film_id: int,
    region: str,
    flags: dict[str, bool],
    has_stream: bool = False,
) -> None:
    valid_columns = select_availability_columns(conn)
    known_flags = {k: bool(v) for k, v in flags.items() if k in valid_columns}
    conn.execute(
        """
        INSERT INTO film_availability_flags (film_id, region, stream, last_updated)
        VALUES (?, ?, ?, datetime('now'))
        ON CONFLICT(film_id) DO UPDATE SET
            region = excluded.region,
            stream = excluded.stream,
            last_updated = datetime('now')
        """,
        (film_id, region, int(has_stream)),
    )

    updates = ['region = ?', 'stream = ?', "last_updated = datetime('now')"]
    params: list[object] = [region, int(has_stream)]
    for col in sorted(known_flags.keys()):
        _validate_availability_column(col)
        updates.append(f'"{col}" = ?')
        params.append(int(bool(known_flags[col])))
    params.append(film_id)

    conn.execute(
        f"""
        UPDATE film_availability_flags
        SET {", ".join(updates)}
        WHERE film_id = ?
        """,
        tuple(params),
    )


def select_available_film_ids(
    conn: sqlite3.Connection,
    film_ids: list[int],
    provider_column: str,
    region: str,
) -> set[int]:
    if provider_column not in select_availability_columns(conn):
        raise ValueError(f"Unknown provider column: {provider_column}")
    _validate_availability_column(provider_column)
    if not film_ids:
        return set()
    placeholders = ",".join("?" for _ in film_ids)
    rows = conn.execute(
        f"""
        SELECT film_id
        FROM film_availability_flags
        WHERE film_id IN ({placeholders})
          AND region = ?
          AND "{provider_column}" = 1
        """,
        (*film_ids, region),
    ).fetchall()
    return {int(row[0]) for row in rows}


def select_availability_columns(conn: sqlite3.Connection) -> set[str]:
    rows = conn.execute("PRAGMA table_info(film_availability_flags)").fetchall()
    return {str(row[1]) for row in rows}


def _validate_availability_column(name: str) -> None:
    if not re.fullmatch(r"[a-z][a-z0-9_]*", name):
        raise ValueError(f"Invalid availability column name: {name}")


def select_availability_map(
    conn: sqlite3.Connection,
    film_ids: list[int],
    columns: list[str],
) -> dict[int, dict[str, bool]]:
    if not film_ids or not columns:
        return {}
    valid_columns = select_availability_columns(conn)
    cols = [col for col in columns if col in valid_columns]
    if not cols:
        return {}
    for col in cols:
        _validate_availability_column(col)
    placeholders = ",".join("?" for _ in film_ids)
    col_expr = ", ".join(f'"{col}"' for col in cols)
    rows = conn.execute(
        f"""
        SELECT film_id, {col_expr}
        FROM film_availability_flags
        WHERE film_id IN ({placeholders})
        """,
        film_ids,
    ).fetchall()
    results: dict[int, dict[str, bool]] = {}
    for row in rows:
        film_id = int(row[0])
        values = {}
        for idx, col in enumerate(cols, start=1):
            values[col] = bool(row[idx])
        results[film_id] = values
    return results
