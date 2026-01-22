import typer
from rich.console import Console

from letterboxd_recs.config import load_config
from letterboxd_recs.db.conn import ensure_db
from letterboxd_recs.ingest.letterboxd.ingest import ingest_user

app = typer.Typer(add_completion=False)
console = Console()


@app.command()
def ingest(username: str, refresh: bool = False) -> None:
    """Ingest Letterboxd profile data for a user."""
    cfg = load_config()
    ensure_db(cfg.database_path)
    console.print(f"Ingesting user: {username} (refresh={refresh})")
    result = ingest_user(username, cfg, refresh=refresh)
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
def recommend(username: str, sort: str = "score", min_score: float = 0.0) -> None:
    """Generate recommendations for a user."""
    cfg = load_config()
    ensure_db(cfg.database_path)
    console.print(f"Recommending for: {username} (sort={sort}, min_score={min_score})")
    console.print("Recommender not implemented yet. This is a scaffold.")


@app.command()
def status(username: str) -> None:
    """Show ingestion status for a user."""
    cfg = load_config()
    ensure_db(cfg.database_path)
    console.print(f"Status for: {username}")
    console.print("Status not implemented yet. This is a scaffold.")
