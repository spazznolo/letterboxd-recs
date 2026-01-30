from pathlib import Path

from letterboxd_recs.ingest.letterboxd.social import parse_following, parse_following_entries
from letterboxd_recs.ingest.letterboxd.parse import parse_next_page


def test_parse_following() -> None:
    html = (
        '<ul>'
        '<li><a class="avatar" href="/alice/"></a></li>'
        '<li><a class="avatar" href="/bob/"></a></li>'
        '</ul>'
    )
    assert parse_following(html) == ["alice", "bob"]


def test_following_pagination_fixture(tmp_path) -> None:
    html = (
        '<ul class="person-list">'
        '<li><a class="avatar" href="/carol/"></a></li>'
        '</ul>'
        '<a class="next" href="/spazznolo/following/page/2/"></a>'
    )
    assert parse_next_page(html) == "/spazznolo/following/page/2/"


def test_parse_following_entries_fixture() -> None:
    html = (Path(__file__).parent / "fixtures" / "following_rows.html").read_text(encoding="utf-8")
    entries = parse_following_entries(html)
    assert len(entries) == 2
    assert entries[0].username == "forssam"
    assert entries[0].display_name == "Sam Forstner"
    assert entries[0].followers == 10
    assert entries[0].following == 14
    assert entries[0].watched == 747
