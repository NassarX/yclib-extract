"""Path utilities for script setup and directory resolution."""

import sys
from pathlib import Path


def get_project_root() -> Path:
    """Get the project root directory (where setup.py or pyproject.toml resides)."""
    current = Path(__file__).parent
    # Go up 3 levels: shared -> scripts -> project_root
    return current.parent.parent


def get_artifacts_dir() -> Path:
    """Get the artifacts directory."""
    return get_project_root() / "artifacts"


def get_metadata_dir() -> Path:
    """Get the metadata directory."""
    return get_artifacts_dir() / "metadata"


def setup_imports() -> None:
    """Add project root to sys.path for imports."""
    root = get_project_root()
    src_path = str(root / "src")
    if src_path not in sys.path:
        sys.path.insert(0, src_path)
