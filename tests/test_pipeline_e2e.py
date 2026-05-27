"""End-to-end integration tests for the full pipeline orchestration."""

from unittest.mock import MagicMock, patch

import pytest

from yclib_extract.pipeline import PipelineOrchestrator


def test_full_pipeline_run(tmp_path):
    """Test a simplified full pipeline run with mocked external calls."""
    # Use temporary files for metadata and content
    metadata_file = tmp_path / "metadata.json"
    content_dir = tmp_path / "content"
    content_dir.mkdir()
    db_path = tmp_path / "pipeline.db"

    orch = PipelineOrchestrator(
        metadata_dir=str(metadata_file), content_dir=str(content_dir), db_path=str(db_path)
    )

    # Mock discovery
    with patch.object(orch, "discover", return_value=5) as mock_discover:
        # Mock extraction
        with patch.object(orch, "extract", return_value=5) as mock_extract:
            # Mock audit
            with patch.object(orch, "write_unified_audit") as mock_audit:
                results = orch.run(start_stage="discover")

                assert results["discovered"] == 5
                assert results["extracted"] == 5
                mock_discover.assert_called_once()
                mock_extract.assert_called_once()
                mock_audit.assert_called_once()


def test_pipeline_resume_logic(tmp_path):
    """Test that pipeline correctly warns about previous failures."""
    db_path = tmp_path / "pipeline.db"
    orch = PipelineOrchestrator(db_path=str(db_path))

    # Simulate a failed run
    run_id = "failed_run_1"
    orch.db.begin_run(run_id, "discover", "weekly", False, "meta", "content")
    orch.db.end_run(run_id, "error")

    with patch.object(orch, "_log") as mock_log:
        with patch.object(orch, "discover", return_value=0):
            with patch.object(orch, "extract", return_value=0):
                orch.run(start_stage="discover")

                # Check for warning in logs
                warning_called = any(
                    "failed" in str(args) for args, kwargs in mock_log.call_args_list
                )
                assert warning_called


def test_stage_ordering(tmp_path):
    """Test that starting from a later stage skips earlier ones."""
    orch = PipelineOrchestrator(db_path=str(tmp_path / "test.db"))

    with patch.object(orch, "discover") as mock_discover:
        with patch.object(orch, "extract") as mock_extract:
            with patch.object(orch, "write_unified_audit") as mock_audit:
                # Start from extract
                orch.run(start_stage="extract")

                mock_discover.assert_not_called()
                mock_extract.assert_called_once()
                mock_audit.assert_called_once()
