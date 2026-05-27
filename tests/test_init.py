"""Tests for init command."""

import tempfile
from pathlib import Path
from unittest.mock import patch

from yclib_extract.commands.init import (
    prompt_yes_no,
    prompt_choice,
    run_init,
)


def test_prompt_yes_no_default_true():
    """Test yes/no prompt defaults to True on empty input."""
    with patch("builtins.input", return_value=""):
        result = prompt_yes_no("Test?", default=True)
        assert result is True


def test_prompt_yes_no_default_false():
    """Test yes/no prompt defaults to False on empty input."""
    with patch("builtins.input", return_value=""):
        result = prompt_yes_no("Test?", default=False)
        assert result is False


def test_prompt_yes_no_yes_answer():
    """Test yes/no prompt accepts 'y' or 'yes'."""
    with patch("builtins.input", return_value="yes"):
        result = prompt_yes_no("Test?")
        assert result is True

    with patch("builtins.input", return_value="y"):
        result = prompt_yes_no("Test?")
        assert result is True


def test_prompt_yes_no_no_answer():
    """Test yes/no prompt accepts 'n' or 'no'."""
    with patch("builtins.input", return_value="no"):
        result = prompt_yes_no("Test?")
        assert result is False

    with patch("builtins.input", return_value="n"):
        result = prompt_yes_no("Test?")
        assert result is False


def test_prompt_choice():
    """Test choice prompt accepts valid selection."""
    with patch("builtins.input", return_value="2"):
        result = prompt_choice("Pick one:", ["Apple", "Banana", "Cherry"])
        assert result == "Banana"


def test_prompt_choice_invalid_then_valid():
    """Test choice prompt rejects invalid then accepts valid."""
    with patch("builtins.input", side_effect=["invalid", "1"]):
        result = prompt_choice("Pick one:", ["Apple", "Banana"])
        assert result == "Apple"


def test_run_init_with_hardcoded_defaults():
    """Test init with hardcoded defaults choice."""
    with tempfile.TemporaryDirectory() as tmpdir:
        env_path = Path(tmpdir) / ".env"

        # Mock the user selections: hardcoded defaults, yes for transcripts
        with patch(
            "builtins.input",
            side_effect=[
                "1",  # hardcoded defaults
                "y",  # enable transcripts
                "y",  # confirm config
            ],
        ):
            result = run_init(output_path=str(env_path))

        assert result == 0
        assert env_path.exists()
        content = env_path.read_text()
        assert "ALGOLIA_APP_ID" in content
        assert "ALGOLIA_API_KEY" in content


def test_run_init_with_manual_credentials():
    """Test init with manual DevTools credentials."""
    with tempfile.TemporaryDirectory() as tmpdir:
        env_path = Path(tmpdir) / ".env"

        with patch(
            "builtins.input",
            side_effect=[
                "2",  # manual from DevTools
                "custom-app-id",  # app id
                "custom-api-key",  # api key
                "n",  # no transcripts
                "y",  # confirm config
            ],
        ):
            result = run_init(output_path=str(env_path))

        assert result == 0
        assert env_path.exists()
        content = env_path.read_text()
        assert "ALGOLIA_APP_ID=custom-app-id" in content
        assert "ALGOLIA_API_KEY=custom-api-key" in content


def test_run_init_missing_required_field():
    """Test init rejects empty required field."""
    with tempfile.TemporaryDirectory() as tmpdir:
        env_path = Path(tmpdir) / ".env"

        with patch(
            "builtins.input",
            side_effect=[
                "2",  # manual from DevTools
                "",  # empty app id (invalid)
            ],
        ):
            result = run_init(output_path=str(env_path))

        assert result == 1
        assert not env_path.exists()


def test_run_init_cancel_on_confirmation():
    """Test init cancels if user rejects config."""
    with tempfile.TemporaryDirectory() as tmpdir:
        env_path = Path(tmpdir) / ".env"

        with patch(
            "builtins.input",
            side_effect=[
                "1",  # hardcoded
                "y",  # transcripts
                "n",  # reject config (cancel)
            ],
        ):
            result = run_init(output_path=str(env_path))

        assert result == 1
        assert not env_path.exists()
