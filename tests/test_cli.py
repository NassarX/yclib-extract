import sys

from yclib_extract import cli


def test_main_prints_help_when_no_command(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["yclib-extract"])

    assert cli.main() == 1
    assert "usage:" in capsys.readouterr().out


def test_main_scrape_dispatches_to_scraper(monkeypatch):
    calls = {}

    class FakeScraper:
        def __init__(self, app_id=None, api_key=None, index_name="library_posts"):
            calls["init"] = (app_id, api_key, index_name)

        def browse_all(self):
            calls["browse"] = True
            return [{"objectID": "1"}]

        def save_posts(self, posts, output_dir):
            calls["save"] = (posts, output_dir)

    monkeypatch.setattr(sys, "argv", ["yclib-extract", "scrape", "--output-dir", "out"])
    monkeypatch.setattr("yclib_extract.scraper.AlgoliaScraper", FakeScraper)

    assert cli.main() == 0
    assert calls["init"] == (None, None, "library_posts")
    assert calls["browse"] is True
    assert calls["save"] == ([{"objectID": "1"}], "out")


def test_main_extract_audit_only_short_circuits(monkeypatch, capsys):
    called = {}

    class FakeExtractor:
        def __init__(self, output_dir="artifacts/yc_library"):
            called["init"] = output_dir

        def process_posts(self, *args, **kwargs):
            called["process"] = True

    monkeypatch.setattr(sys, "argv", ["yclib-extract", "extract", "--audit-only"])
    monkeypatch.setattr("yclib_extract.extractor.ContentExtractor", FakeExtractor)

    assert cli.main() == 0
    assert "Audit mode: no changes" in capsys.readouterr().out
    assert called["init"] == "artifacts/yc_library"
    assert "process" not in called


def test_main_extract_retry_failed_only_dispatches(monkeypatch):
    called = {}

    class FakeExtractor:
        def __init__(self, output_dir="artifacts/yc_library"):
            called["init"] = output_dir

        def process_posts(self, input_dir, workers=4, force=False, retry_failed_only=False):
            called["process"] = (input_dir, workers, force, retry_failed_only)

    monkeypatch.setattr(
        sys,
        "argv",
        ["yclib-extract", "extract", "--input-dir", "meta", "--retry-failed-only"],
    )
    monkeypatch.setattr("yclib_extract.extractor.ContentExtractor", FakeExtractor)

    assert cli.main() == 0
    assert called["init"] == "artifacts/yc_library"
    assert called["process"] == ("meta", 4, False, True)


def test_main_pipeline_dispatches_to_orchestrator(monkeypatch):
    called = {}

    class FakeOrchestrator:
        def __init__(
            self,
            metadata_dir,
            content_dir,
            workers,
            algolia_app_id,
            algolia_api_key,
            algolia_index,
            algolia_blog_index,
            algolia_blog_api_key=None,
        ):
            called["init"] = (
                metadata_dir,
                content_dir,
                workers,
                algolia_app_id,
                algolia_api_key,
                algolia_index,
                algolia_blog_index,
            )

        def run(self, start_stage, mode, replay, retry_failed_only):
            called["run"] = (start_stage, mode, replay, retry_failed_only)

    monkeypatch.setattr(
        sys,
        "argv",
        ["yclib-extract", "pipeline", "--start-stage", "extract", "--mode", "dev", "--replay"],
    )
    monkeypatch.setattr("yclib_extract.pipeline.PipelineOrchestrator", FakeOrchestrator)

    assert cli.main() == 0
    # Now the CLI uses config defaults
    assert called["init"][0] == "artifacts/metadata/yc_library_metadata.json"
    assert called["init"][1] == "artifacts/yc_library"
    assert called["init"][2] == 4
    assert called["init"][3] == "45BWZJ1SGC"  # algolia_app_id from config
    assert called["init"][5] == "library_posts"  # algolia_index default from pipeline parser
    assert called["init"][6] == "ycdc_blog_production"  # correct blog index from config
    assert called["run"] == ("extract", "dev", True, False)


def test_main_pipeline_startup_school_workflow_dispatches(monkeypatch):
    called = {}

    class FakeOrchestrator:
        def __init__(
            self,
            metadata_dir,
            content_dir,
            workers,
            algolia_app_id,
            algolia_api_key,
            algolia_index,
            algolia_blog_index,
            algolia_blog_api_key=None,
        ):
            called["init"] = (
                metadata_dir,
                content_dir,
                workers,
                algolia_app_id,
                algolia_api_key,
                algolia_index,
                algolia_blog_index,
            )

        def run_startup_school(self, replay=False, force=False):
            called["workflow"] = (replay, force)

        def run(self, *args, **kwargs):
            called["run_called"] = True

    monkeypatch.setattr(
        sys,
        "argv",
        ["yclib-extract", "pipeline", "--workflow", "startup_school", "--mode", "dev", "--replay"],
    )
    monkeypatch.setattr("yclib_extract.pipeline.PipelineOrchestrator", FakeOrchestrator)

    assert cli.main() == 0
    assert called["workflow"] == (True, True)
    assert "run_called" not in called


def test_main_pipeline_yc_blog_workflow_dispatches(monkeypatch):
    called = {}

    class FakeOrchestrator:
        def __init__(
            self,
            metadata_dir,
            content_dir,
            workers,
            algolia_app_id,
            algolia_api_key,
            algolia_index,
            algolia_blog_index,
            algolia_blog_api_key=None,
        ):
            called["init"] = (
                metadata_dir,
                content_dir,
                workers,
                algolia_app_id,
                algolia_api_key,
                algolia_index,
                algolia_blog_index,
            )

        def run_yc_blog(
            self,
            replay=False,
            force=False,
            include_tags=None,
            exclude_tags=None,
            conditional_tags=None,
            conditional_min_words=300,
        ):
            called["workflow"] = (
                replay,
                force,
                include_tags,
                exclude_tags,
                conditional_tags,
                conditional_min_words,
            )

        def run(self, *args, **kwargs):
            called["run_called"] = True

    monkeypatch.setattr(
        sys,
        "argv",
        ["yclib-extract", "pipeline", "--workflow", "yc_blog", "--mode", "dev", "--replay"],
    )
    monkeypatch.setattr("yclib_extract.pipeline.PipelineOrchestrator", FakeOrchestrator)

    assert cli.main() == 0
    assert called["workflow"][0:2] == (True, True)
    assert "run_called" not in called


def test_main_scrape_blog_writes_taxonomy_and_filtered_posts(monkeypatch, tmp_path):
    calls = {}

    class FakeBlogScraper:
        def __init__(self, app_id=None, api_key=None, index_name="blog_posts"):
            calls["init"] = (app_id, api_key, index_name)
            self.index_name = index_name

        def browse_all(self):
            return [{"objectID": "1", "url": "/blog/test", "title": "Test"}]

        def browse_facets(self):
            return {"tags": {"essay": 1}}

        def save_posts(
            self,
            posts,
            output_dir,
            include_tags=None,
            exclude_tags=None,
            conditional_tags=None,
            conditional_min_words=300,
        ):
            calls["save"] = (
                posts,
                output_dir,
                include_tags,
                exclude_tags,
                conditional_tags,
                conditional_min_words,
            )
            return 1

    monkeypatch.setattr("yclib_extract.cli.YCBlogScraper", FakeBlogScraper)
    monkeypatch.setattr(
        "yclib_extract.cli.build_clean_taxonomy_from_posts", lambda posts: {"tags": {}, "categories": {}, "total_posts": 1}
    )
    out_meta = tmp_path / "yc_blog_metadata.json"
    out_tax = tmp_path / "yc_blog_taxonomy.json"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "yclib-extract",
            "scrape-blog",
            "--output-dir",
            str(out_meta),
            "--taxonomy-output",
            str(out_tax),
        ],
    )

    assert cli.main() == 0
    # Now the CLI uses config defaults
    assert calls["init"][0] == "45BWZJ1SGC"  # algolia_app_id
    assert calls["init"][2] == "ycdc_blog_production"  # index_name (correct blog index)
    assert out_tax.exists()
    assert calls["save"][1] == str(out_meta)
