"""Tests for the Sam Altman essay extraction pipeline."""

from unittest.mock import MagicMock, patch

import pytest

from yclib_extract.pipeline import PipelineOrchestrator
from yclib_extract.scraper import RSSScraper


def test_sa_index_discovery():
    """Test that Sam Altman index discovery uses RSSScraper."""
    orch = PipelineOrchestrator()

    with patch("yclib_extract.scraper.RSSScraper.fetch_items") as mock_fetch:
        mock_fetch.return_value = [
            {"url": "https://blog.samaltman.com/essay1", "date": "2023-01-01"},
            {"url": "https://blog.samaltman.com/essay2", "date": "2023-01-02"},
        ]

        urls_with_dates = orch._fetch_sa_index_urls()

        assert len(urls_with_dates) == 2
        assert urls_with_dates[0][0] == "https://blog.samaltman.com/essay1"
        assert urls_with_dates[1][0] == "https://blog.samaltman.com/essay2"


def test_sa_slug_generation():
    """Test canonical slug generation for Sam Altman essays."""
    orch = PipelineOrchestrator()
    assert (
        orch._sa_slug("https://blog.samaltman.com/how-to-be-successful") == "how-to-be-successful"
    )
    assert orch._sa_slug("https://blog.samaltman.com/2279512") == "2279512"
    assert orch._sa_slug("https://blog.samaltman.com/") == "essay"


@patch("requests.get")
def test_rss_scraper_altman_format(mock_get):
    """Test RSSScraper with Sam Altman's Atom feed format."""
    mock_get.return_value.content = b"""<?xml version="1.0" encoding="utf-8"?>
    <feed xmlns="http://www.w3.org/2005/Atom">
      <entry>
        <title>Idea Generation</title>
        <link href="https://blog.samaltman.com/idea-generation"/>
        <updated>2023-05-01T00:00:00Z</updated>
      </entry>
    </feed>"""
    mock_get.return_value.raise_for_status = MagicMock()

    scraper = RSSScraper("https://blog.samaltman.com/posts.atom")
    items = scraper.fetch_items()

    assert len(items) == 1
    assert items[0]["title"] == "Idea Generation"
    assert items[0]["url"] == "https://blog.samaltman.com/idea-generation"
    assert "2023-05-01" in items[0]["date"]
