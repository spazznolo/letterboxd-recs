from __future__ import annotations

from dataclasses import dataclass

from playwright.sync_api import sync_playwright

from letterboxd_recs.util.logging import get_logger

LOG = get_logger(__name__)


@dataclass(frozen=True)
class BrowserFetchResult:
    url: str
    content: str


def fetch_html(url: str, user_agent: str, timeout_ms: int = 30000) -> BrowserFetchResult:
    LOG.info("Browser fetching: %s", url)
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(user_agent=user_agent)
        page = context.new_page()
        page.goto(url, wait_until="networkidle", timeout=timeout_ms)
        content = page.content()
        context.close()
        browser.close()
    return BrowserFetchResult(url=url, content=content)
