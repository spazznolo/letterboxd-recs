from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from bs4 import BeautifulSoup


@dataclass(frozen=True)
class FilmItem:
    slug: str
    title: str | None
    year: int | None
    rating: float | None
    liked: bool
    watched: bool
    watch_date: str | None
    watchlist: bool


@dataclass(frozen=True)
class Profile:
    username: str
    display_name: str | None


def parse_profile(username: str, html: str) -> Profile:
    soup = BeautifulSoup(html, "lxml")
    display = None
    header = soup.select_one("h1.title-2") or soup.select_one("h1.profile-name")
    if header:
        display = header.get_text(strip=True) or None
    return Profile(username=username, display_name=display)


def is_challenge_page(html: str) -> bool:
    markers = (
        "Just a moment...",
        "cf_chl_opt",
        "cf_chl",
        "Enable JavaScript and cookies to continue",
        "/cdn-cgi/challenge-platform/h/b/orchestrate",
    )
    return any(marker in html for marker in markers)


def parse_diary(html: str) -> list[FilmItem]:
    soup = BeautifulSoup(html, "lxml")
    items: list[FilmItem] = []
    for row in soup.select("tr.diary-entry-row"):
        slug = _attr(row, "data-film-slug") or _find_poster_slug(row)
        if not slug:
            continue
        title = _attr(row, "data-film-name")
        year = _to_int(_attr(row, "data-film-year"))
        rating_text = None
        rating_cell = row.select_one("td.col-rating span.rating")
        if rating_cell:
            rating_text = rating_cell.get_text(strip=True)
        rating = _parse_star_rating(rating_text)
        liked = row.select_one("span.like") is not None or "liked" in row.get("class", [])
        watch_date = None
        date_cell = row.select_one("td.col-date")
        if date_cell:
            watch_date = date_cell.get("data-date") or date_cell.get_text(strip=True)
        items.append(
            FilmItem(
                slug=slug,
                title=title,
                year=year,
                rating=rating,
                liked=liked,
                watched=True,
                watch_date=watch_date,
                watchlist=False,
            )
        )
    return items


def parse_films_list(html: str) -> list[FilmItem]:
    soup = BeautifulSoup(html, "lxml")
    items: list[FilmItem] = []
    for poster in soup.select("div.film-poster"):
        slug = _attr(poster, "data-film-slug") or _slug_from_poster(poster)
        if not slug:
            continue
        title = _attr(poster, "data-film-name")
        year = _to_int(_attr(poster, "data-film-year"))
        rating = _parse_star_rating(_rating_text_from_poster(poster))
        items.append(
            FilmItem(
                slug=slug,
                title=title,
                year=year,
                rating=rating,
                liked=False,
                watched=True,
                watch_date=None,
                watchlist=False,
            )
        )
    return items


def parse_likes_list(html: str) -> list[FilmItem]:
    items = _parse_poster_list(html)
    return [
        FilmItem(
            slug=item.slug,
            title=item.title,
            year=item.year,
            rating=item.rating,
            liked=True,
            watched=True,
            watch_date=item.watch_date,
            watchlist=False,
        )
        for item in items
    ]


def parse_watchlist(html: str) -> list[FilmItem]:
    items = _parse_poster_list(html)
    return [
        FilmItem(
            slug=item.slug,
            title=item.title,
            year=item.year,
            rating=item.rating,
            liked=False,
            watched=item.watched,
            watch_date=item.watch_date,
            watchlist=True,
        )
        for item in items
    ]


def parse_next_page(html: str) -> str | None:
    soup = BeautifulSoup(html, "lxml")
    link = soup.select_one("a.next") or soup.select_one("a.next-page")
    if link and link.get("href"):
        return link["href"]
    rel = soup.find("a", rel="next")
    if rel and rel.get("href"):
        return rel["href"]
    return None


def _parse_poster_list(html: str) -> list[FilmItem]:
    soup = BeautifulSoup(html, "lxml")
    items: list[FilmItem] = []
    for poster in soup.select("div.film-poster"):
        slug = _attr(poster, "data-film-slug") or _slug_from_poster(poster)
        if not slug:
            continue
        title = _attr(poster, "data-film-name")
        year = _to_int(_attr(poster, "data-film-year"))
        items.append(
            FilmItem(
                slug=slug,
                title=title,
                year=year,
                rating=None,
                liked=False,
                watched=False,
                watch_date=None,
                watchlist=False,
            )
        )
    return items


def _attr(node, key: str) -> str | None:
    return node.get(key) if node else None


def _to_int(value: str | None) -> int | None:
    if not value:
        return None
    try:
        return int(value)
    except ValueError:
        return None


def _parse_star_rating(text: str | None) -> float | None:
    if not text:
        return None
    try:
        numeric = float(text)
        return numeric
    except ValueError:
        pass
    stars = text.count("★")
    half = 0.5 if "½" in text else 0.0
    return float(stars) + half


def _rating_text_from_poster(poster) -> str | None:
    rating = poster.find_next("span", class_="rating")
    if rating:
        return rating.get_text(strip=True)
    return None


def _slug_from_poster(poster) -> str | None:
    link = poster.find("a", href=True)
    if not link:
        return None
    href = link["href"]
    return href.strip("/").split("/")[-1] if href else None


def _find_poster_slug(node) -> str | None:
    poster = node.select_one("div.film-poster")
    if poster:
        return _attr(poster, "data-film-slug") or _slug_from_poster(poster)
    return None


def merge_items(items: Iterable[FilmItem]) -> dict[str, FilmItem]:
    merged: dict[str, FilmItem] = {}
    for item in items:
        existing = merged.get(item.slug)
        if not existing:
            merged[item.slug] = item
            continue
        merged[item.slug] = FilmItem(
            slug=item.slug,
            title=item.title or existing.title,
            year=item.year or existing.year,
            rating=item.rating or existing.rating,
            liked=item.liked or existing.liked,
            watched=item.watched or existing.watched,
            watch_date=item.watch_date or existing.watch_date,
            watchlist=item.watchlist or existing.watchlist,
        )
    return merged
