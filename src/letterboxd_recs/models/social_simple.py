from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Iterable

from letterboxd_recs.db import repo
from letterboxd_recs.config import (
    SocialConfig,
    SocialRatingsConfig,
    SocialSimilarityConfig,
    SocialNormalizeConfig,
)


@dataclass(frozen=True)
class SocialScore:
    film_id: int
    title: str
    year: int | None
    genres: str | None
    score: float


@dataclass(frozen=True)
class SimilarityScore:
    followee_id: int
    username: str
    display_name: str | None
    similarity: float
    jaccard: float
    rating_similarity: float
    overlap: int
    rated_overlap: int
    avg_diff: float | None


@dataclass(frozen=True)
class SocialWeights:
    watched_weight: float = 1.0
    watchlist_weight: float = 0.5
    time_weight_min: float = 0.25
    time_weight_years: int = 100


def compute_social_scores(
    db_path: str,
    username: str,
    weights: SocialWeights | SocialConfig | None = None,
    rating_weights: SocialRatingsConfig | None = None,
    similarity: SocialSimilarityConfig | None = None,
    normalize: SocialNormalizeConfig | None = None,
    limit: int | None = 200,
) -> list[SocialScore]:
    if weights is None:
        weights = SocialWeights()
    if rating_weights is None:
        rating_weights = SocialRatingsConfig(
            negative_min=-1.0,
            negative_max=-0.1,
            positive_min=0.1,
            positive_max=1.0,
            unrated=0.25,
            watchlist_multiplier=0.5,
        )
    if similarity is None:
        similarity = SocialSimilarityConfig(
            jaccard_weight=0.6,
            rating_weight=0.4,
            rating_prior=0.5,
            rating_k=10,
            default_similarity=0.5,
            stretch_power=5.0,
            normalize_top=True,
        )
    if normalize is None:
        normalize = SocialNormalizeConfig(
            enabled=True,
            followee_weight=1.0,
            similarity_weight=1.0,
            interaction_weight=1.0,
            time_weight=1.0,
        )

    with repo.connect(db_path) as conn:
        rows = repo.select_social_rows(conn, username)
        sim_rows = repo.select_similarity_rows(conn, username)
        me_watched = repo.select_watched_count(conn, username)
        watchlist_rows = repo.select_user_watchlist(conn, username)
        root_id = conn.execute(
            "SELECT id FROM users WHERE username = ?",
            (username,),
        ).fetchone()[0]
        followee_ids = [int(r["followee_id"]) for r in sim_rows]
        followee_watched_map = repo.select_followee_watched_counts(conn, followee_ids)
        rating_stats = repo.select_user_rating_stats(conn, [root_id] + followee_ids)
        rating_diffs = _rating_diffs(conn, root_id, followee_ids, rating_stats)

    sim_map: dict[int, float] = {}
    sim_components: list[tuple[int, float, float]] = []
    for row in sim_rows:
        followee_id = int(row["followee_id"])
        overlap = int(row["overlap"])
        rated_overlap, avg_diff = rating_diffs.get(followee_id, (0, None))
        followee_watched = followee_watched_map.get(followee_id, 0)
        jaccard, rating_shrunk = _compute_components(
            overlap=overlap,
            me_watched=me_watched,
            followee_watched=followee_watched,
            rated_overlap=rated_overlap,
            avg_diff=avg_diff,
            cfg=similarity,
        )
        sim_components.append((followee_id, jaccard, rating_shrunk))
    jaccard_norm = _minmax([item[1] for item in sim_components])
    rating_norm = _minmax([item[2] for item in sim_components])
    for idx, (followee_id, jaccard, rating_shrunk) in enumerate(sim_components):
        sim = (jaccard_norm[idx] * rating_norm[idx]) ** 2
        sim_map[followee_id] = sim
    if similarity.normalize_top and sim_map:
        top = max(sim_map.values())
        if top > 0:
            sim_map = {k: v / top for k, v in sim_map.items()}

    if normalize.enabled and (rows or watchlist_rows):
        component_rows: list[dict[str, float]] = []
        current_year = datetime.now().year
        for row in rows:
            watched = int(row["watched"])
            watchlist = int(row["watchlist"])
            rating = row["rating"]
            year = row["year"]
            followee_id = int(row["followee_id"])

            sim_weight = sim_map.get(followee_id, similarity.default_similarity)
            interaction_weight = _interaction_weight(
                watched,
                watchlist,
                rating,
                weights,
                rating_weights,
                followee_id,
                rating_stats,
            )
            if interaction_weight == 0.0:
                continue
            time_weight = _time_weight(
                year,
                current_year=current_year,
                min_weight=weights.time_weight_min,
                window_years=weights.time_weight_years,
            )
            component_rows.append(
                {
                    "film_id": int(row["film_id"]),
                    "title": row["title"],
                    "year": year,
                    "genres": row["genres"],
                    "similarity": sim_weight,
                    "interaction_weight": interaction_weight,
                    "time_weight": time_weight,
                }
            )
        for row in watchlist_rows:
            year = row["year"]
            time_weight = _time_weight(
                year,
                current_year=current_year,
                min_weight=weights.time_weight_min,
                window_years=weights.time_weight_years,
            )
            component_rows.append(
                {
                    "film_id": int(row["film_id"]),
                    "title": row["title"],
                    "year": year,
                    "genres": row["genres"],
                    "similarity": 5.0,
                    "interaction_weight": rating_weights.unrated
                    * rating_weights.watchlist_multiplier,
                    "time_weight": time_weight,
                }
            )

        interaction_z = _zscore([r["interaction_weight"] for r in component_rows])

        scores: dict[int, SocialScore] = {}
        for idx, row in enumerate(component_rows):
            score = (
                normalize.similarity_weight * float(row["similarity"])
            ) * (
                normalize.interaction_weight * interaction_z[idx]
            ) * (
                normalize.time_weight * float(row["time_weight"])
            )
            film_id = int(row["film_id"])
            existing = scores.get(film_id)
            if existing:
                scores[film_id] = SocialScore(
                    film_id=film_id,
                    title=existing.title,
                    year=existing.year,
                    genres=existing.genres,
                    score=existing.score + score,
                )
            else:
                scores[film_id] = SocialScore(
                    film_id=film_id,
                    title=row["title"],
                    year=row["year"],
                    genres=row["genres"],
                    score=score,
                )
    else:
        scores: dict[int, SocialScore] = {}
        for row in rows:
            film_id = int(row["film_id"])
            title = row["title"]
            year = row["year"]
            genres = row["genres"]
            watched = int(row["watched"])
            watchlist = int(row["watchlist"])
            rating = row["rating"]
            followee_id = int(row["followee_id"])

            sim_weight = sim_map.get(followee_id, similarity.default_similarity)
            interaction_weight = _interaction_weight(
                watched,
                watchlist,
                rating,
                weights,
                rating_weights,
                followee_id,
                rating_stats,
            )
            if interaction_weight == 0.0:
                continue

            time_weight = _time_weight(
                year,
                current_year=datetime.now().year,
                min_weight=weights.time_weight_min,
                window_years=weights.time_weight_years,
            )
            score = sim_weight * interaction_weight * time_weight
            existing = scores.get(film_id)
            if existing:
                scores[film_id] = SocialScore(
                    film_id=film_id,
                    title=existing.title,
                    year=existing.year,
                    genres=existing.genres,
                    score=existing.score + score,
                )
            else:
                scores[film_id] = SocialScore(
                    film_id=film_id,
                    title=title,
                    year=year,
                    genres=genres,
                    score=score,
                )
        for row in watchlist_rows:
            film_id = int(row["film_id"])
            title = row["title"]
            year = row["year"]
            genres = row["genres"]
            time_weight = _time_weight(
                year,
                current_year=datetime.now().year,
                min_weight=weights.time_weight_min,
                window_years=weights.time_weight_years,
            )
            score = (
                5.0
                * rating_weights.unrated
                * rating_weights.watchlist_multiplier
                * time_weight
            )
            existing = scores.get(film_id)
            if existing:
                scores[film_id] = SocialScore(
                    film_id=film_id,
                    title=existing.title,
                    year=existing.year,
                    genres=existing.genres,
                    score=existing.score + score,
                )
            else:
                scores[film_id] = SocialScore(
                    film_id=film_id,
                    title=title,
                    year=year,
                    genres=genres,
                    score=score,
                )

    ranked = sorted(scores.values(), key=lambda item: item.score, reverse=True)
    if limit is None:
        return ranked
    return ranked[:limit]


def compute_similarity_scores(
    db_path: str,
    username: str,
    similarity: SocialSimilarityConfig | None = None,
    normalize_top: bool = False,
) -> list[SimilarityScore]:
    if similarity is None:
        similarity = SocialSimilarityConfig(
            jaccard_weight=0.6,
            rating_weight=0.4,
            rating_prior=0.5,
            rating_k=10,
            default_similarity=0.5,
            stretch_power=5.0,
            normalize_top=True,
        )

    with repo.connect(db_path) as conn:
        sim_rows = repo.select_similarity_rows(conn, username)
        me_watched = repo.select_watched_count(conn, username)
        root_id = conn.execute(
            "SELECT id FROM users WHERE username = ?",
            (username,),
        ).fetchone()[0]
        followee_ids = [int(r["followee_id"]) for r in sim_rows]
        followee_watched_map = repo.select_followee_watched_counts(conn, followee_ids)
        name_map = repo.select_user_names(conn, followee_ids)
        rating_stats = repo.select_user_rating_stats(conn, [root_id] + followee_ids)
        rating_diffs = _rating_diffs(conn, root_id, followee_ids, rating_stats)

    scores: list[SimilarityScore] = []
    components: list[tuple[int, float, float, int, int, float | None]] = []
    for row in sim_rows:
        followee_id = int(row["followee_id"])
        overlap = int(row["overlap"])
        rated_overlap, avg_diff = rating_diffs.get(followee_id, (0, None))
        followee_watched = followee_watched_map.get(followee_id, 0)
        jaccard, rating_shrunk = _compute_components(
            overlap=overlap,
            me_watched=me_watched,
            followee_watched=followee_watched,
            rated_overlap=rated_overlap,
            avg_diff=avg_diff,
            cfg=similarity,
        )
        components.append((followee_id, jaccard, rating_shrunk, overlap, rated_overlap, avg_diff))

    jaccard_norm = _minmax([item[1] for item in components])
    rating_norm = _minmax([item[2] for item in components])

    for idx, (followee_id, jaccard, rating_shrunk, overlap, rated_overlap, avg_diff) in enumerate(
        components
    ):
        sim_value = (jaccard_norm[idx] * rating_norm[idx]) ** 2
        username_val, display_name = name_map.get(followee_id, ("", None))
        scores.append(
            SimilarityScore(
                followee_id=followee_id,
                username=username_val,
                display_name=display_name,
                similarity=sim_value,
                jaccard=jaccard_norm[idx],
                rating_similarity=rating_norm[idx],
                overlap=overlap,
                rated_overlap=rated_overlap,
                avg_diff=avg_diff,
            )
        )

    scores.sort(key=lambda item: item.similarity, reverse=True)
    if normalize_top and scores:
        top = scores[0].similarity
        if top > 0:
            scores = [
                SimilarityScore(
                    followee_id=s.followee_id,
                    username=s.username,
                    display_name=s.display_name,
                    similarity=s.similarity / top,
                    jaccard=s.jaccard,
                    rating_similarity=s.rating_similarity,
                    overlap=s.overlap,
                    rated_overlap=s.rated_overlap,
                    avg_diff=s.avg_diff,
                )
                for s in scores
            ]
    return scores


def compute_social_contributions(
    db_path: str,
    username: str,
    film_ids: list[int],
    weights: SocialWeights | SocialConfig,
    rating_weights: SocialRatingsConfig,
    similarity: SocialSimilarityConfig,
) -> dict[int, list[dict[str, float | str]]]:
    if not film_ids:
        return {}

    with repo.connect(db_path) as conn:
        rows = repo.select_social_rows(conn, username)
        sim_rows = repo.select_similarity_rows(conn, username)
        me_watched = repo.select_watched_count(conn, username)
        watchlist_rows = repo.select_user_watchlist(conn, username)
        root_id = conn.execute(
            "SELECT id FROM users WHERE username = ?",
            (username,),
        ).fetchone()[0]
        followee_ids = [int(r["followee_id"]) for r in sim_rows]
        followee_watched_map = repo.select_followee_watched_counts(conn, followee_ids)
        name_map = repo.select_user_names(conn, followee_ids)
        rating_stats = repo.select_user_rating_stats(conn, [root_id] + followee_ids)
        rating_diffs = _rating_diffs(conn, root_id, followee_ids, rating_stats)

    sim_map: dict[int, float] = {}
    sim_components: list[tuple[int, float, float]] = []
    for row in sim_rows:
        followee_id = int(row["followee_id"])
        overlap = int(row["overlap"])
        rated_overlap, avg_diff = rating_diffs.get(followee_id, (0, None))
        followee_watched = followee_watched_map.get(followee_id, 0)
        jaccard, rating_shrunk = _compute_components(
            overlap=overlap,
            me_watched=me_watched,
            followee_watched=followee_watched,
            rated_overlap=rated_overlap,
            avg_diff=avg_diff,
            cfg=similarity,
        )
        sim_components.append((followee_id, jaccard, rating_shrunk))
    jaccard_norm = _minmax([item[1] for item in sim_components])
    rating_norm = _minmax([item[2] for item in sim_components])
    for idx, (followee_id, jaccard, rating_shrunk) in enumerate(sim_components):
        sim = (jaccard_norm[idx] * rating_norm[idx]) ** 2
        sim_map[followee_id] = sim

    if similarity.normalize_top and sim_map:
        top = max(sim_map.values())
        if top > 0:
            sim_map = {k: v / top for k, v in sim_map.items()}

    film_set = set(film_ids)
    contributions: dict[int, list[dict[str, float | str]]] = {}
    current_year = datetime.now().year

    for row in rows:
        film_id = int(row["film_id"])
        if film_id not in film_set:
            continue
        followee_id = int(row["followee_id"])
        watched = int(row["watched"])
        watchlist = int(row["watchlist"])
        rating = row["rating"]
        watched_count = row["watched_count"]
        year = row["year"]

        sim_weight = sim_map.get(followee_id, similarity.default_similarity)
        interaction_weight = _interaction_weight(
            watched,
            watchlist,
            rating,
            weights,
            rating_weights,
            followee_id,
            rating_stats,
        )
        if interaction_weight == 0.0:
            continue
        time_weight = _time_weight(
            year,
            current_year=current_year,
            min_weight=weights.time_weight_min,
            window_years=weights.time_weight_years,
        )
        contribution = sim_weight * interaction_weight * time_weight
        username_val, _ = name_map.get(followee_id, (str(followee_id), None))
        film_contrib = contributions.setdefault(film_id, [])
        film_contrib.append(
            {
                "username": username_val,
                "contribution": contribution,
                "similarity": sim_weight,
                "interaction_weight": interaction_weight,
                "time_weight": time_weight,
            }
        )
    for row in watchlist_rows:
        film_id = int(row["film_id"])
        if film_id not in film_set:
            continue
        time_weight = _time_weight(
            row["year"],
            current_year=current_year,
            min_weight=weights.time_weight_min,
            window_years=weights.time_weight_years,
        )
        interaction_weight = rating_weights.unrated * rating_weights.watchlist_multiplier
        contribution = 5.0 * interaction_weight * time_weight
        film_contrib = contributions.setdefault(film_id, [])
        film_contrib.append(
            {
                "username": "watchlist",
                "contribution": contribution,
                "similarity": 5.0,
                "interaction_weight": interaction_weight,
                "time_weight": time_weight,
            }
        )

    return {
        film_id: sorted(contrib, key=lambda item: float(item["contribution"]), reverse=True)
        for film_id, contrib in contributions.items()
    }


def compute_social_contributions_normalized(
    db_path: str,
    username: str,
    film_ids: list[int],
    weights: SocialWeights | SocialConfig,
    rating_weights: SocialRatingsConfig,
    similarity: SocialSimilarityConfig,
    normalize: SocialNormalizeConfig,
) -> dict[int, list[dict[str, float | str | int | None]]]:
    if not film_ids:
        return {}

    with repo.connect(db_path) as conn:
        rows = repo.select_social_rows(conn, username)
        sim_rows = repo.select_similarity_rows(conn, username)
        me_watched = repo.select_watched_count(conn, username)
        watchlist_rows = repo.select_user_watchlist(conn, username)
        root_id = conn.execute(
            "SELECT id FROM users WHERE username = ?",
            (username,),
        ).fetchone()[0]
        followee_ids = [int(r["followee_id"]) for r in sim_rows]
        followee_watched_map = repo.select_followee_watched_counts(conn, followee_ids)
        name_map = repo.select_user_names(conn, followee_ids)
        rating_stats = repo.select_user_rating_stats(conn, [root_id] + followee_ids)
        rating_diffs = _rating_diffs(conn, root_id, followee_ids, rating_stats)

    sim_map: dict[int, float] = {}
    sim_components: list[tuple[int, float, float]] = []
    for row in sim_rows:
        followee_id = int(row["followee_id"])
        overlap = int(row["overlap"])
        rated_overlap, avg_diff = rating_diffs.get(followee_id, (0, None))
        followee_watched = followee_watched_map.get(followee_id, 0)
        jaccard, rating_shrunk = _compute_components(
            overlap=overlap,
            me_watched=me_watched,
            followee_watched=followee_watched,
            rated_overlap=rated_overlap,
            avg_diff=avg_diff,
            cfg=similarity,
        )
        sim_components.append((followee_id, jaccard, rating_shrunk))
    jaccard_norm = _minmax([item[1] for item in sim_components])
    rating_norm = _minmax([item[2] for item in sim_components])
    for idx, (followee_id, jaccard, rating_shrunk) in enumerate(sim_components):
        sim_map[followee_id] = (jaccard_norm[idx] * rating_norm[idx]) ** 2

    if similarity.normalize_top and sim_map:
        top = max(sim_map.values())
        if top > 0:
            sim_map = {k: v / top for k, v in sim_map.items()}

    current_year = datetime.now().year
    component_rows: list[dict[str, float | int | None | str]] = []
    for row in rows:
        watched = int(row["watched"])
        watchlist = int(row["watchlist"])
        rating = row["rating"]
        year = row["year"]
        followee_id = int(row["followee_id"])

        sim_weight = sim_map.get(followee_id, similarity.default_similarity)
        interaction_weight = _interaction_weight(
            watched,
            watchlist,
            rating,
            weights,
            rating_weights,
            followee_id,
            rating_stats,
        )
        if interaction_weight == 0.0:
            continue
        time_weight = _time_weight(
            year,
            current_year=current_year,
            min_weight=weights.time_weight_min,
            window_years=weights.time_weight_years,
        )
        username_val, _ = name_map.get(followee_id, (str(followee_id), None))
        component_rows.append(
            {
                "film_id": int(row["film_id"]),
                "title": row["title"],
                "year": year,
                "followee_id": followee_id,
                "username": username_val,
                "similarity": sim_weight,
                "interaction_weight": interaction_weight,
                "time_weight": time_weight,
            }
        )
    for row in watchlist_rows:
        year = row["year"]
        time_weight = _time_weight(
            year,
            current_year=current_year,
            min_weight=weights.time_weight_min,
            window_years=weights.time_weight_years,
        )
        component_rows.append(
            {
                "film_id": int(row["film_id"]),
                "title": row["title"],
                "year": year,
                "followee_id": -1,
                "username": "watchlist",
                "similarity": 5.0,
                "interaction_weight": rating_weights.unrated
                * rating_weights.watchlist_multiplier,
                "time_weight": time_weight,
            }
        )

    if not component_rows:
        return {}

    interaction_z = _zscore([float(r["interaction_weight"]) for r in component_rows])

    film_set = set(film_ids)
    contributions: dict[int, list[dict[str, float | str | int | None]]] = {}
    for idx, row in enumerate(component_rows):
        film_id = int(row["film_id"])
        if film_id not in film_set:
            continue
        score = (
            normalize.similarity_weight * float(row["similarity"])
        ) * (
            normalize.interaction_weight * interaction_z[idx]
        ) * (
            normalize.time_weight * float(row["time_weight"])
        )
        contributions.setdefault(film_id, []).append(
            {
                "username": row["username"],
                "contribution": score,
                "similarity": row["similarity"],
                "interaction_weight": row["interaction_weight"],
                "time_weight": row["time_weight"],
                "interaction_z": interaction_z[idx],
            }
        )

    return {
        film_id: sorted(contrib, key=lambda item: float(item["contribution"]), reverse=True)
        for film_id, contrib in contributions.items()
    }


def _scale(value: float, min_val: float, max_val: float, out_min: float, out_max: float) -> float:
    if max_val == min_val:
        return out_min
    ratio = (value - min_val) / (max_val - min_val)
    ratio = max(0.0, min(1.0, ratio))
    return out_min + (out_max - out_min) * ratio


def _rating_z(rating: float, stats: tuple[float, float] | None) -> float | None:
    if stats is None:
        return None
    mean, std = stats
    if std == 0.0:
        return None
    return (rating - mean) / std


def _rating_score_from_z(z: float, weights: SocialRatingsConfig, z_clip: float = 2.0) -> float:
    z = max(-z_clip, min(z_clip, z))
    if z <= 0:
        return _scale(z, -z_clip, 0.0, weights.negative_min, weights.negative_max)
    return _scale(z, 0.0, z_clip, weights.positive_min, weights.positive_max)


def _rating_diffs(
    conn,
    root_id: int,
    followee_ids: list[int],
    rating_stats: dict[int, tuple[float, float] | None],
) -> dict[int, tuple[int, float | None]]:
    diffs: dict[int, list[float]] = {fid: [] for fid in followee_ids}
    if not followee_ids:
        return {}
    shared = repo.select_shared_ratings(conn, root_id, followee_ids)
    root_stats = rating_stats.get(root_id)
    for followee_id, r1, r2 in shared:
        z1 = _rating_z(float(r1), root_stats)
        z2 = _rating_z(float(r2), rating_stats.get(int(followee_id)))
        if z1 is None or z2 is None:
            continue
        diffs[int(followee_id)].append(abs(z1 - z2))
    summary: dict[int, tuple[int, float | None]] = {}
    for followee_id, values in diffs.items():
        if values:
            summary[followee_id] = (len(values), sum(values) / len(values))
        else:
            summary[followee_id] = (0, None)
    return summary


def _rating_score(rating: float | None, weights: SocialRatingsConfig) -> float:
    if rating is None:
        return weights.unrated
    if rating <= 2.5:
        return _scale(rating, 0.5, 2.5, weights.negative_min, weights.negative_max)
    if rating >= 3.0:
        return _scale(rating, 3.0, 5.0, weights.positive_min, weights.positive_max)
    return 0.0


def _interaction_weight(
    watched: int,
    watchlist: int,
    rating: float | None,
    weights: SocialWeights | SocialConfig,
    rating_weights: SocialRatingsConfig,
    user_id: int,
    rating_stats: dict[int, tuple[float, float] | None],
) -> float:
    if watched:
        if rating is None:
            return rating_weights.unrated
        z = _rating_z(float(rating), rating_stats.get(user_id))
        if z is None:
            return _rating_score(rating, rating_weights)
        return _rating_score_from_z(z, rating_weights)
    if watchlist:
        return rating_weights.unrated * rating_weights.watchlist_multiplier
    return 0.0


def _zscore(values: list[float]) -> list[float]:
    if not values:
        return []
    mean = sum(values) / len(values)
    variance = sum((v - mean) ** 2 for v in values) / len(values)
    std = variance ** 0.5
    if std == 0:
        return [0.0 for _ in values]
    return [(v - mean) / std for v in values]


def _time_weight(
    year: int | None,
    current_year: int,
    min_weight: float,
    window_years: int,
) -> float:
    if year is None:
        return 0.75
    if year >= current_year:
        return 1.0
    age_years = max(0, current_year - year)
    half_life = max(window_years, 1)
    weight = 0.5 ** (age_years / half_life)
    return max(min_weight, weight)


def _compute_components(
    overlap: int,
    me_watched: int,
    followee_watched: int,
    rated_overlap: int,
    avg_diff: float | None,
    cfg: SocialSimilarityConfig,
) -> tuple[float, float]:
    union = me_watched + followee_watched - overlap
    jaccard = overlap / union if union > 0 else 0.0

    if rated_overlap > 0 and avg_diff is not None:
        rating_agreement = 1.0 - (float(avg_diff) / 5.0)
        rating_agreement = max(0.0, min(1.0, rating_agreement))
        rating_shrunk = (
            rated_overlap * rating_agreement + cfg.rating_k * cfg.rating_prior
        ) / (rated_overlap + cfg.rating_k)
    else:
        rating_shrunk = cfg.rating_prior

    return jaccard, rating_shrunk


def _minmax(values: list[float]) -> list[float]:
    if not values:
        return []
    min_val = min(values)
    max_val = max(values)
    span = max_val - min_val
    if span == 0:
        return [0.0 for _ in values]
    return [(v - min_val) / span for v in values]
