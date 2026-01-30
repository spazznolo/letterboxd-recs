from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlparse

from bs4 import BeautifulSoup


@dataclass(frozen=True)
class FolloweeSummary:
    username: str
    display_name: str | None
    followers: int | None
    following: int | None
    watched: int | None


def parse_following(html: str) -> list[str]:
    return [entry.username for entry in parse_following_entries(html)]


def parse_following_entries(html: str) -> list[FolloweeSummary]:
    soup = BeautifulSoup(html, "lxml")
    rows = soup.select("tr") or []
    entries: list[FolloweeSummary] = []

    for row in rows:
        name_link = row.select_one("td.col-member a.name")
        if not name_link:
            continue
        href = name_link.get("href")
        if not href:
            continue
        username = href.strip("/").split("/")[0]
        if not username:
            continue

        display_name = name_link.get_text(strip=True) or None

        meta = row.select_one("td.col-member small.metadata")
        followers = None
        following = None
        if meta:
            links = meta.select("a")
            if len(links) >= 1:
                followers = _parse_int(links[0].get_text(strip=True))
            if len(links) >= 2:
                following = _parse_int(links[1].get_text(strip=True))

        watched = None
        watched_cell = row.select_one("td.col-watched a")
        if watched_cell:
            watched = _parse_int(watched_cell.get_text(strip=True))

        entries.append(
            FolloweeSummary(
                username=username,
                display_name=display_name,
                followers=followers,
                following=following,
                watched=watched,
            )
        )

    if entries:
        return entries

    # Fallback: try to infer from avatar links only.
    usernames: list[str] = []
    for link in soup.select("a.avatar, a.avatar-link, a[href*='/profile/'], a[href^='/']"):
        href = link.get("href")
        if not href:
            continue
        path = urlparse(href).path if href.startswith("http") else href
        path = path.strip("/")
        if not path or "/" in path:
            continue
        if path in ("films", "members", "followers", "following"):
            continue
        if path not in usernames:
            usernames.append(path)
    return [
        FolloweeSummary(username=u, display_name=None, followers=None, following=None, watched=None)
        for u in usernames
    ]


def _parse_int(text: str) -> int | None:
    if not text:
        return None
    cleaned = (
        text.replace("followers", "")
        .replace("follower", "")
        .replace("following", "")
        .replace(",", "")
        .strip()
    )
    digits = "".join(ch for ch in cleaned if ch.isdigit())
    return int(digits) if digits else None
