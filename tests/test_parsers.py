from pathlib import Path

from letterboxd_recs.availability import (
    extract_availability_csi_url,
    parse_availability_sources,
    parse_where_to_watch_flags,
)
from letterboxd_recs.ingest.letterboxd.parse import (
    is_challenge_page,
    parse_diary,
    parse_film_page,
    parse_films_list,
    parse_genres_page,
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


def test_poster_list_parses_title_and_year() -> None:
    films = parse_films_list(load("films.html"))
    assert films
    first = films[0]
    assert first.title == "The Woman in Cabin 10"
    assert first.year == 2025

    likes = parse_likes_list(load("likes.html"))
    assert likes
    first_like = likes[0]
    assert first_like.title == "Closer"
    assert first_like.year == 2004

    watchlist = parse_watchlist(load("watchlist.html"))
    assert watchlist
    first_watchlist = watchlist[0]
    assert first_watchlist.title == "The Chronology of Water"
    assert first_watchlist.year == 2025


def test_film_page_parsing() -> None:
    html = load("film_page.html")
    title, year, genres = parse_film_page(html)
    assert title == "Example Film"
    assert year == 2019
    assert genres == ["Drama", "Comedy"]


def test_genres_page_parsing() -> None:
    html = load("genres.html")
    genres = parse_genres_page(html)
    assert genres == ["Action", "War", "Drama", "History"]


def test_where_to_watch_parsing() -> None:
    html = load("where_to_watch.html")
    source_flags, has_stream = parse_availability_sources(html)
    providers = parse_where_to_watch_flags(html)
    assert source_flags["netflix"] is True
    assert source_flags["apple_itunes"] is True
    assert source_flags["amazon"] is False
    assert "physical_disc" not in source_flags
    assert has_stream is True
    assert "netflix" in providers
    assert "apple_itunes" in providers
    assert "amazon" not in providers


def test_csi_availability_url_and_source_provider_mapping() -> None:
    html = """
    <div class="loading-csi"
         data-src="/csi/film/the-batman/availability/?esiAllowUser=true&amp;esiAllowCountry=true">
    </div>
    """
    csi_url = extract_availability_csi_url(html)
    assert csi_url == (
        "https://letterboxd.com/csi/film/the-batman/availability/"
        "?esiAllowUser=true&esiAllowCountry=true"
    )

    csi_html = """
    <section class="services">
      <p id="source-netflix" class="service -netflix">
        <span class="options"><a class="link -stream"><span class="extended">Stream</span></a></span>
      </p>
      <p id="source-amazonprimevideo" class="service -amazonprimevideo">
        <span class="options"><a class="link -rent"><span class="extended">Rent</span></a></span>
      </p>
    </section>
    """
    flags, has_stream = parse_availability_sources(csi_html)
    assert flags["netflix"] is True
    assert flags["prime_video"] is True
    assert has_stream is True
