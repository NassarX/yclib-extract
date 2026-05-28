"""Tests for shared utilities and resource registry."""

import tempfile
from pathlib import Path

import pytest

from scripts.shared import (
    OutputFormatter,
    get_metadata_dir,
    get_project_root,
    get_resource,
    get_resource_by_env_var,
    get_resource_by_metadata_file,
    get_resource_by_name,
    list_all_resources,
    list_resource_names,
    list_resource_slugs,
    load_json,
    save_json,
)


class TestPathUtils:
    """Test path utilities."""

    def test_get_project_root(self):
        """Test getting project root."""
        root = get_project_root()
        assert root.exists()
        assert (root / "src").exists()
        assert (root / "scripts").exists()

    def test_get_metadata_dir(self):
        """Test getting metadata directory."""
        metadata_dir = get_metadata_dir()
        assert metadata_dir.parent.name == "artifacts"


class TestResourceRegistry:
    """Test resource registry and lookup functions."""

    def test_get_resource_by_slug(self):
        """Test getting resource by slug."""
        pg = get_resource("pg-essay")
        assert pg is not None
        assert pg.name == "Paul Graham Essays"
        assert pg.slug == "pg-essay"

    def test_get_resource_invalid_slug(self):
        """Test getting resource with invalid slug."""
        result = get_resource("invalid-slug")
        assert result is None

    def test_get_resource_by_name(self):
        """Test getting resource by name."""
        yc_lib = get_resource_by_name("YC Library")
        assert yc_lib is not None
        assert yc_lib.slug == "yc-library"

    def test_get_resource_by_name_case_insensitive(self):
        """Test resource name lookup is case-insensitive."""
        result = get_resource_by_name("paul graham essays")
        assert result is not None
        assert result.slug == "pg-essay"

    def test_get_resource_by_env_var(self):
        """Test getting resource by environment variable."""
        pg = get_resource_by_env_var("PG_ESSAYS_DIR")
        assert pg is not None
        assert pg.slug == "pg-essay"

    def test_get_resource_by_metadata_file(self):
        """Test getting resource by metadata filename."""
        altman = get_resource_by_metadata_file("altman_essays_metadata.json")
        assert altman is not None
        assert altman.name == "Sam Altman Essays"

    def test_list_all_resources(self):
        """Test listing all resources."""
        resources = list_all_resources()
        assert len(resources) == 5
        slugs = {r.slug for r in resources}
        assert "pg-essay" in slugs
        assert "yc-library" in slugs
        assert "yc-blog" in slugs
        assert "altman-essay" in slugs
        assert "startup-school" in slugs

    def test_list_resource_slugs(self):
        """Test listing resource slugs."""
        slugs = list_resource_slugs()
        assert len(slugs) == 5
        assert "pg-essay" in slugs
        assert "yc-library" in slugs

    def test_list_resource_names(self):
        """Test listing resource names."""
        names = list_resource_names()
        assert len(names) == 5
        assert "Paul Graham Essays" in names
        assert "YC Library" in names

    def test_resource_output_path(self):
        """Test getting resource output path."""
        pg = get_resource("pg-essay")
        output_path = pg.get_output_path()
        assert output_path.name == "pg_essays"
        assert output_path.parent.name == "artifacts"

    def test_resource_metadata_path(self):
        """Test getting resource metadata path."""
        pg = get_resource("pg-essay")
        metadata_path = pg.get_metadata_path()
        assert metadata_path.name == "pg_essays_metadata.json"
        assert metadata_path.parent.name == "metadata"

    def test_resource_default_tags(self):
        """Test resource default tags."""
        yc_lib = get_resource("yc-library")
        assert "YC" in yc_lib.default_tags
        assert "yc-library" in yc_lib.default_tags

        pg = get_resource("pg-essay")
        assert "essay" in pg.default_tags
        assert "pg" in pg.default_tags

    def test_resource_orchestrator_method(self):
        """Test getting orchestrator method name."""
        pg = get_resource("pg-essay")
        assert pg.get_orchestrator_method_name() == "fetch_pg_essays"

        altman = get_resource("altman-essay")
        assert altman.get_orchestrator_method_name() == "fetch_sa_essays"


class TestOutputFormatter:
    """Test output formatting utilities."""

    def test_formatter_methods_exist(self):
        """Test that formatter has all required methods."""
        formatter = OutputFormatter()
        assert hasattr(formatter, "header")
        assert hasattr(formatter, "success")
        assert hasattr(formatter, "error")
        assert hasattr(formatter, "warning")
        assert hasattr(formatter, "info")
        assert hasattr(formatter, "done")
        assert hasattr(formatter, "stats")

    def test_formatter_is_callable(self):
        """Test that formatter methods are callable."""
        formatter = OutputFormatter()
        # Just verify they don't raise exceptions
        formatter.header("Test")
        formatter.success("Test")
        formatter.error("Test")
        formatter.warning("Test")
        formatter.info("Test")
        formatter.stats("Test", {"key": "value"})
        formatter.done()


class TestMetadataUtils:
    """Test metadata file utilities."""

    def test_save_and_load_json(self):
        """Test saving and loading JSON."""
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = Path(tmpdir) / "test.json"
            data = {"key": "value", "nested": {"a": 1}}

            save_json(filepath, data)
            loaded = load_json(filepath)

            assert loaded == data

    def test_save_json_formats_nicely(self):
        """Test that saved JSON is formatted with indentation."""
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = Path(tmpdir) / "test.json"
            data = {"key": "value"}

            save_json(filepath, data, indent=2)
            content = filepath.read_text()

            assert "\n" in content  # Should have newlines for formatting
            assert '  "key"' in content  # Should have indentation
