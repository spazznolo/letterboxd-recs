from __future__ import annotations

from dataclasses import dataclass
import re
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


def parse_film_page(html: str) -> tuple[str | None, int | None, list[str]]:
    soup = BeautifulSoup(html, "lxml")
    title = None
    year = None

    header = soup.select_one("h1.headline-1") or soup.select_one("h1.film-title") or soup.select_one("h1")
    if header:
        title = header.get_text(strip=True) or None
        title, year = _normalize_title_year(title, year)

    if year is None:
        year_node = (
            soup.select_one("small.number")
            or soup.select_one("a[href*='/year/']")
            or soup.select_one("a[href*='/films/year/']")
        )
        if year_node:
            year = _to_int(year_node.get_text(strip=True))

    if title is None:
        meta = soup.find("meta", property="og:title") or soup.find("meta", attrs={"name": "twitter:title"})
        if meta and meta.get("content"):
            title = meta["content"].strip()
            title, year = _normalize_title_year(title, year)

    genres = parse_genres_page(html)

    return title, year, genres


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
        slug = _poster_attr(poster, "data-item-slug") or _attr(poster, "data-film-slug") or _slug_from_poster(poster)
        if not slug:
            continue
        title = _poster_attr(poster, "data-item-name") or _attr(poster, "data-film-name")
        year = _to_int(_poster_attr(poster, "data-item-year")) or _to_int(_attr(poster, "data-film-year"))
        title, year = _normalize_title_year(title, year)
        if not title:
            title = _frame_title(poster)
            title, year = _normalize_title_year(title, year)
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
        slug = _poster_attr(poster, "data-item-slug") or _attr(poster, "data-film-slug") or _slug_from_poster(poster)
        if not slug:
            continue
        title = _poster_attr(poster, "data-item-name") or _attr(poster, "data-film-name")
        year = _to_int(_poster_attr(poster, "data-item-year")) or _to_int(_attr(poster, "data-film-year"))
        title, year = _normalize_title_year(title, year)
        if not title:
            title = _frame_title(poster)
            title, year = _normalize_title_year(title, year)
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
    parent = _poster_parent(poster)
    if parent:
        slug = _attr(parent, "data-item-slug")
        if slug:
            return slug
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


def _poster_parent(poster):
    return poster.find_parent(attrs={"data-item-slug": True})


def _poster_attr(poster, key: str) -> str | None:
    parent = _poster_parent(poster)
    if parent:
        return parent.get(key)
    return None


def _frame_title(poster) -> str | None:
    frame = poster.select_one("span.frame-title")
    if frame:
        return frame.get_text(strip=True) or None
    return None


def _split_title_year(text: str) -> tuple[str | None, int | None]:
    match = re.match(r"^(?P<title>.+?)\s*\((?P<year>\d{4})\)$", text.strip())
    if not match:
        return text, None
    return match.group("title").strip(), _to_int(match.group("year"))


def _normalize_title_year(title: str | None, year: int | None) -> tuple[str | None, int | None]:
    if not title:
        return title, year
    cleaned, parsed_year = _split_title_year(title)
    if parsed_year is not None:
        year = year or parsed_year
        title = cleaned
    return title, year


def parse_genres_page(html: str) -> list[str]:
    soup = BeautifulSoup(html, "lxml")
    tab = soup.select_one("#tab-genres") or soup
    genres: list[str] = []

    heading = None
    for h3 in tab.select("h3"):
        span = h3.find("span")
        if span and span.get_text(strip=True).lower() == "genres":
            heading = h3
            break

    if heading:
        block = heading.find_next_sibling("div")
        candidates = block.select("a.text-slug") if block else tab.select("a.text-slug")
    else:
        candidates = tab.select("a.text-slug")

    for tag in candidates:
        href = tag.get("href", "")
        text = tag.get_text(strip=True)
        if not text:
            continue
        if "/films/genre/" not in href:
            continue
        if text not in genres:
            genres.append(text)

    return genres


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
