import re
from pathlib import Path

from bs4 import BeautifulSoup
from yclib_extract.extractor import ContentExtractor
from yclib_extract.lib.html_cleaning import extract_main_content, html_to_markdown

FIXED_FIXTURES = Path(__file__).parent / "fixtures"
LIVE_OFFICE_HOURS_HTML = FIXED_FIXTURES / "live_office_hours.html"
LIVE_OFFICE_HOURS_URL = "https://www.ycombinator.com/library/7n-live-office-hours-with-yc-s-kevin-hale-and-dalton-caldwell-2017"


def test_live_office_hours_extraction_strips_chrome():
    html = LIVE_OFFICE_HOURS_HTML.read_text()
    soup = BeautifulSoup(html, "html.parser")
    content = extract_main_content(soup)

    assert content is not None
    assert "window.posthog" not in content
    # Check text content ignoring HTML entities
    assert "Live office hours with YC" in content
    assert "Kevin Hale and Dalton Caldwell (2017)" in content


def test_html_to_markdown_preserves_links():
    html = '<p>Check out <a href="https://example.com">this link</a></p>'
    markdown = html_to_markdown(html)
    assert "[this link](https://example.com)" in markdown


def test_extract_main_content_handles_various_containers():
    # Test article container
    html1 = "<html><body><article><h1>Title</h1><p>Content</p></article></body></html>"
    soup1 = BeautifulSoup(html1, "html.parser")
    assert "Content" in extract_main_content(soup1)

    # Test main container
    html2 = "<html><body><main><h1>Title</h1><p>Main Content</p></main></body></html>"
    soup2 = BeautifulSoup(html2, "html.parser")
    assert "Main Content" in extract_main_content(soup2)

    # Test div with content class
    html3 = '<html><body><div class="content"><h1>Title</h1><p>Div Content</p></div></body></html>'
    soup3 = BeautifulSoup(html3, "html.parser")
    assert "Div Content" in extract_main_content(soup3)


def test_live_office_hours_end_to_end_page_flow(monkeypatch, tmp_path):
    html = LIVE_OFFICE_HOURS_HTML.read_text()

    class FakeResponse:
        content = html.encode()
        text = html

        def raise_for_status(self):
            return None

    class FakeDB:
        def __init__(self):
            self.status = {}

        def register_job(self, job_id, file_path, url, source_type):
            self.status[job_id] = {"status": "pending", "url": url}

        def update_job_status(
            self, job_id, status, content_length=None, error_msg="", source_type=None, quality=None
        ):
            self.status[job_id] = {
                "status": status,
                "content_length": content_length,
                "error_msg": error_msg,
                "source_type": source_type,
            }

        def get_job_status(self, job_id):
            return self.status.get(job_id)

    monkeypatch.setattr("yclib_extract.extractor.ExtractionDB", FakeDB)
    monkeypatch.setattr("yclib_extract.extractor.requests.get", lambda url, timeout: FakeResponse())
    # Ensure it finds the youtube URL
    monkeypatch.setattr(
        "yclib_extract.extractor.extract_youtube_url",
        lambda h: "https://www.youtube.com/watch?v=8Qc8ipjzatY",
    )

    extractor = ContentExtractor(output_dir=str(tmp_path), min_content_length=1)
    result = extractor.extract_content(
        LIVE_OFFICE_HOURS_URL, "7n-live-office-hours", source_type="Video"
    )

    assert result is not None
    assert result.video_url == "https://www.youtube.com/watch?v=8Qc8ipjzatY"
    assert "Live office hours with YC's Kevin Hale and Dalton Caldwell (2017)" in result.content
    assert extractor.db.status["7n-live-office-hours"]["status"] == "done"


def test_video_extraction_appends_transcript_and_video_url(monkeypatch, tmp_path):
    html = """
    <html>
      <body>
        <article>
          <h1>Video title</h1>
          <p>Short summary.</p>
        </article>
      </body>
    </html>
    """

    class FakeResponse:
        content = html.encode()
        text = html

        def raise_for_status(self):
            return None

    class FakeDB:
        def __init__(self):
            self.status = {}

        def register_job(self, job_id, file_path, url, source_type):
            self.status[job_id] = {"status": "pending", "url": url, "source_type": source_type}

        def update_job_status(
            self, job_id, status, content_length=None, error_msg="", source_type=None, quality=None
        ):
            self.status[job_id] = {
                "status": status,
                "content_length": content_length,
                "error_msg": error_msg,
                "source_type": source_type,
            }

        def get_job_status(self, job_id):
            return self.status.get(job_id)

    transcript = "Transcript line. " * 200

    monkeypatch.setattr("yclib_extract.extractor.ExtractionDB", FakeDB)
    monkeypatch.setattr("yclib_extract.extractor.requests.get", lambda url, timeout: FakeResponse())
    monkeypatch.setattr("yclib_extract.extractor.get_transcript", lambda url: transcript)
    monkeypatch.setattr(
        "yclib_extract.extractor.extract_youtube_url",
        lambda h: "https://www.youtube.com/watch?v=8Qc8ipjzatY",
    )

    extractor = ContentExtractor(output_dir=str(tmp_path), min_content_length=2000)
    result = extractor.extract_content(
        "https://www.ycombinator.com/library/test-video",
        "test-video",
        source_type="Video",
    )

    assert result is not None
    assert result.video_url == "https://www.youtube.com/watch?v=8Qc8ipjzatY"
    assert "## Transcript" in result.content
    assert "Transcript line." in result.content


def test_social_radars_page_detects_podcast_and_writes_podcast_url(monkeypatch, tmp_path):
    html = """
    <html>
      <body>
        <div data-page='{"props":{"article":{"title":"Emmett Shear","content":"In this episode.","author":"The Social Radars"}}}'>
        </div>
      </body>
    </html>
    """

    class FakeResponse:
        content = html.encode()
        text = html

        def raise_for_status(self):
            return None

    class FakeDB:
        def __init__(self):
            self.status = {}

        def register_job(self, job_id, file_path, url, source_type):
            self.status[job_id] = {"status": "pending", "url": url, "source_type": source_type}

        def update_job_status(
            self, job_id, status, content_length=None, error_msg="", source_type=None, quality=None
        ):
            self.status[job_id] = {
                "status": status,
                "content_length": content_length,
                "error_msg": error_msg,
                "source_type": source_type,
            }

        def get_job_status(self, job_id):
            return self.status.get(job_id)

    monkeypatch.setattr("yclib_extract.extractor.ExtractionDB", FakeDB)
    monkeypatch.setattr("yclib_extract.extractor.requests.get", lambda url, timeout: FakeResponse())
    monkeypatch.setattr(
        "yclib_extract.extractor.extract_podcast_url",
        lambda h: "https://open.spotify.com/episode/abc",
    )

    extractor = ContentExtractor(output_dir=str(tmp_path), min_content_length=2000)
    result = extractor.extract_content(
        "https://www.ycombinator.com/library/test-podcast",
        "test-podcast",
        source_type="Blog",
    )

    assert result is not None
    assert result.podcast_url == "https://open.spotify.com/episode/abc"
    assert extractor.db.status["test-podcast"]["status"] == "done"


def test_video_with_no_video_url_and_tiny_body_is_removed(monkeypatch, tmp_path):
    html = "<html><body><article><h1>Video</h1><p>tiny</p></article></body></html>"

    class FakeResponse:
        content = html.encode()
        text = html

        def raise_for_status(self):
            return None

    class FakeDB:
        def __init__(self):
            self.status = {}

        def register_job(self, job_id, file_path, url, source_type):
            self.status[job_id] = {"status": "pending", "url": url, "source_type": source_type}

        def update_job_status(
            self, job_id, status, content_length=None, error_msg="", source_type=None, quality=None
        ):
            self.status[job_id] = {
                "status": status,
                "content_length": content_length,
                "error_msg": error_msg,
                "source_type": source_type,
            }

        def get_job_status(self, job_id):
            return self.status.get(job_id)

    monkeypatch.setattr("yclib_extract.extractor.ExtractionDB", FakeDB)
    monkeypatch.setattr("yclib_extract.extractor.requests.get", lambda url, timeout: FakeResponse())
    monkeypatch.setattr("yclib_extract.extractor.get_transcript", lambda url: None)
    monkeypatch.setattr("yclib_extract.extractor.extract_youtube_url", lambda h: None)

    extractor = ContentExtractor(output_dir=str(tmp_path), min_content_length=2000)
    result = extractor.extract_content(
        "https://example.com/removed", "post_removed", source_type="Video"
    )

    assert result is None
    assert extractor.db.status["post_removed"]["status"] == "removed"
