from pathlib import Path

import math
import random
import typer
from rich.console import Console

from letterboxd_recs.availability import (
    CARED_PROVIDER_COLUMNS,
    extract_availability_csi_url,
    parse_availability_sources,
    provider_column_from_arg,
)
from letterboxd_recs.config import load_config
from letterboxd_recs.db import repo
from letterboxd_recs.db.conn import ensure_db
from letterboxd_recs.export.html import ExportFilm, render_recs_html
from letterboxd_recs.ingest.letterboxd.browser import fetch_html as browser_fetch
from letterboxd_recs.ingest.letterboxd.ingest import ingest_user
from letterboxd_recs.ingest.letterboxd.social import parse_following_entries
from letterboxd_recs.graph.ingest import ingest_follow_graph
from letterboxd_recs.models.social_simple import compute_social_scores, compute_similarity_scores
from letterboxd_recs.util.retry import retry

app = typer.Typer(add_completion=False)
console = Console()


def _sort_results(results, sort: str):
    sort_val = sort.lower()
    if sort_val in ("asc", "ascending", "low", "bottom"):
        return sorted(results, key=lambda item: item.score)
    return sorted(results, key=lambda item: item.score, reverse=True)


def _base_recommendations(cfg, username: str, sort: str):
    results = compute_social_scores(
        cfg.database_path,
        username,
        weights=cfg.social,
        rating_weights=cfg.social_ratings,
        similarity=cfg.social_similarity,
        normalize=cfg.social_normalize,
        limit=None,
    )
    return _sort_results(results, sort)


def _refresh_all_users(cfg) -> tuple[int, int]:
    with repo.connect(cfg.database_path) as conn:
        usernames = repo.select_all_usernames(conn)
    ok = 0
    failed = 0
    for username in usernames:
        try:
            ingest_user(
                username,
                cfg,
                refresh=True,
                include_diary=False,
                include_films=True,
                include_likes=False,
                include_watchlist=True,
            )
            ok += 1
        except Exception as exc:  # noqa: BLE001
            failed += 1
            console.print(f"[red]Refresh failed for {username}: {exc}[/red]")
    return ok, failed


def _update_top_availability(cfg, username: str, top_n: int = 100) -> tuple[int, int]:
    ranked = _base_recommendations(cfg, username, sort="desc")
    top = ranked[:top_n]
    if not top:
        return 0, 0
    with repo.connect(cfg.database_path) as conn:
        slugs = repo.select_film_slugs(conn, [r.film_id for r in top])
        updated = 0
        skipped = 0
        for item in top:
            slug = slugs.get(item.film_id)
            if not slug:
                skipped += 1
                continue
            url = f"https://letterboxd.com/film/{slug}/"
            html = browser_fetch(url, user_agent=cfg.app.user_agent).content
            source_flags: dict[str, bool] = {}
            base_flags, has_stream = parse_availability_sources(html)
            source_flags.update(base_flags)
            csi_url = extract_availability_csi_url(html)
            if csi_url:
                csi_html = browser_fetch(csi_url, user_agent=cfg.app.user_agent).content
                csi_flags, csi_has_stream = parse_availability_sources(csi_html)
                has_stream = has_stream or csi_has_stream
                for key, val in csi_flags.items():
                    source_flags[key] = source_flags.get(key, False) or val
            repo.upsert_film_availability_flags(
                conn,
                item.film_id,
                cfg.app.region,
                source_flags,
                has_stream=has_stream,
            )
            updated += 1
        conn.commit()
    return updated, skipped


def _scaled_scores(results):
    if not results:
        return {}
    scores = [item.score for item in results]
    min_score = min(scores)
    max_score = max(scores)
    span = max_score - min_score
    scaled = {}
    for item in results:
        if span > 0:
            value = (item.score - min_score) / span
        else:
            value = 0.0
        scaled[item.film_id] = value * 10.0
    return scaled


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
def ingest_interactions(
    username: str,
    refresh: bool = False,
    include_likes: bool = False,
) -> None:
    """Ingest a user's watched/watchlist interactions only (no graph)."""
    cfg = load_config()
    ensure_db(cfg.database_path)
    console.print(f"Ingesting interactions for: {username} (refresh={refresh})")
    result = ingest_user(
        username,
        cfg,
        refresh=refresh,
        include_diary=False,
        include_films=True,
        include_likes=include_likes,
        include_watchlist=True,
    )
    console.print(
        f"Ingested: watched={result.films_seen} liked={result.likes} watchlist={result.watchlist}"
    )


@app.command()
def graph_ingest(
    username: str,
    max_depth: int = 1,
    ingest_missing_interactions: bool = True,
) -> None:
    """Ingest follow graph and (optionally) scrape missing followee interactions."""
    cfg = load_config()
    ensure_db(cfg.database_path)
    console.print(f"Ingesting follow graph for: {username} (max_depth={max_depth})")
    graph_result = ingest_follow_graph(
        username,
        cfg,
        refresh=False,
        max_depth=max_depth,
        ingest_interactions=False,
    )
    console.print(f"Graph: nodes={graph_result.nodes} edges={graph_result.edges}")
    if not ingest_missing_interactions:
        return
    with repo.connect(cfg.database_path) as conn:
        missing = repo.select_missing_followees(conn, username, 100, 100)
    if not missing:
        console.print("No missing followees to ingest.")
        return
    console.print(f"Ingesting interactions for {len(missing)} missing followees...")
    ok = 0
    failed = 0
    for followee in missing:
        try:
            ingest_user(
                followee,
                cfg,
                refresh=False,
                include_diary=False,
                include_films=True,
                include_likes=False,
                include_watchlist=True,
            )
            ok += 1
        except Exception as exc:  # noqa: BLE001
            failed += 1
            console.print(f"[red]Failed {followee}: {exc}[/red]")
    console.print(f"Graph interaction ingest complete: ok={ok} failed={failed}")


@app.command()
def refresh() -> None:
    """Refresh first page of watched/watchlist for every user in DB."""
    cfg = load_config()
    ensure_db(cfg.database_path)
    ok, failed = _refresh_all_users(cfg)
    console.print(f"Refresh complete: ok={ok} failed={failed}")


@app.command()
def update_availability(username: str = "spazznolo", top_n: int = 100) -> None:
    """Scrape where-to-watch providers for the top-N recommended films."""
    cfg = load_config()
    ensure_db(cfg.database_path)
    updated, skipped = _update_top_availability(cfg, username=username, top_n=top_n)
    console.print(
        f"Availability update complete: updated={updated} skipped_without_slug={skipped}"
    )


@app.command()
def weekly(username: str = "spazznolo", top_n: int = 100) -> None:
    """Weekly pipeline: refresh all users, then update top-N availability."""
    cfg = load_config()
    ensure_db(cfg.database_path)
    ok, failed = _refresh_all_users(cfg)
    console.print(f"Refresh complete: ok={ok} failed={failed}")
    added_users = _refresh_similarity_pool(cfg, username, sample_count=10)
    if added_users:
        console.print(f"Similarity pool: added={len(added_users)} -> {', '.join(added_users)}")
    else:
        console.print("Similarity pool: added=0")
    updated, skipped = _update_top_availability(cfg, username=username, top_n=top_n)
    console.print(
        f"Availability update complete: updated={updated} skipped_without_slug={skipped}"
    )
    _export_html(username=username, limit=500, out="docs/index.html")


@app.command()
def recommend(
    username: str,
    sort: str = "desc",
    genre: str | None = None,
    provider: str | None = None,
    stream: bool = False,
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
        results = _base_recommendations(cfg, username, sort=sort)
        display_rank = 0
        genre_filter = genre.lower() if genre else None
        provider_column = provider_column_from_arg(provider) if provider else None
        if provider and provider_column is None:
            console.print(f"[red]Unknown provider: {provider}[/red]")
            raise typer.Exit(code=2)
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
        if provider_column or stream:
            with repo.connect(cfg.database_path) as conn:
                film_ids = [item.film_id for item in filtered]
                available_sets: list[set[int]] = []
                if provider_column:
                    try:
                        available_sets.append(
                            repo.select_available_film_ids(
                                conn,
                                film_ids,
                                provider_column=provider_column,
                                region=cfg.app.region,
                            )
                        )
                    except ValueError:
                        console.print(
                            f"[yellow]Provider column not found yet: {provider_column}[/yellow]"
                        )
                        available_sets.append(set())
                if stream:
                    available_sets.append(
                        repo.select_available_film_ids(
                            conn,
                            film_ids,
                            provider_column="stream",
                            region=cfg.app.region,
                        )
                    )
            if available_sets:
                allowed = available_sets[0]
                for subset in available_sets[1:]:
                    allowed = allowed.intersection(subset)
                filtered = [item for item in filtered if item.film_id in allowed]
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
def export_html(
    username: str,
    limit: int = 500,
    out: str = "docs/index.html",
) -> None:
    """Export static HTML recommendations for GitHub Pages."""
    _export_html(username=username, limit=limit, out=out)


def _export_html(username: str, limit: int, out: str) -> None:
    cfg = load_config()
    ensure_db(cfg.database_path)
    results = _base_recommendations(cfg, username, sort="desc")
    if not results:
        console.print("[yellow]No recommendations to export.[/yellow]")
        return
    results = results[:limit]
    scaled_scores = _scaled_scores(results)
    film_ids = [item.film_id for item in results]
    provider_columns = list(CARED_PROVIDER_COLUMNS)
    with repo.connect(cfg.database_path) as conn:
        slug_map = repo.select_film_slugs(conn, film_ids)
        availability = repo.select_availability_map(
            conn,
            film_ids,
            ["stream"] + provider_columns,
        )
    films: list[ExportFilm] = []
    for item in results:
        slug = slug_map.get(item.film_id)
        letterboxd_url = f"https://letterboxd.com/film/{slug}/" if slug else None
        flags = availability.get(item.film_id, {})
        stream_flag = bool(flags.get("stream", False))
        provider_flags = {col: bool(flags.get(col, False)) for col in provider_columns}
        genres = [g.strip() for g in (item.genres or "").split(",") if g.strip()]
        films.append(
            ExportFilm(
                title=item.title,
                year=item.year,
                genres=genres,
                score=item.score,
                score_scaled=scaled_scores.get(item.film_id, 0.0),
                letterboxd_url=letterboxd_url,
                providers=provider_flags,
                stream=stream_flag,
            )
        )
    render_recs_html(username, films, provider_columns, Path(out))
    console.print(f"Exported {len(films)} films to {out}")


def _refresh_similarity_pool(
    cfg,
    username: str,
    sample_count: int = 10,
) -> list[str]:
    scores = compute_similarity_scores(
        cfg.database_path,
        username,
        similarity=cfg.social_similarity,
        normalize_top=False,
    )
    if not scores:
        return []

    remaining = list(scores)
    if not remaining:
        return []

    weights = [max(0.0, s.similarity) for s in remaining]
    if all(w == 0 for w in weights):
        weights = [1.0 for _ in remaining]

    added = 0
    added_usernames: list[str] = []
    attempts = 0
    max_attempts = sample_count * 6
    while added < sample_count and attempts < max_attempts:
        attempts += 1
        base = random.choices(remaining, weights=weights, k=1)[0]
        followee = _random_followee(base.username, cfg)
        if not followee:
            continue
        with repo.connect(cfg.database_path) as conn:
            if repo.select_user_id(conn, followee.username):
                continue
            src_id = repo.ensure_user(conn, base.username)
            dst_id = repo.upsert_user_stats(
                conn,
                followee.username,
                followee.display_name,
                followee.followers,
                followee.following,
                followee.watched,
            )
            repo.upsert_graph_edge(conn, src_id, dst_id, 1)
            conn.commit()
        try:
            ingest_user(
                followee.username,
                cfg,
                refresh=False,
                include_diary=False,
                include_films=True,
                include_likes=False,
                include_watchlist=True,
            )
            added += 1
            added_usernames.append(followee.username)
        except Exception as exc:  # noqa: BLE001
            console.print(f"[yellow]Failed ingest for {followee.username}: {exc}[/yellow]")

    return added_usernames


def _random_followee(username: str, cfg):
    with repo.connect(cfg.database_path) as conn:
        following_count = repo.select_following_count(conn, username)
    pages = max(1, math.ceil(following_count / 10)) if following_count > 0 else 1
    page = random.randint(1, pages)
    if page == 1:
        url = f"https://letterboxd.com/{username}/following/"
    else:
        url = f"https://letterboxd.com/{username}/following/page/{page}/"
    def fetch_entries():
        html = browser_fetch(url, user_agent=cfg.app.user_agent).content
        return parse_following_entries(html)

    def on_error(exc: Exception, attempt: int) -> None:
        console.print(f"[yellow]Retry {attempt} for followees of {username}: {exc}[/yellow]")

    entries = retry(fetch_entries, attempts=3, delay_seconds=2.0, on_error=on_error)
    if not entries:
        return None
    return random.choice(entries)


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
