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
            self, metadata_dir, content_dir, workers, algolia_app_id, algolia_api_key, algolia_index
        ):
            called["init"] = (
                metadata_dir,
                content_dir,
                workers,
                algolia_app_id,
                algolia_api_key,
                algolia_index,
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
    assert called["init"] == (
        "artifacts/metadata/yc_library_metadata.json",
        "artifacts/yc_library",
        4,
        None,
        None,
        "library_posts",
    )
    assert called["run"] == ("extract", "dev", True, False)


def test_main_pipeline_startup_school_workflow_dispatches(monkeypatch):
    called = {}

    class FakeOrchestrator:
        def __init__(
            self, metadata_dir, content_dir, workers, algolia_app_id, algolia_api_key, algolia_index
        ):
            called["init"] = (
                metadata_dir,
                content_dir,
                workers,
                algolia_app_id,
                algolia_api_key,
                algolia_index,
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
