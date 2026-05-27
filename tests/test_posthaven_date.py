import pytest
from bs4 import BeautifulSoup

from yclib_extract.lib.html_cleaning import extract_page_metadata


def test_extract_posthaven_date():
    html = """
    <div class="actual-date">
        <span class="posthaven-formatted-date" data-format="%B %e, %Y at %l:%M %p" data-unix-time="1757376622">September  9, 2025 at  1:10 AM</span>
      </div>
    """
    soup = BeautifulSoup(html, "html.parser")
    meta = extract_page_metadata(soup)
    assert meta.get("published_at") == "2025-09-09"
