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


def test_export_html_preserves_raw_scores_in_payload(tmp_path, monkeypatch) -> None:
    out_path = tmp_path / "index.html"

    cfg = SimpleNamespace(database_path=str(tmp_path / "test.sqlite"))
    results = [
        SimpleNamespace(
            film_id=1,
            title="Movie A",
            year=2020,
            genres="Drama",
            score=0.912345,
        ),
    ]

    monkeypatch.setattr(cli, "load_config", lambda: cfg)
    monkeypatch.setattr(cli, "ensure_db", lambda path: None)
    monkeypatch.setattr(cli, "_base_recommendations", lambda *args, **kwargs: results)
    monkeypatch.setattr(
        cli.repo,
        "connect",
        lambda path: _FakeConn(),
    )
    monkeypatch.setattr(
        cli.repo,
        "select_film_slugs",
        lambda conn, film_ids: {1: "movie-a"},
    )
    monkeypatch.setattr(
        cli.repo,
        "select_availability_map",
        lambda conn, film_ids, columns: {1: {"stream": True, "netflix": True}},
    )

    cli._export_html("spazznolo", limit=1, out=str(out_path))
    payload = _extract_payload(out_path)

    assert payload["films"][0]["score"] == 0.912345
    assert payload["films"][0]["score_scaled"] == 0.912345


def test_export_html_includes_sortable_rank_and_movement_controls(tmp_path) -> None:
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
                current_rank=1,
                previous_rank=3,
                rank_change=2,
            ),
        ],
        ["netflix"],
        out_path,
    )

    html = out_path.read_text(encoding="utf-8")

    assert 'id="sort-rank"' in html
    assert 'id="sort-movement"' in html
    assert 'let sortKey = "rank";' in html
    assert 'let sortDirection = "asc";' in html
    assert "sortKey === \"movement\"" in html
    assert "sortDirection = sortDirection === \"asc\" ? \"desc\" : \"asc\";" in html


def test_export_html_does_not_clamp_scores_to_zero_to_ten(tmp_path) -> None:
    out_path = tmp_path / "index.html"

    cli.render_recs_html(
        "spazznolo",
        [
            cli.ExportFilm(
                title="Movie A",
                year=2020,
                genres=["Drama"],
                score=18.23687,
                score_scaled=18.23687,
                letterboxd_url="https://letterboxd.com/film/movie-a/",
                providers={"netflix": True},
                stream=True,
                current_rank=1,
            ),
        ],
        ["netflix"],
        out_path,
    )

    html = out_path.read_text(encoding="utf-8")

    assert "Math.max(0, Math.min(10" not in html


def test_weekly_exports_top_5000_movies(monkeypatch) -> None:
    called: dict[str, int] = {}
    cfg = SimpleNamespace(database_path="ignored.sqlite")

    monkeypatch.setattr(cli, "load_config", lambda: cfg)
    monkeypatch.setattr(cli, "ensure_db", lambda path: None)
    monkeypatch.setattr(cli, "_refresh_similar_users", lambda *args, **kwargs: (0, 0))
    monkeypatch.setattr(cli, "_refresh_similarity_pool", lambda *args, **kwargs: [])
    monkeypatch.setattr(cli, "_update_top_availability", lambda *args, **kwargs: (0, 0))

    def _fake_export_html(username, limit, out, similar_user_limit=100):
        called["limit"] = limit

    monkeypatch.setattr(cli, "_export_html", _fake_export_html)

    cli.weekly()

    assert called["limit"] == 5000
