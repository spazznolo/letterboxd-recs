from pathlib import Path

from letterboxd_recs.ingest.letterboxd.parse import (
    is_challenge_page,
    parse_diary,
    parse_films_list,
    parse_likes_list,
    parse_profile,
    parse_watchlist,
)


FIXTURES = Path(__file__).parent / "fixtures"


def load(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def test_profile_parsing() -> None:
    html = load("profile.html")
    profile = parse_profile("spazznolo", html)
    assert profile.username == "spazznolo"
    assert profile.display_name
    assert not is_challenge_page(html)


def test_pages_not_challenge() -> None:
    for name in ("diary.html", "films.html", "likes.html", "watchlist.html"):
        html = load(name)
        assert is_challenge_page(html) is False


def test_parsers_return_lists() -> None:
    assert isinstance(parse_diary(load("diary.html")), list)
    assert isinstance(parse_films_list(load("films.html")), list)
    assert isinstance(parse_likes_list(load("likes.html")), list)
    assert isinstance(parse_watchlist(load("watchlist.html")), list)
