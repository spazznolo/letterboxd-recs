from types import SimpleNamespace

from letterboxd_recs import cli
from letterboxd_recs.db import repo
from letterboxd_recs.db.conn import ensure_db


def test_refresh_similarity_pool_uses_shallow_ingest_and_skips_failures(
    tmp_path, monkeypatch
) -> None:
    db_path = tmp_path / "test.sqlite"
    ensure_db(str(db_path))

    with repo.connect(str(db_path)) as conn:
        repo.ensure_user(conn, "base-user")
        conn.commit()

    cfg = SimpleNamespace(
        database_path=str(db_path),
        social_similarity=SimpleNamespace(),
    )
    scores = [SimpleNamespace(username="base-user", similarity=1.0)]
    followees = iter(
        [
            SimpleNamespace(
                username="blocked-user",
                display_name="Blocked User",
                followers=10,
                following=10,
                watched=10,
            ),
            SimpleNamespace(
                username="good-user",
                display_name="Good User",
                followers=10,
                following=10,
                watched=10,
            ),
        ]
    )
    ingest_calls: list[tuple[str, bool]] = []

    monkeypatch.setattr(cli, "compute_similarity_scores", lambda *args, **kwargs: scores)
    monkeypatch.setattr(cli, "_random_followee", lambda username, cfg: next(followees, None))

    def fake_ingest_user(username, cfg, refresh, **kwargs):
        ingest_calls.append((username, refresh))
        if username == "blocked-user":
            raise RuntimeError("blocked")
        return SimpleNamespace()

    monkeypatch.setattr(cli, "ingest_user", fake_ingest_user)

    added = cli._refresh_similarity_pool(
        cfg,
        username="root",
        sample_count=1,
        base_user_limit=1,
    )

    assert added == ["good-user"]
    assert ingest_calls == [
        ("blocked-user", True),
        ("good-user", True),
    ]

