import sqlite3

from letterboxd_recs.db.conn import ensure_db
from letterboxd_recs.db import repo


def test_select_followees_for_ingest(tmp_path) -> None:
    db_path = tmp_path / "test.sqlite"
    ensure_db(str(db_path))

    with repo.connect(str(db_path)) as conn:
        root_id = repo.ensure_user(conn, "root")
        a_id = repo.upsert_user_stats(conn, "a", "A", 150, 10, 200)
        b_id = repo.upsert_user_stats(conn, "b", "B", 99, 10, 500)
        c_id = repo.upsert_user_stats(conn, "c", "C", 200, 10, 99)
        d_id = repo.upsert_user_stats(conn, "d", "D", 100, 10, 100)

        repo.upsert_graph_edge(conn, root_id, a_id, 1)
        repo.upsert_graph_edge(conn, root_id, b_id, 1)
        repo.upsert_graph_edge(conn, root_id, c_id, 1)
        repo.upsert_graph_edge(conn, root_id, d_id, 1)
        conn.commit()

        selected = repo.select_followees_for_ingest(conn, "root", 100, 100)

    assert selected == ["a", "d"]
