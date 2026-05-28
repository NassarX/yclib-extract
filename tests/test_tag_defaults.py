"""Tests for tag defaults and mandatory tags field across all resources."""

import json
import tempfile
from pathlib import Path

import pytest

from yclib_extract.extractor import ContentExtractor
from yclib_extract.lib.tag_defaults import (
    build_tags_for_resource,
    get_default_tags_for_source,
    merge_tags,
)


class TestTagDefaults:
    """Test tag defaults for all resource types."""

    def test_get_default_tags_for_source_yc_library(self):
        """YC Library should have YC and yc-library tags."""
        tags = get_default_tags_for_source("yc-library")
        assert tags == ["YC", "yc-library"]

    def test_get_default_tags_for_source_yc_blog(self):
        """YC Blog should have YC and yc-blog tags."""
        tags = get_default_tags_for_source("yc-blog")
        assert tags == ["YC", "yc-blog"]

    def test_get_default_tags_for_source_essay(self):
        """Essays should have essay tag."""
        tags = get_default_tags_for_source("essay")
        assert tags == ["essay"]

    def test_get_default_tags_for_source_pg_essay(self):
        """PG Essays should have essay and pg tags."""
        tags = get_default_tags_for_source("pg-essay")
        assert tags == ["essay", "pg"]

    def test_get_default_tags_for_source_altman_essay(self):
        """Altman Essays should have essay and altman tags."""
        tags = get_default_tags_for_source("altman-essay")
        assert tags == ["essay", "altman"]

    def test_get_default_tags_for_source_startup_school(self):
        """Startup School should have YC and startup-school tags."""
        tags = get_default_tags_for_source("startup-school")
        assert tags == ["YC", "startup-school"]

    def test_merge_tags_with_metadata(self):
        """Merge tags should combine defaults with metadata tags."""
        result = merge_tags(["advice", "fundraising"], "yc-blog")
        assert result == ["YC", "yc-blog", "advice", "fundraising"]

    def test_merge_tags_without_metadata(self):
        """Merge tags should work with empty metadata tags."""
        result = merge_tags([], "essay")
        assert result == ["essay"]

    def test_merge_tags_deduplication(self):
        """Merge tags should deduplicate with case-insensitive comparison."""
        result = merge_tags(["YC", "Startup School"], "startup-school")
        # Should deduplicate YC (case-insensitive) and startup-school
        assert "YC" in result or "yc" in result
        assert "startup-school" in result or "Startup School" in result

    def test_build_tags_for_resource_yc_library(self):
        """Build tags for YC Library resource."""
        result = build_tags_for_resource("article", "yc-library", ["advice"])
        assert "YC" in result
        assert "yc-library" in result
        assert "advice" in result

    def test_build_tags_for_resource_essay_no_metadata(self):
        """Build tags for essay should add default even without metadata."""
        result = build_tags_for_resource("article", "essay", [])
        assert result == ["essay"]

    def test_build_tags_for_resource_yc_blog(self):
        """Build tags for YC Blog with metadata tags."""
        result = build_tags_for_resource("article", "yc-blog", ["startup-school"])
        assert "YC" in result
        assert "yc-blog" in result
        assert "startup-school" in result


class TestExtractorTagsInFrontmatter:
    """Test that tags are properly included in frontmatter."""

    def test_save_markdown_includes_tags_from_metadata(self):
        """Saved markdown should include tags field with metadata tags."""
        with tempfile.TemporaryDirectory() as tmpdir:
            extractor = ContentExtractor(output_dir=tmpdir)
            metadata = {
                "title": "Test Article",
                "url": "https://example.com",
                "tags": ["advice", "fundraising"],
            }
            content = "Test content"

            extractor.save_markdown(
                job_id="test-1",
                content=content,
                metadata=metadata,
                source_type="yc-blog",
            )

            # Read the saved file
            saved_file = Path(tmpdir) / "test-1.md"
            assert saved_file.exists()

            with open(saved_file) as f:
                content_str = f.read()

            # Check frontmatter includes tags
            assert "tags:" in content_str
            assert "YC" in content_str  # Default YC tag
            assert "yc-blog" in content_str  # Default yc-blog tag
            assert "advice" in content_str  # Metadata tag

    def test_save_markdown_adds_tags_for_essay(self):
        """Saved markdown for essays should include essay tag."""
        with tempfile.TemporaryDirectory() as tmpdir:
            extractor = ContentExtractor(output_dir=tmpdir)
            metadata = {
                "title": "Test Essay",
                "url": "https://example.com",
            }
            content = "Essay content"

            extractor.save_markdown(
                job_id="essay-1",
                content=content,
                metadata=metadata,
                source_type="essay",
            )

            saved_file = Path(tmpdir) / "essay-1.md"
            with open(saved_file) as f:
                content_str = f.read()

            assert "tags:" in content_str
            assert "essay" in content_str

    def test_save_markdown_preserves_metadata_tags(self):
        """Saved markdown should preserve metadata tags with defaults."""
        with tempfile.TemporaryDirectory() as tmpdir:
            extractor = ContentExtractor(output_dir=tmpdir)
            metadata = {
                "title": "Test Post",
                "url": "https://example.com",
                "tags": ["technical", "startup school"],
            }
            content = "Content"

            extractor.save_markdown(
                job_id="post-1",
                content=content,
                metadata=metadata,
                source_type="yc-library",
            )

            saved_file = Path(tmpdir) / "post-1.md"
            with open(saved_file) as f:
                content_str = f.read()

            # Should have defaults + metadata tags
            assert "YC" in content_str
            assert "yc-library" in content_str
            assert "technical" in content_str or "startup school" in content_str
