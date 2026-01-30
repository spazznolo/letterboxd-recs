import sqlite3
from pathlib import Path

from letterboxd_recs.util.logging import get_logger

LOG = get_logger(__name__)


def ensure_db(path: str) -> None:
    db_path = Path(path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    created = not db_path.exists()

    with sqlite3.connect(db_path) as conn:
        schema_path = Path(__file__).parent / "schema.sql"
        conn.executescript(schema_path.read_text(encoding="utf-8"))
        _migrate_users(conn)

    if created:
        LOG.info("Created database at %s", db_path)


def _migrate_users(conn: sqlite3.Connection) -> None:
    existing = {row[1] for row in conn.execute("PRAGMA table_info(users)").fetchall()}
    columns = {
        "follower_count": "INTEGER",
        "following_count": "INTEGER",
        "watched_count": "INTEGER",
    }
    for name, col_type in columns.items():
        if name not in existing:
            conn.execute(f"ALTER TABLE users ADD COLUMN {name} {col_type}")
