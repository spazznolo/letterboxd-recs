import json
import re
from pathlib import Path
from types import SimpleNamespace

from letterboxd_recs import cli


def _extract_payload(out_path: Path) -> dict:
    html = out_path.read_text(encoding="utf-8")
    match = re.search(
        r'<script id="recs-data" type="application/json">(.*?)</script>',
        html,
        re.DOTALL,
    )
    assert match is not None
    return json.loads(match.group(1))


class _FakeConn:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return None


def test_export_html_includes_movement_from_previous_publish(
    tmp_path, monkeypatch
) -> None:
    out_path = tmp_path / "index.html"
    cli.render_recs_html(
        "spazznolo",
        [
            cli.ExportFilm(
                title="Movie A",
                year=2020,
                genres=["Drama"],
                score=1.0,
                score_scaled=8.5,
                letterboxd_url="https://letterboxd.com/film/movie-a/",
                providers={"netflix": True},
                stream=True,
            ),
            cli.ExportFilm(
                title="Movie B",
                year=2021,
                genres=["Comedy"],
                score=0.9,
                score_scaled=7.0,
                letterboxd_url="https://letterboxd.com/film/movie-b/",
                providers={"netflix": False},
                stream=False,
            ),
        ],
        ["netflix"],
        out_path,
    )

    cfg = SimpleNamespace(database_path=str(tmp_path / "test.sqlite"))
    results = [
        SimpleNamespace(
            film_id=2,
            title="Movie B",
            year=2021,
            genres="Comedy",
            score=0.9,
        ),
        SimpleNamespace(
            film_id=1,
            title="Movie A",
            year=2020,
            genres="Drama",
            score=0.8,
        ),
        SimpleNamespace(
            film_id=3,
            title="Movie C",
            year=2022,
            genres="Sci-Fi",
            score=0.7,
        ),
    ]

    monkeypatch.setattr(cli, "load_config", lambda: cfg)
    monkeypatch.setattr(cli, "ensure_db", lambda path: None)
    monkeypatch.setattr(cli, "_base_recommendations", lambda *args, **kwargs: results)
    monkeypatch.setattr(
        cli,
        "_scaled_scores",
        lambda _results: {2: 9.0, 1: 8.0, 3: 7.0},
    )
    monkeypatch.setattr(
        cli.repo,
        "connect",
        lambda path: _FakeConn(),
    )
    monkeypatch.setattr(
        cli.repo,
        "select_film_slugs",
        lambda conn, film_ids: {
            1: "movie-a",
            2: "movie-b",
            3: "movie-c",
        },
    )
    monkeypatch.setattr(
        cli.repo,
        "select_availability_map",
        lambda conn, film_ids, columns: {
            1: {"stream": True, "netflix": True},
            2: {"stream": False, "netflix": False},
            3: {"stream": True, "netflix": True},
        },
    )

    cli._export_html("spazznolo", limit=3, out=str(out_path))
    payload = _extract_payload(out_path)

    assert "Movement" in out_path.read_text(encoding="utf-8")
    assert [film["title"] for film in payload["films"]] == ["Movie B", "Movie A", "Movie C"]
    assert payload["films"][0]["previous_rank"] == 2
    assert payload["films"][0]["rank_change"] == 1
    assert payload["films"][1]["previous_rank"] == 1
    assert payload["films"][1]["rank_change"] == -1
    assert payload["films"][2]["previous_rank"] is None
    assert payload["films"][2]["rank_change"] is None
