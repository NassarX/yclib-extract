"""Tests for the Paul Graham essay extraction pipeline."""

import pytest
from unittest.mock import MagicMock, patch
from yclib_extract.pipeline import PipelineOrchestrator
from yclib_extract.scraper import RSSScraper

def test_pg_index_discovery():
    """Test that PG index discovery combines HTML and RSS."""
    orch = PipelineOrchestrator()
    
    with patch("requests.get") as mock_get:
        # Mock HTML index response
        mock_html = MagicMock()
        mock_html.text = '<html><a href="essay1.html">Essay 1</a><a href="essay2.html">Essay 2</a></html>'
        mock_html.raise_for_status = MagicMock()
        
        # Mock RSS response
        mock_rss_content = b"""<?xml version="1.0" encoding="UTF-8"?>
        <rss version="2.0">
        <channel>
            <item><link>https://paulgraham.com/essay3.html</link><title>Essay 3</title></item>
        </channel>
        </rss>"""
        
        def side_effect(url, **kwargs):
            m = MagicMock()
            m.raise_for_status = MagicMock()
            if "articles.html" in url:
                m.text = mock_html.text
                m.content = mock_html.text.encode()
            elif "rss.xml" in url:
                m.content = mock_rss_content
            return m
            
        mock_get.side_effect = side_effect
        
        urls = orch._fetch_pg_index_urls()
        
        assert any("essay1.html" in u for u in urls)
        assert any("essay2.html" in u for u in urls)
        assert any("essay3.html" in u for u in urls)
        assert len(urls) >= 3

def test_pg_slug_generation():
    """Test canonical slug generation for PG essays."""
    orch = PipelineOrchestrator()
    assert orch._pg_slug("https://paulgraham.com/best.html") == "best"
    assert orch._pg_slug("http://www.paulgraham.com/articles.html") == "articles"
    assert orch._pg_slug("https://paulgraham.com/sub/deep.html") == "deep"

@patch("requests.get")
def test_rss_scraper_pg_format(mock_get):
    """Test RSSScraper with PG's specific RSS format."""
    mock_get.return_value.content = b"""<?xml version="1.0" encoding="UTF-8"?>
    <rss version="2.0">
    <channel>
        <item>
            <title>How to Do Great Work</title>
            <link>https://paulgraham.com/greatwork.html</link>
            <pubDate>Sun, 01 Jul 2023 00:00:00 GMT</pubDate>
        </item>
    </channel>
    </rss>"""
    mock_get.return_value.raise_for_status = MagicMock()
    
    scraper = RSSScraper("https://paulgraham.com/rss.xml")
    items = scraper.fetch_items()
    
    assert len(items) == 1
    assert items[0]["title"] == "How to Do Great Work"
    assert items[0]["url"] == "https://paulgraham.com/greatwork.html"
