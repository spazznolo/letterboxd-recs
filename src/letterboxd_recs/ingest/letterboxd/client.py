from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import time
from typing import Iterable

import requests

from letterboxd_recs.config import ScrapeConfig
from letterboxd_recs.util.cache import FileCache
from letterboxd_recs.util.logging import get_logger
from letterboxd_recs.util.ratelimit import sleep_seconds

LOG = get_logger(__name__)


@dataclass(frozen=True)
class FetchResult:
    url: str
    content: str
    from_cache: bool


class LetterboxdClient:
    def __init__(
        self,
        user_agent: str,
        scrape_config: ScrapeConfig,
        cache_dir: Path,
    ) -> None:
        self.scrape = scrape_config
        self.cache = FileCache(cache_dir)
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": user_agent})

    def fetch_html(self, url: str, cache_key: str, refresh: bool = False) -> FetchResult:
        entry = self.cache.entry(f"{cache_key}.html")

        if not refresh and entry.is_fresh(self.scrape.cache_ttl_days):
            LOG.info("Cache hit: %s", url)
            return FetchResult(url=url, content=entry.read_text(), from_cache=True)

        content = self._fetch_with_retries(url)
        entry.write_text(content)
        return FetchResult(url=url, content=content, from_cache=False)

    def write_cache(self, cache_key: str, content: str) -> None:
        entry = self.cache.entry(f"{cache_key}.html")
        entry.write_text(content)

    def fetch_many(self, urls: Iterable[str], refresh: bool = False) -> list[FetchResult]:
        results: list[FetchResult] = []
        for url in urls:
            cache_key = self.cache_key(url)
            results.append(self.fetch_html(url, cache_key, refresh=refresh))
            sleep_seconds(self.scrape.rate_limit_seconds)
        return results

    def _fetch_with_retries(self, url: str) -> str:
        last_error: Exception | None = None
        for attempt in range(1, self.scrape.max_retries + 1):
            try:
                LOG.info("Fetching: %s", url)
                resp = self.session.get(url, timeout=30)
                resp.raise_for_status()
                return resp.text
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                wait = self.scrape.rate_limit_seconds * (2 ** (attempt - 1))
                LOG.warning("Fetch failed (%s). Retry in %.1fs", exc, wait)
                time.sleep(wait)
        raise RuntimeError(f"Failed to fetch {url}") from last_error

    def cache_key(self, url: str) -> str:
        return self._cache_key_from_url(url)

    @staticmethod
    def _cache_key_from_url(url: str) -> str:
        return url.replace("https://", "").replace("http://", "").replace("/", "_")
