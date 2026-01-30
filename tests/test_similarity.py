from letterboxd_recs.config import SocialSimilarityConfig
from letterboxd_recs.models.social_simple import _compute_similarity


def test_similarity_increases_with_overlap_and_rating() -> None:
    cfg = SocialSimilarityConfig(
        jaccard_weight=0.6,
        rating_weight=0.4,
        rating_prior=0.5,
        rating_k=10,
        default_similarity=0.5,
        stretch_power=1.0,
        normalize_top=False,
    )
    sim_low = _compute_similarity(
        overlap=5,
        me_watched=100,
        followee_watched=100,
        rated_overlap=2,
        avg_diff=2.5,
        cfg=cfg,
    )
    sim_high = _compute_similarity(
        overlap=30,
        me_watched=100,
        followee_watched=100,
        rated_overlap=20,
        avg_diff=0.5,
        cfg=cfg,
    )
    assert sim_high > sim_low
