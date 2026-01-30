from letterboxd_recs.config import SocialNormalizeConfig, SocialRatingsConfig, SocialSimilarityConfig
from letterboxd_recs.db import repo
from letterboxd_recs.db.conn import ensure_db
from letterboxd_recs.models.social_simple import SocialWeights, compute_social_scores


def test_rating_weighting_affects_scores(tmp_path) -> None:
    db_path = tmp_path / "test.sqlite"
    ensure_db(str(db_path))

    with repo.connect(str(db_path)) as conn:
        root_id = repo.ensure_user(conn, "root")
        u1 = repo.upsert_user_stats(conn, "u1", "U1", 200, 10, 100)
        repo.upsert_graph_edge(conn, root_id, u1, 1)

        f1 = repo.upsert_film(conn, _film("film-a", "Film A", 2020))
        f2 = repo.upsert_film(conn, _film("film-b", "Film B", 2021))

        repo.upsert_interaction(conn, u1, f1, _film("film-a", "Film A", 2020, watched=True, rating=5.0))
        repo.upsert_interaction(conn, u1, f2, _film("film-b", "Film B", 2021, watched=True, rating=1.0))
        conn.commit()

    results = compute_social_scores(
        str(db_path),
        "root",
        weights=SocialWeights(),
        rating_weights=_ratings(),
        similarity=_similarity(),
        normalize=_no_normalize(),
        limit=10,
    )
    assert results[0].title == "Film A"
    assert results[1].title == "Film B"


def test_unrated_beats_watchlist(tmp_path) -> None:
    db_path = tmp_path / "test.sqlite"
    ensure_db(str(db_path))

    with repo.connect(str(db_path)) as conn:
        root_id = repo.ensure_user(conn, "root")
        u1 = repo.upsert_user_stats(conn, "u1", "U1", 200, 10, 100)
        repo.upsert_graph_edge(conn, root_id, u1, 1)

        f1 = repo.upsert_film(conn, _film("film-a", "Film A", 2020))
        f2 = repo.upsert_film(conn, _film("film-b", "Film B", 2021))

        repo.upsert_interaction(conn, u1, f1, _film("film-a", "Film A", 2020, watched=True, rating=None))
        repo.upsert_interaction(conn, u1, f2, _film("film-b", "Film B", 2021, watched=False, rating=None, watchlist=True))
        conn.commit()

    results = compute_social_scores(
        str(db_path),
        "root",
        weights=SocialWeights(),
        rating_weights=_ratings(),
        similarity=_similarity(),
        normalize=_no_normalize(),
        limit=10,
    )
    assert results[0].title == "Film A"


def test_watchlist_includes_films(tmp_path) -> None:
    db_path = tmp_path / "test.sqlite"
    ensure_db(str(db_path))

    with repo.connect(str(db_path)) as conn:
        repo.ensure_user(conn, "root")
        f1 = repo.upsert_film(conn, _film("film-a", "Film A", 2024))
        repo.upsert_interaction(
            conn,
            repo.ensure_user(conn, "root"),
            f1,
            _film("film-a", "Film A", 2024, watched=False, rating=None, watchlist=True),
        )
        conn.commit()

    results = compute_social_scores(
        str(db_path),
        "root",
        weights=SocialWeights(),
        rating_weights=_ratings(),
        similarity=_similarity(),
        normalize=_no_normalize(),
        limit=10,
    )
    assert results
    assert results[0].title == "Film A"
    assert results[0].score > 0


def _film(
    slug: str,
    title: str,
    year: int,
    watched: bool = False,
    rating: float | None = None,
    watchlist: bool = False,
):
    from letterboxd_recs.ingest.letterboxd.parse import FilmItem

    return FilmItem(
        slug=slug,
        title=title,
        year=year,
        rating=rating,
        liked=False,
        watched=watched,
        watch_date=None,
        watchlist=watchlist,
    )


def _ratings() -> SocialRatingsConfig:
    return SocialRatingsConfig(
        negative_min=-1.0,
        negative_max=-0.1,
        positive_min=0.1,
        positive_max=1.0,
        unrated=0.25,
        watchlist_multiplier=0.5,
    )


def _similarity() -> SocialSimilarityConfig:
    return SocialSimilarityConfig(
        jaccard_weight=0.6,
        rating_weight=0.4,
        rating_prior=0.5,
        rating_k=10,
        default_similarity=0.5,
        stretch_power=1.0,
        normalize_top=False,
    )


def _no_normalize() -> SocialNormalizeConfig:
    return SocialNormalizeConfig(
        enabled=False,
        followee_weight=1.0,
        similarity_weight=1.0,
        interaction_weight=1.0,
        time_weight=1.0,
    )
