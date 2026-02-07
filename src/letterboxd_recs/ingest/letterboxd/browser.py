from __future__ import annotations

from dataclasses import dataclass

from letterboxd_recs.util.logging import get_logger
from letterboxd_recs.util.retry import retry

LOG = get_logger(__name__)


@dataclass(frozen=True)
class BrowserFetchResult:
    url: str
    content: str


def fetch_html(url: str, user_agent: str, timeout_ms: int = 30000) -> BrowserFetchResult:
    LOG.info("Browser fetching: %s", url)
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise RuntimeError(
            "Playwright is not installed. Install 'playwright' to enable browser fetching."
        ) from exc

    def _fetch_once() -> str:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(user_agent=user_agent)
            page = context.new_page()
            page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
            content = page.content()
            context.close()
            browser.close()
        return content

    def _on_error(exc: Exception, attempt: int) -> None:
        LOG.warning("Browser fetch failed (attempt %s): %s", attempt, exc)

    content = retry(_fetch_once, attempts=3, delay_seconds=2.0, on_error=_on_error)
    return BrowserFetchResult(url=url, content=content)
