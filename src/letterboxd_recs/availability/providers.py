from __future__ import annotations

import re
from bs4 import BeautifulSoup

SOURCE_ALIASES: dict[str, str] = {
    "apple_tv_store": "apple_itunes",
    "amazon_ca": "amazon",
    "amazon_prime_video": "prime_video",
    "amazonprimevideo": "prime_video",
    "prime_video": "prime_video",
    "disney_plus": "disney_plus",
    "disneyplus": "disney_plus",
    "apple_tv_plus": "apple_tv_plus",
    "appletvplus": "apple_tv_plus",
    "criterion_channel": "criterion_channel",
    "criterionchannel": "criterion_channel",
    "paramount_plus": "paramount_plus",
    "paramountplus": "paramount_plus",
    "google_play": "google_play_movies",
    "cosmogo_ca": "cosmogo",
}

STREAM_MARKERS = ("stream", "play", "flatrate", "free", "ads")
RENT_MARKERS = ("rent",)
NEGATIVE_ONLY_MARKERS = ("buy", "disc")

CARED_PROVIDER_COLUMNS: tuple[str, ...] = (
    # Streaming subscriptions/ad-supported
    "netflix",
    "disney_plus",
    "prime_video",
    "apple_tv_plus",
    "crave",
    "mubi",
    "criterion_channel",
    "max",
    "hulu",
    "paramount_plus",
    "peacock",
    "tubi",
    "youtube",
    "plex",
    # Transactional stores
    "amazon",
    "apple_itunes",
    "google_play_movies",
    "cineplex",
    "cosmogo",
)


def provider_columns() -> tuple[str, ...]:
    return CARED_PROVIDER_COLUMNS


def source_to_column(source: str) -> str:
    value = source.strip().lower()
    if value.startswith("source-"):
        value = value[len("source-") :]
    value = value.replace("+", "plus")
    value = re.sub(r"[^a-z0-9]+", "_", value)
    value = value.strip("_")
    if not value:
        return "unknown_source"
    if value[0].isdigit():
        value = f"s_{value}"
    return value


def provider_column_from_arg(value: str) -> str | None:
    if not value or not value.strip():
        return None
    normalized = source_to_column(value)
    normalized = SOURCE_ALIASES.get(normalized, normalized)
    if normalized in CARED_PROVIDER_COLUMNS or normalized == "stream":
        return normalized
    return None


def parse_availability_sources(html: str) -> tuple[dict[str, bool], bool]:
    soup = BeautifulSoup(html, "lxml")
    flags: dict[str, bool] = {}
    has_stream = False

    for node in soup.select("p[id^='source-'].service"):
        source = str(node.get("id", ""))[len("source-") :].strip()
        if not source:
            continue
        column = SOURCE_ALIASES.get(source_to_column(source), source_to_column(source))
        if column not in CARED_PROVIDER_COLUMNS:
            continue
        option_nodes = node.select(".options a")
        option_tokens: set[str] = set()
        for option in option_nodes:
            text = option.get_text(" ", strip=True).lower()
            classes = " ".join(option.get("class", [])).lower()
            blob = f"{text} {classes}"
            for marker in STREAM_MARKERS + RENT_MARKERS + NEGATIVE_ONLY_MARKERS:
                if marker in blob:
                    option_tokens.add(marker)

        if not option_tokens:
            # Some entries only show the provider link; do not mark true.
            flags[column] = flags.get(column, False)
            continue

        source_has_stream = any(marker in option_tokens for marker in STREAM_MARKERS)
        source_has_rent = any(marker in option_tokens for marker in RENT_MARKERS)
        flags[column] = flags.get(column, False) or source_has_stream or source_has_rent
        has_stream = has_stream or source_has_stream

    return flags, has_stream


def extract_availability_csi_url(html: str) -> str | None:
    soup = BeautifulSoup(html, "lxml")
    node = soup.select_one(".loading-csi[data-src*='/csi/film/'][data-src*='/availability/']")
    if not node:
        return None
    data_src = str(node.get("data-src", "")).strip()
    if not data_src:
        return None
    data_src = data_src.replace("&amp;", "&")
    if data_src.startswith("/"):
        return f"https://letterboxd.com{data_src}"
    return data_src


def parse_where_to_watch_flags(html: str) -> set[str]:
    # Backward-compatible wrapper used by older code/tests.
    flags, _ = parse_availability_sources(html)
    return {key for key, val in flags.items() if val}
