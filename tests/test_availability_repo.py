from letterboxd_recs.db import repo
from letterboxd_recs.db.conn import ensure_db
from letterboxd_recs.ingest.letterboxd.parse import FilmItem


def test_upsert_and_select_available_film_ids(tmp_path) -> None:
    db_path = tmp_path / "test.sqlite"
    ensure_db(str(db_path))

    with repo.connect(str(db_path)) as conn:
        film_a = FilmItem("film-a", "Film A", 2024, None, False, True, None, False)
        film_b = FilmItem("film-b", "Film B", 2023, None, False, True, None, False)
        film_a_id = repo.upsert_film(conn, film_a)
        film_b_id = repo.upsert_film(conn, film_b)

        repo.upsert_film_availability_flags(
            conn,
            film_a_id,
            "CA",
            {"netflix": True, "apple_itunes": True},
            has_stream=True,
        )
        repo.upsert_film_availability_flags(
            conn,
            film_b_id,
            "CA",
            {"netflix": False, "apple_itunes": True},
            has_stream=False,
        )
        conn.commit()

        available = repo.select_available_film_ids(
            conn,
            [film_a_id, film_b_id],
            provider_column="netflix",
            region="CA",
        )
        itunes_available = repo.select_available_film_ids(
            conn,
            [film_a_id, film_b_id],
            provider_column="apple_itunes",
            region="CA",
        )
        stream_available = repo.select_available_film_ids(
            conn,
            [film_a_id, film_b_id],
            provider_column="stream",
            region="CA",
        )

    assert available == {film_a_id}
    assert itunes_available == {film_a_id, film_b_id}
    assert stream_available == {film_a_id}
