"""Tests for Config module."""

import os
import tempfile
from pathlib import Path

from yclib_extract.config import Config


def test_config_from_explicit_args():
    """Test Config with explicit arguments."""
    config = Config(
        algolia_app_id="test-app",
        algolia_api_key="test-key",
        algolia_index="test-index",
        metadata_dir="/tmp/meta",
        content_dir="/tmp/content",
        min_content_length=1000,
        invidious_instances="invidio.us,yewtu.cafe",
        load_env=False,
    )

    assert config.algolia_app_id == "test-app"
    assert config.algolia_api_key == "test-key"
    assert config.algolia_index == "test-index"
    assert config.metadata_dir == "/tmp/meta"
    assert config.content_dir == "/tmp/content"
    assert config.min_content_length == 1000
    assert config.invidious_instances == ["invidio.us", "yewtu.cafe"]


def test_config_from_defaults():
    """Test Config with all defaults."""
    config = Config(load_env=False)

    assert config.algolia_app_id == "45BWZJ1SGC"
    assert config.algolia_api_key == Config.DEFAULT_ALGOLIA_API_KEY
    assert config.algolia_index == "Library_bookface_production"
    assert config.min_content_length == 700


def test_config_env_override():
    """Test Config respects environment variables."""
    os.environ["ALGOLIA_APP_ID"] = "env-app"
    os.environ["ALGOLIA_API_KEY"] = "env-key"
    os.environ["YCLIB_EXTRACT_MIN_CONTENT_LENGTH"] = "5000"

    try:
        config = Config(load_env=False)
        assert config.algolia_app_id == "env-app"
        assert config.algolia_api_key == "env-key"
        assert config.min_content_length == 5000
    finally:
        del os.environ["ALGOLIA_APP_ID"]
        del os.environ["ALGOLIA_API_KEY"]
        del os.environ["YCLIB_EXTRACT_MIN_CONTENT_LENGTH"]


def test_config_cli_override_env():
    """Test Config CLI args take precedence over env."""
    os.environ["ALGOLIA_APP_ID"] = "env-app"

    try:
        config = Config(algolia_app_id="cli-app", load_env=False)
        assert config.algolia_app_id == "cli-app"
    finally:
        del os.environ["ALGOLIA_APP_ID"]


def test_config_to_dict():
    """Test Config.to_dict() for inspection."""
    config = Config(
        algolia_app_id="test-app",
        algolia_api_key="test-key",
        load_env=False,
    )

    d = config.to_dict()
    assert "algolia_app_id" in d
    assert "algolia_api_key" in d
    assert d["algolia_api_key"] == "***"  # API key masked


def test_config_save_to_env_file():
    """Test Config.save_to_env_file() writes correctly."""
    with tempfile.TemporaryDirectory() as tmpdir:
        env_path = Path(tmpdir) / ".env"
        config = Config(
            algolia_app_id="test-app",
            algolia_api_key="test-key",
            load_env=False,
        )
        config.save_to_env_file(str(env_path))

        content = env_path.read_text()
        assert "ALGOLIA_APP_ID=test-app" in content
        assert "ALGOLIA_API_KEY=test-key" in content


def test_config_from_env():
    """Test Config.from_env() classmethod."""
    os.environ["ALGOLIA_APP_ID"] = "env-app"

    try:
        config = Config.from_env(load_env=False)
        assert config.algolia_app_id == "env-app"
    finally:
        del os.environ["ALGOLIA_APP_ID"]


def test_config_invidious_instances_parsing():
    """Test parsing of comma-separated Invidious instances."""
    config = Config(
        invidious_instances="invidio.us, yewtu.cafe , testing.com",
        load_env=False,
    )

    assert config.invidious_instances == ["invidio.us", "yewtu.cafe", "testing.com"]


def test_config_min_content_length_conversion():
    """Test min_content_length converts to int."""
    config = Config(min_content_length="3000", load_env=False)
    assert config.min_content_length == 3000
    assert isinstance(config.min_content_length, int)


def test_config_min_content_length_invalid_defaults():
    """Test invalid min_content_length defaults to 2000."""
    config = Config(min_content_length="invalid", load_env=False)
    assert config.min_content_length == 700
