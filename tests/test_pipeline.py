import csv
import json
import os
from datetime import datetime
from types import SimpleNamespace
from pathlib import Path

from yclib_extract.pipeline import PipelineOrchestrator


def test_extract_skips_completed_items(monkeypatch, tmp_path):
    called = {}

    class FakeExtractor:
        def __init__(self, output_dir="artifacts/yc_library", min_content_length=2000):
            called["init"] = (output_dir, min_content_length)
            self.db = SimpleNamespace(
                get_job_status=lambda job_id: {"status": "done", "source_type": "Article"}
            )

        def extract_content(self, *args, **kwargs):
            called["extract"] = True

    class FakeScraper:
        def __init__(self, *args, **kwargs):
            pass

    monkeypatch.setattr("yclib_extract.pipeline.ContentExtractor", FakeExtractor)
    monkeypatch.setattr("yclib_extract.pipeline.AlgoliaScraper", FakeScraper)

    artifacts_dir = tmp_path / "artifacts"
    metadata_dir = artifacts_dir / "metadata"
    content_dir = artifacts_dir / "yc_library"
    metadata_dir.mkdir(parents=True)
    content_dir.mkdir()

    metadata_file = metadata_dir / "yc_library_metadata.json"
    metadata_file.write_text(
        json.dumps(
            {
                "posts": [
                    {
                        "id": "post-1",
                        "url": "https://example.com/one",
                        "title": "One",
                        "type": "article",
                    }
                ]
            }
        )
    )

    orchestrator = PipelineOrchestrator(
        metadata_dir=str(metadata_file),
        content_dir=str(content_dir),
        db_path=str(artifacts_dir / "pipeline.db"),
    )
    orchestrator.db.upsert_item("https://example.com/one", status="done", stage="extract")

    assert orchestrator.extract() == 0
    assert "extract" not in called


def test_write_scrape_run_includes_legacy_fields_and_daily_manifest(monkeypatch, tmp_path):
    class FakeExtractor:
        def __init__(self, output_dir="artifacts/yc_library", min_content_length=2000):
            self.db = SimpleNamespace()

    class FakeScraper:
        def __init__(self, *args, **kwargs):
            pass

    monkeypatch.setattr("yclib_extract.pipeline.ContentExtractor", FakeExtractor)
    monkeypatch.setattr("yclib_extract.pipeline.AlgoliaScraper", FakeScraper)
    monkeypatch.setattr("yclib_extract.pipeline.SCRAPE_RUNS_DIR", tmp_path / "scrape_runs")

    class FakeDateTime:
        @staticmethod
        def now():
            return datetime(2026, 5, 24, 19, 2, 28, 673001)

    artifacts_dir = tmp_path / "artifacts"
    metadata_dir = artifacts_dir / "metadata"
    metadata_dir.mkdir(parents=True)
    metadata_file = metadata_dir / "yc_library_metadata.json"
    content_dir = artifacts_dir / "content"
    content_dir.mkdir()

    # Create consolidated metadata file
    metadata_file.write_text(
        json.dumps(
            {
                "posts": [
                    {
                        "id": "post-1",
                        "url": "https://example.com/one",
                        "title": "One",
                        "type": "video",
                    }
                ]
            }
        )
    )

    orchestrator = PipelineOrchestrator(
        metadata_dir=str(metadata_file),
        content_dir=str(content_dir),
        db_path=str(artifacts_dir / "pipeline.db"),
    )
    monkeypatch.setattr("yclib_extract.pipeline.datetime", FakeDateTime)

    orchestrator.db.upsert_item(
        "https://example.com/one",
        title="One",
        source_type="Video",
        metadata_path=str(metadata_file),
        status="done",
        job_id="post-1",
    )
    orchestrator.db.upsert_item(
        "https://example.com/two",
        title="Two",
        source_type="Blog",
        metadata_path=str(metadata_file),
        status="short",
        job_id="post-2",
        media_url="https://example.com/two",
    )

    orchestrator._write_scrape_run("run-1", "extract", 1, 1, force=True, limit=5)
    orchestrator._write_scrape_run("run-2", "audit", 0, 0, force=False, limit=None)
    snapshot_file = next((tmp_path / "scrape_runs").glob("yc_content_runs_20260524.json"))
    snapshot = json.loads(snapshot_file.read_text())
    assert snapshot["date"] == "20260524"
    assert len(snapshot["runs"]) == 2
    first = snapshot["runs"][0]
    assert first["type"] == "extract"
    assert first["state"] == "done"
    assert first["input_dir"] == "yc-library-metadata-json"
    assert first["generated_at"] == "2026-05-24T19:02:28.673001"
    assert first["total_files"] == 1
    assert first["done"] == 1
    assert first["missing"] == 1
    assert first["by_source_type"]["video"] == {"done": 1, "missing": 0}
    assert first["issues"][0]["status"] == "short"
    assert first["workers"] == 4
    assert first["force"] is True
    assert first["limit"] == 5
    assert "items" not in first


def test_write_unified_audit_collects_all_sources(tmp_path, monkeypatch):
    # Set up absolute paths for test
    artifacts_dir = tmp_path / "artifacts"
    metadata_dir = artifacts_dir / "metadata"
    metadata_dir.mkdir(parents=True)

    pg_dir = artifacts_dir / "pg_essays"
    pg_dir.mkdir()
    yc_dir = artifacts_dir / "yc_library"
    yc_dir.mkdir()
    ss_dir = artifacts_dir / "yc_startup_school"
    ss_dir.mkdir()

    # 1. PG Metadata
    (metadata_dir / "pg_essays_metadata.json").write_text(
        json.dumps(
            {
                "posts": [
                    {
                        "id": "pg-1",
                        "url": "https://pg.com/1",
                        "title": "PG 1",
                        "status": "fetched",
                        "local_path": str(pg_dir / "pg-1.md"),
                    }
                ]
            }
        )
    )
    (pg_dir / "pg-1.md").write_text("content")

    # 2. Startup School Metadata
    (metadata_dir / "yc_startup_school_metadata.json").write_text(
        json.dumps(
            {
                "posts": [
                    {
                        "id": "ss-1",
                        "url": "https://ss.org/1",
                        "title": "SS 1",
                        "type": "video",
                        "media_url": "https://youtube.com/v1",
                    }
                ]
            }
        )
    )
    (ss_dir / "ss-1.md").write_text("content")

    # Mock constants in pipeline
    monkeypatch.setattr("yclib_extract.pipeline.ARTIFACTS_DIR", artifacts_dir)
    monkeypatch.setattr("yclib_extract.pipeline.METADATA_DIR", metadata_dir)
    monkeypatch.setattr(
        "yclib_extract.pipeline.DEFAULT_PG_METADATA", metadata_dir / "pg_essays_metadata.json"
    )
    monkeypatch.setattr(
        "yclib_extract.pipeline.DEFAULT_SA_METADATA", metadata_dir / "altman_essays_metadata.json"
    )
    monkeypatch.setattr(
        "yclib_extract.pipeline.DEFAULT_SS_METADATA",
        metadata_dir / "yc_startup_school_metadata.json",
    )
    monkeypatch.setattr("yclib_extract.pipeline.SA_STARTUP_DIR", ss_dir)
    monkeypatch.setattr(
        "yclib_extract.pipeline.UNIFIED_AUDIT_CSV", artifacts_dir / "resources_audit.csv"
    )

    orchestrator = PipelineOrchestrator(
        metadata_dir=str(metadata_dir / "yc_library_metadata.json"),
        content_dir=str(yc_dir),
        db_path=str(artifacts_dir / "extraction_jobs.db"),
    )

    audit_path = orchestrator.write_unified_audit()

    with open(audit_path, newline="") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    assert len(rows) >= 2
    sources = [r["source"] for r in rows]
    assert "PG Essays" in sources
    assert "Startup School" in sources

    ss_row = next(r for r in rows if r["source"] == "Startup School")
    assert ss_row["status"] == "done"
    assert ss_row["source_url"] == "https://youtube.com/v1"
