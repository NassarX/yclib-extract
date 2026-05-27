import pytest
from bs4 import BeautifulSoup

from yclib_extract.lib.html_cleaning import extract_page_metadata


def test_extract_page_metadata_date():
    html = """<html><body>
    <div data-page='{"props":{"article":{"created_at":"2020-06-09T01:07:16.711Z"}}}'></div>
    </body></html>"""
    soup = BeautifulSoup(html, "html.parser")
    meta = extract_page_metadata(soup)
    assert meta.get("published_at") == "2020-06-09"

    html_pub = """<html><body>
    <div data-page='{"props":{"article":{"published_at":"2021-08-10T12:00:00Z"}}}'></div>
    </body></html>"""
    soup_pub = BeautifulSoup(html_pub, "html.parser")
    meta_pub = extract_page_metadata(soup_pub)
    assert meta_pub.get("published_at") == "2021-08-10"
