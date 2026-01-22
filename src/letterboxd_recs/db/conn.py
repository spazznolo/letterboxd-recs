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

    if created:
        LOG.info("Created database at %s", db_path)
