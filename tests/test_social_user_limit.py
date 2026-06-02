from letterboxd_recs.config import SocialNormalizeConfig, SocialRatingsConfig, SocialSimilarityConfig
from letterboxd_recs.db import repo
from letterboxd_recs.db.conn import ensure_db
from letterboxd_recs.models.social_simple import SocialWeights, compute_social_scores


def test_social_scores_can_limit_to_top_similar_users(tmp_path) -> None:
    db_path = tmp_path / "test.sqlite"
    ensure_db(str(db_path))

    with repo.connect(str(db_path)) as conn:
        root_id = repo.ensure_user(conn, "root")
        stronger_id = repo.upsert_user_stats(conn, "stronger", "Stronger", 100, 10, 100)
        weaker_id = repo.upsert_user_stats(conn, "weaker", "Weaker", 100, 10, 100)
        repo.upsert_graph_edge(conn, root_id, stronger_id, 1)
        repo.upsert_graph_edge(conn, root_id, weaker_id, 1)

        shared_a = repo.upsert_film(conn, _film("shared-a", "Shared A", 2020, watched=True, rating=5.0))
        shared_b = repo.upsert_film(conn, _film("shared-b", "Shared B", 2021, watched=True, rating=4.5))
        stronger_only = repo.upsert_film(conn, _film("stronger-only", "Stronger Only", 2022, watched=True, rating=5.0))
        weaker_only = repo.upsert_film(conn, _film("weaker-only", "Weaker Only", 2023, watched=True, rating=5.0))

        repo.upsert_interaction(conn, root_id, shared_a, _film("shared-a", "Shared A", 2020, watched=True, rating=5.0))
        repo.upsert_interaction(conn, root_id, shared_b, _film("shared-b", "Shared B", 2021, watched=True, rating=4.5))
        repo.upsert_interaction(conn, stronger_id, shared_a, _film("shared-a", "Shared A", 2020, watched=True, rating=5.0))
        repo.upsert_interaction(conn, stronger_id, shared_b, _film("shared-b", "Shared B", 2021, watched=True, rating=4.5))
        repo.upsert_interaction(conn, weaker_id, shared_a, _film("shared-a", "Shared A", 2020, watched=True, rating=2.0))
        repo.upsert_interaction(conn, stronger_id, stronger_only, _film("stronger-only", "Stronger Only", 2022, watched=True, rating=5.0))
        repo.upsert_interaction(conn, weaker_id, weaker_only, _film("weaker-only", "Weaker Only", 2023, watched=True, rating=5.0))
        conn.commit()

    results = compute_social_scores(
        str(db_path),
        "root",
        weights=SocialWeights(),
        rating_weights=_ratings(),
        similarity=_similarity(),
        normalize=_no_normalize(),
        limit=None,
        similar_user_limit=1,
    )

    titles = [item.title for item in results]
    assert "Stronger Only" in titles
    assert "Weaker Only" not in titles


def _film(
    slug: str,
    title: str,
    year: int,
    watched: bool = False,
    rating: float | None = None,
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
        watchlist=False,
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
        normalize_top=True,
    )


def _no_normalize() -> SocialNormalizeConfig:
    return SocialNormalizeConfig(
        enabled=False,
        followee_weight=1.0,
        similarity_weight=1.0,
        interaction_weight=1.0,
        time_weight=1.0,
    )
