import json

from yclib_extract.extractor import ContentExtractor, ExtractionDB


def test_extraction_db_registers_and_updates(tmp_path):
    db = ExtractionDB(db_path=str(tmp_path / "jobs.db"))

    db.register_job("job-1", "file.json", "https://example.com", "article")
    db.update_job_status("job-1", "done", content_length=123, quality="high")

    job = db.get_job_status("job-1")
    assert job["id"] == "job-1"
    assert job["status"] == "done"
    assert job["content_length"] == 123
    assert job["quality"] == "high"
    assert job["attempt_count"] == 1


def test_extract_content_handles_successful_html(monkeypatch, tmp_path):
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

    class FakeResponse:
        content = b"<html><body><article><h1>Title</h1><p>Hello world</p></article></body></html>"
        text = "<html><body><article><h1>Title</h1><p>Hello world</p></article></body></html>"

        def raise_for_status(self):
            return None

    monkeypatch.setattr("yclib_extract.extractor.ExtractionDB", FakeDB)
    monkeypatch.setattr("yclib_extract.extractor.requests.get", lambda url, timeout: FakeResponse())

    extractor = ContentExtractor(output_dir=str(tmp_path), min_content_length=1)
    result = extractor.extract_content("https://example.com/post", "job-1")

    assert result is not None
    assert "Hello world" in result.content
    assert extractor.db.status["job-1"]["status"] == "done"


def test_process_posts_skips_completed_jobs(monkeypatch, tmp_path):
    input_dir = tmp_path / "metadata"
    input_dir.mkdir()
    (input_dir / "post_00001.json").write_text(
        json.dumps({"url": "https://example.com/1", "title": "One"})
    )
    (input_dir / "post_00002.json").write_text(
        json.dumps({"url": "https://example.com/2", "title": "Two"})
    )

    class FakeDB:
        def __init__(self):
            self.status = {"post_00001": {"status": "done"}}

        def register_job(self, *args, **kwargs):
            return None

        def update_job_status(self, *args, **kwargs):
            return None

        def get_job_status(self, job_id):
            return self.status.get(job_id)

    monkeypatch.setattr("yclib_extract.extractor.ExtractionDB", FakeDB)
    monkeypatch.setattr("yclib_extract.extractor.load_ignore_sources", lambda: set())

    extractor = ContentExtractor(output_dir=str(tmp_path / "out"), min_content_length=1)
    seen = []

    def fake_extract_content(url, job_id, source_type="article", media_url_hint=None):
        seen.append(job_id)
        return type(
            "Result",
            (),
            {
                "content": "content",
                "video_url": None,
                "podcast_url": None,
                "source_type": "Article",
            },
        )()

    monkeypatch.setattr(extractor, "extract_content", fake_extract_content)
    monkeypatch.setattr(
        extractor,
        "save_markdown",
        lambda job_id, content, metadata, video_url="", podcast_url="", source_type="": job_id,
    )

    extractor.process_posts(str(input_dir), workers=1, force=False)

    assert seen == ["post_00002"]


def test_process_posts_retry_failed_only_filters_statuses(monkeypatch, tmp_path):
    input_dir = tmp_path / "metadata"
    input_dir.mkdir()
    (input_dir / "post_done.json").write_text(json.dumps({"url": "https://example.com/done"}))
    (input_dir / "post_short.json").write_text(json.dumps({"url": "https://example.com/short"}))
    (input_dir / "post_failed.json").write_text(json.dumps({"url": "https://example.com/failed"}))
    (input_dir / "post_new.json").write_text(json.dumps({"url": "https://example.com/new"}))

    class FakeDB:
        def __init__(self):
            self.status = {
                "post_done": {"status": "done"},
                "post_short": {"status": "short"},
                "post_failed": {"status": "failed"},
            }

        def register_job(self, *args, **kwargs):
            return None

        def update_job_status(self, *args, **kwargs):
            return None

        def get_job_status(self, job_id):
            return self.status.get(job_id)

    monkeypatch.setattr("yclib_extract.extractor.ExtractionDB", FakeDB)
    monkeypatch.setattr("yclib_extract.extractor.load_ignore_sources", lambda: set())

    extractor = ContentExtractor(output_dir=str(tmp_path / "out"), min_content_length=1)
    seen = []

    def fake_extract_content(url, job_id, source_type="article", media_url_hint=None):
        seen.append(job_id)
        return type(
            "Result",
            (),
            {
                "content": "content",
                "video_url": None,
                "podcast_url": None,
                "source_type": "Article",
            },
        )()

    monkeypatch.setattr(extractor, "extract_content", fake_extract_content)
    monkeypatch.setattr(
        extractor,
        "save_markdown",
        lambda job_id, content, metadata, video_url="", podcast_url="", source_type="": job_id,
    )

    extractor.process_posts(str(input_dir), workers=1, retry_failed_only=True)

    assert seen == ["post_failed", "post_short"]


def test_extract_content_marks_removed_videos_from_tiny_body(monkeypatch, tmp_path):
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

    class FakeResponse:
        content = b"<html><body><article><h1>Removed</h1></article></body></html>"
        text = "<html><body><article><h1>Removed</h1></article></body></html>"

        def raise_for_status(self):
            return None

    monkeypatch.setattr("yclib_extract.extractor.ExtractionDB", FakeDB)
    monkeypatch.setattr("yclib_extract.extractor.requests.get", lambda url, timeout: FakeResponse())
    monkeypatch.setattr("yclib_extract.extractor.load_ignore_sources", lambda: set())
    monkeypatch.setattr("yclib_extract.extractor.get_transcript", lambda url: None)
    monkeypatch.setattr("yclib_extract.extractor.extract_youtube_url", lambda html: None)

    extractor = ContentExtractor(output_dir=str(tmp_path / "out"), min_content_length=2000)
    result = extractor.extract_content(
        "https://example.com/removed",
        "post_removed",
        source_type="Video",
    )

    assert result is None
    status_info = extractor.db.status["post_removed"]
    if status_info["status"] == "error":
        print(f"DEBUG Error: {status_info.get('error_msg')}")
    assert status_info["status"] == "removed"


def test_extract_content_skips_length_check_for_external(monkeypatch, tmp_path):
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

    class FakeResponse:
        content = b"<html><body><article><h1>Title</h1><p>Short external content</p></article></body></html>"
        text = "<html><body><article><h1>Title</h1><p>Short external content</p></article></body></html>"

        def raise_for_status(self):
            return None

    monkeypatch.setattr("yclib_extract.extractor.ExtractionDB", FakeDB)
    monkeypatch.setattr("yclib_extract.extractor.load_ignore_sources", lambda: set())
    monkeypatch.setattr("yclib_extract.extractor.requests.get", lambda url, timeout: FakeResponse())

    extractor = ContentExtractor(output_dir=str(tmp_path), min_content_length=2000)
    result = extractor.extract_content(
        "https://example.com/external", "external-1", source_type="External"
    )

    assert result is not None
    assert extractor.db.status["external-1"]["status"] == "done"


def test_get_all_jobs_ordering(tmp_path):
    import time

    db = ExtractionDB(db_path=str(tmp_path / "ordering.db"))

    # Register and update multiple jobs at different times
    db.register_job("job-old", "old.md", "url-old", "article")
    db.update_job_status("job-old", "done")

    # Ensure some time passes for last_attempt difference (though ISO8601 should be fine)
    time.sleep(0.01)

    db.register_job("job-new", "new.md", "url-new", "article")
    db.update_job_status("job-new", "done")

    jobs = db.get_all_jobs()
    assert len(jobs) == 2
    assert jobs[0]["id"] == "job-new"
    assert jobs[1]["id"] == "job-old"


def test_quality_tracking():
    """Test quality level determination based on content length."""
    from yclib_extract.extractor import YCLibraryExtractionEnhancer
    
    # Excellent (> 5000)
    meta = {"title": "Title", "author": "Author"}
    metrics = YCLibraryExtractionEnhancer.track_extraction_quality("a" * 6000, meta)
    assert metrics["quality_level"] == "excellent"
    
    # Good (500 - 5000)
    metrics = YCLibraryExtractionEnhancer.track_extraction_quality("a" * 1000, meta)
    assert metrics["quality_level"] == "good"
    
    # Minimal (100 - 500)
    metrics = YCLibraryExtractionEnhancer.track_extraction_quality("a" * 200, meta)
    assert metrics["quality_level"] == "minimal"
    
    # Short (< 100)
    metrics = YCLibraryExtractionEnhancer.track_extraction_quality("a" * 50, meta)
    assert metrics["quality_level"] == "short"
    assert "content_too_short" in metrics["warnings"]
