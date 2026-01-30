from letterboxd_recs.db import repo
from letterboxd_recs.db.conn import ensure_db
from letterboxd_recs.ingest.letterboxd.parse import FilmItem


def test_select_missing_followees(tmp_path) -> None:
    db_path = tmp_path / "test.sqlite"
    ensure_db(str(db_path))

    with repo.connect(str(db_path)) as conn:
        root_id = repo.ensure_user(conn, "root")
        a_id = repo.upsert_user_stats(conn, "a", "A", 150, 10, 200)
        b_id = repo.upsert_user_stats(conn, "b", "B", 150, 10, 200)
        repo.upsert_graph_edge(conn, root_id, a_id, 1)
        repo.upsert_graph_edge(conn, root_id, b_id, 1)

        film = FilmItem("film-a", "Film A", 2020, None, False, True, None, False)
        film_id = repo.upsert_film(conn, film)
        repo.upsert_interaction(conn, b_id, film_id, film)
        conn.commit()

        missing = repo.select_missing_followees(conn, "root", 100, 100)

    assert missing == ["a"]
