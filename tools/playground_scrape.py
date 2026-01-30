from __future__ import annotations

from pprint import pprint

from letterboxd_recs.ingest.letterboxd.browser import fetch_html
from letterboxd_recs.ingest.letterboxd.parse import is_challenge_page, parse_film_page, parse_genres_page


def main() -> None:
    slug = "columbus-2017"
    film_url = f"https://letterboxd.com/film/{slug}/"
    genres_url = f"https://letterboxd.com/film/{slug}/genres/"

    film_html = fetch_html(film_url, user_agent="letterboxd-recs/0.1").content
    genres_html = fetch_html(genres_url, user_agent="letterboxd-recs/0.1").content

    title, year, genres_from_film = parse_film_page(film_html)
    genres_from_genres = parse_genres_page(genres_html)

    print("film_url:", film_url)
    print("genres_url:", genres_url)
    print("film_page_challenge:", is_challenge_page(film_html))
    print("genres_page_challenge:", is_challenge_page(genres_html))
    print("title:", title)
    print("year:", year)
    print("genres_from_film:")
    pprint(genres_from_film)
    print("genres_from_genres:")
    pprint(genres_from_genres)


if __name__ == "__main__":
    main()
