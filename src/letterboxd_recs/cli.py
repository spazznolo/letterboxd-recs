import typer
from rich.console import Console

from letterboxd_recs.config import load_config
from letterboxd_recs.db import repo
from letterboxd_recs.db.conn import ensure_db
from letterboxd_recs.ingest.letterboxd.ingest import ingest_user
from letterboxd_recs.graph.ingest import ingest_follow_graph
from letterboxd_recs.models.social_simple import compute_social_scores, compute_similarity_scores

app = typer.Typer(add_completion=False)
console = Console()


@app.command()
def ingest(
    username: str,
    refresh: bool = False,
    max_depth: int | None = None,
    graph: bool = True,
    graph_interactions: bool = False,
    graph_only: bool = False,
) -> None:
    """Ingest Letterboxd profile data for a user."""
    cfg = load_config()
    ensure_db(cfg.database_path)
    if not graph_only:
        console.print(f"Ingesting user: {username} (refresh={refresh})")
        result = ingest_user(username, cfg, refresh=refresh)
        console.print(
            f"Ingested: watched={result.films_seen} liked={result.likes} watchlist={result.watchlist}"
        )
    if graph:
        console.print("Ingesting follow graph...")
        graph_result = ingest_follow_graph(
            username,
            cfg,
            refresh=refresh,
            max_depth=max_depth,
            ingest_interactions=graph_interactions,
        )
        console.print(f"Graph: nodes={graph_result.nodes} edges={graph_result.edges}")


@app.command()
def ingest_user_only(
    username: str,
    refresh: bool = False,
    include_diary: bool = False,
    include_films: bool = True,
    include_likes: bool = False,
    include_watchlist: bool = True,
) -> None:
    """Ingest only the user's interactions (no graph edges)."""
    cfg = load_config()
    ensure_db(cfg.database_path)
    console.print(f"Ingesting interactions for: {username} (refresh={refresh})")
    result = ingest_user(
        username,
        cfg,
        refresh=refresh,
        include_diary=include_diary,
        include_films=include_films,
        include_likes=include_likes,
        include_watchlist=include_watchlist,
    )
    console.print(
        f"Ingested: watched={result.films_seen} liked={result.likes} watchlist={result.watchlist}"
    )


@app.command()
def refresh(username: str, availability: bool = False) -> None:
    """Refresh selected data for a user."""
    cfg = load_config()
    ensure_db(cfg.database_path)
    console.print(f"Refreshing user: {username} (availability={availability})")
    console.print("Refresh not implemented yet. This is a scaffold.")


@app.command()
def recommend(
    username: str,
    sort: str = "desc",
    genre: str | None = None,
    min_year: int | None = None,
    recommend_ten: bool = False,
    social_only: bool = True,
    limit: int = 50,
    explain_top: int = 0,
    contributors: int = 5,
) -> None:
    """Generate recommendations for a user."""
    cfg = load_config()
    ensure_db(cfg.database_path)
    console.print(f"Recommending for: {username} (sort={sort})")
    if social_only:
        results = compute_social_scores(
            cfg.database_path,
            username,
            weights=cfg.social,
            rating_weights=cfg.social_ratings,
            similarity=cfg.social_similarity,
            normalize=cfg.social_normalize,
            limit=None,
        )
        sort_val = sort.lower()
        if sort_val in ("asc", "ascending", "low", "bottom"):
            results = sorted(results, key=lambda item: item.score)
        else:
            results = sorted(results, key=lambda item: item.score, reverse=True)
        display_rank = 0
        genre_filter = genre.lower() if genre else None
        if results:
            all_scores = [item.score for item in results]
            min_score = min(all_scores)
            max_score = max(all_scores)
            score_range = max_score - min_score
        else:
            min_score = 0.0
            score_range = 0.0
        filtered: list = []
        for item in results:
            if min_year is not None and (item.year is None or item.year < min_year):
                continue
            if genre_filter:
                genres_val = (item.genres or "").lower()
                if genre_filter not in genres_val:
                    continue
            filtered.append(item)
        if recommend_ten:
            import random

            candidates = filtered[:]
            if not candidates:
                return
            weights = [max(0.0, item.score) for item in candidates]
            if all(w == 0 for w in weights):
                weights = [1.0 for _ in candidates]
            chosen = []
            for _ in range(min(10, len(candidates))):
                total = sum(weights)
                r = random.random() * total
                upto = 0.0
                idx = 0
                for i, w in enumerate(weights):
                    upto += w
                    if upto >= r:
                        idx = i
                        break
                chosen.append(candidates.pop(idx))
                weights.pop(idx)
            filtered = chosen
        for item in filtered[:limit]:
            display_rank += 1
            if score_range > 0:
                scaled_score = (item.score - min_score) / score_range
            else:
                scaled_score = 0.0
            scaled_score *= 10
            year = f" ({item.year})" if item.year else ""
            genres = f" [{item.genres}]" if item.genres else ""
            console.print(f"{display_rank:>3}. {scaled_score:.2f}  {item.title}{year}{genres}")
        if explain_top > 0:
            from letterboxd_recs.models.social_simple import (
                compute_social_contributions,
                compute_social_contributions_normalized,
            )

            explain_ids = [item.film_id for item in results[:explain_top]]
            if cfg.social_normalize.enabled:
                contrib = compute_social_contributions_normalized(
                    cfg.database_path,
                    username,
                    explain_ids,
                    cfg.social,
                    cfg.social_ratings,
                    cfg.social_similarity,
                    cfg.social_normalize,
                )
            else:
                contrib = compute_social_contributions(
                    cfg.database_path,
                    username,
                    explain_ids,
                    cfg.social,
                    cfg.social_ratings,
                    cfg.social_similarity,
                )
            for item in results[:explain_top]:
                console.print(f"\nTop contributors for {item.title}:")
                entries = contrib.get(item.film_id, [])
                if cfg.social_normalize.enabled:
                    console.print(
                        "  score    user           "
                        "sim        inter (z)    time"
                    )
                    for entry in entries[:contributors]:
                        console.print(
                            f"  {entry['contribution']:+7.4f}  {entry['username']:<14} "
                            f"{entry['similarity']:.4f}  "
                            f"{entry['interaction_weight']:.4f} ({entry['interaction_z']:+.3f})  "
                            f"{entry['time_weight']:.4f}"
                        )
                else:
                    for entry in entries[:contributors]:
                        console.print(
                            f"  {entry['contribution']:.4f}  {entry['username']}"
                        )
        return
    console.print("Recommender not implemented yet beyond social_only.")


@app.command()
def status(username: str) -> None:
    """Show ingestion status for a user."""
    cfg = load_config()
    ensure_db(cfg.database_path)
    console.print(f"Status for: {username}")
    console.print("Status not implemented yet. This is a scaffold.")


@app.command()
def similarities(username: str, limit: int = 25, normalize_top: bool = True) -> None:
    """Print followee similarity scores for a user."""
    cfg = load_config()
    ensure_db(cfg.database_path)
    scores = compute_similarity_scores(
        cfg.database_path,
        username,
        similarity=cfg.social_similarity,
        normalize_top=normalize_top,
    )
    console.print(f"Similarities for: {username}")
    for entry in scores[:limit]:
        name = entry.display_name or entry.username
        avg_diff = f"{entry.avg_diff:.2f}" if entry.avg_diff is not None else "-"
        console.print(
            f"{entry.similarity:.3f}  {name} ({entry.username})  "
            f"j_norm={entry.jaccard:.3f} r_norm={entry.rating_similarity:.3f} "
            f"overlap={entry.overlap} rated={entry.rated_overlap} avg_diff={avg_diff}"
        )


@app.command()
def similarity_explain(username: str, followee: str, limit: int = 10) -> None:
    """Explain similarity between two users using rating z-scores."""
    cfg = load_config()
    ensure_db(cfg.database_path)
    with repo.connect(cfg.database_path) as conn:
        root_id = conn.execute(
            "SELECT id FROM users WHERE username = ?",
            (username,),
        ).fetchone()
        followee_id = conn.execute(
            "SELECT id FROM users WHERE username = ?",
            (followee,),
        ).fetchone()
        if not root_id or not followee_id:
            console.print("User not found.")
            return
        root_id = root_id[0]
        followee_id = followee_id[0]
        rating_stats = repo.select_user_rating_stats(conn, [root_id, followee_id])
        shared = repo.select_shared_rated_films(conn, root_id, followee_id)

    root_stats = rating_stats.get(root_id)
    followee_stats = rating_stats.get(followee_id)
    if not shared:
        console.print("No shared rated films.")
        return

    def zscore(rating: float, stats: tuple[float, float] | None):
        if not stats:
            return None
        mean, std = stats
        if std == 0:
            return None
        return (rating - mean) / std

    disagreements = []
    for title, year, r1, r2 in shared:
        z1 = zscore(r1, root_stats)
        z2 = zscore(r2, followee_stats)
        if z1 is None or z2 is None:
            continue
        disagreements.append((abs(z1 - z2), title, year, r1, r2, z1, z2))

    if not disagreements:
        console.print("Not enough rating data to compute z-score disagreements.")
        return

    disagreements.sort(key=lambda x: x[0], reverse=True)
    console.print(
        f"Top {min(limit, len(disagreements))} disagreements (z-score) "
        f"between {username} and {followee}:"
    )
    for diff, title, year, r1, r2, z1, z2 in disagreements[:limit]:
        year_str = f" ({year})" if year else ""
        console.print(
            f"{diff:.2f}  {title}{year_str}  "
            f"{username}={r1:.1f} (z={z1:+.2f})  {followee}={r2:.1f} (z={z2:+.2f})"
        )
