from letterboxd_recs.db import repo
from letterboxd_recs.db.conn import ensure_db
from letterboxd_recs.models.social_simple import compute_social_scores


def test_social_scores_inverse_watched_weight(tmp_path) -> None:
    db_path = tmp_path / "test.sqlite"
    ensure_db(str(db_path))

    with repo.connect(str(db_path)) as conn:
        root_id = repo.ensure_user(conn, "root")
        u1 = repo.upsert_user_stats(conn, "u1", "U1", 200, 10, 100)
        u2 = repo.upsert_user_stats(conn, "u2", "U2", 200, 10, 400)

        repo.upsert_graph_edge(conn, root_id, u1, 1)
        repo.upsert_graph_edge(conn, root_id, u2, 1)

        f1 = repo.upsert_film(conn, _film("film-a", "Film A", 2020))
        f2 = repo.upsert_film(conn, _film("film-b", "Film B", 2021))

        # u1 watched film-a, u2 watched film-b
        repo.upsert_interaction(conn, u1, f1, _film("film-a", "Film A", 2020, watched=True))
        repo.upsert_interaction(conn, u2, f2, _film("film-b", "Film B", 2021, watched=True))
        conn.commit()

    results = compute_social_scores(str(db_path), "root", limit=10)
    assert results[0].title == "Film A"
    assert results[1].title == "Film B"


def _film(slug: str, title: str, year: int, watched: bool = False):
    from letterboxd_recs.ingest.letterboxd.parse import FilmItem

    return FilmItem(
        slug=slug,
        title=title,
        year=year,
        rating=None,
        liked=False,
        watched=watched,
        watch_date=None,
        watchlist=False,
    )
