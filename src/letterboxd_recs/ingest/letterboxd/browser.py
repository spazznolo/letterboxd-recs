from __future__ import annotations

from dataclasses import dataclass

from letterboxd_recs.util.logging import get_logger

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
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(user_agent=user_agent)
        page = context.new_page()
        page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
        content = page.content()
        context.close()
        browser.close()
    return BrowserFetchResult(url=url, content=content)
