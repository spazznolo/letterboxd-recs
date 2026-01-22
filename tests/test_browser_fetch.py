import os

import pytest

from letterboxd_recs.ingest.letterboxd.browser import fetch_html
from letterboxd_recs.ingest.letterboxd.parse import is_challenge_page


@pytest.mark.skipif(os.getenv("RUN_BROWSER_TESTS") != "1", reason="Set RUN_BROWSER_TESTS=1 to enable")
def test_browser_fetch_profile() -> None:
    result = fetch_html("https://letterboxd.com/spazznolo/", user_agent="letterboxd-recs/0.1")
    assert "letterboxd" in result.content.lower()
    assert not is_challenge_page(result.content)
