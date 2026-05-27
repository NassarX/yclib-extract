"""Centralized configuration management for yclib-extract.

Handles environment variables, CLI overrides, and .env file persistence.
Single source of truth for all configuration across the package.
"""

import os
from pathlib import Path
from typing import Dict, Optional


def _load_dotenv(path: str = ".env") -> None:
    """Load .env file if it exists.

    This is a simple implementation that doesn't require python-dotenv.
    """
    env_file = Path(path)
    if not env_file.exists():
        return

    try:
        for line in env_file.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value
    except Exception:
        pass


class Config:
    """Centralized configuration container.

    Priority order for values:
    1. Explicit arguments passed to constructor
    2. Environment variables (from .env or process env)
    3. Sensible defaults
    """

    # Default paths
    ARTIFACTS_DIR = Path("artifacts")
    DEFAULT_METADATA_DIR = str(ARTIFACTS_DIR / "yc_library_metadata.json")
    DEFAULT_CONTENT_DIR = str(ARTIFACTS_DIR / "yc_library")

    # Algolia defaults (public, hardcoded fallback)
    DEFAULT_ALGOLIA_APP_ID = "45BWZJ1SGC"
    DEFAULT_ALGOLIA_API_KEY = "MDlkNDAyNzM1YjA2YTQwYjBkMGIwNjk2Mzg4NDQ3ZGRkMTdhZWJmODM0MDdiNDVhMTNlNDRiYzFlOGZiMGI5MmFuYWx5dGljc1RhZ3M9eWNkYyUyQ2xpYnJhcnkmcmVzdHJpY3RJbmRpY2VzPUxpYnJhcnlfYm9va2ZhY2VfcHJvZHVjdGlvbiZ0YWdGaWx0ZXJzPSU1QiUyMnljZGNfcHVibGljJTIyJTJDJTVCJTIya2Jfcm9vdF8xNzYlMjIlMkMlMjJrYl9yb290XzkxMiUyMiU1RCU1RA=="
    DEFAULT_ALGOLIA_INDEX = "Library_bookface_production"

    # Transcript defaults
    DEFAULT_MIN_CONTENT_LENGTH = 700
    DEFAULT_INVIDIOUS_INSTANCES = "yewtu.cafe,invidio.us"

    def __init__(
        self,
        algolia_app_id: Optional[str] = None,
        algolia_api_key: Optional[str] = None,
        algolia_index: Optional[str] = None,
        metadata_dir: Optional[str] = None,
        content_dir: Optional[str] = None,
        min_content_length: Optional[int] = None,
        invidious_instances: Optional[str] = None,
        load_env: bool = True,
    ):
        """Initialize Config with CLI overrides or environment values.

        Args:
            algolia_app_id: Algolia app ID (overrides env)
            algolia_api_key: Algolia API key (overrides env)
            algolia_index: Algolia index name (overrides env)
            metadata_dir: Directory for post metadata (overrides env)
            content_dir: Directory for extracted content (overrides env)
            min_content_length: Minimum chars for valid extraction (overrides env)
            invidious_instances: Comma-separated Invidious URLs (overrides env)
            load_env: Whether to load .env file from disk (default True)
        """
        if load_env:
            _load_dotenv()

        # Algolia configuration
        self.algolia_app_id = (
            algolia_app_id or os.getenv("ALGOLIA_APP_ID") or self.DEFAULT_ALGOLIA_APP_ID
        )
        self.algolia_api_key = (
            algolia_api_key or os.getenv("ALGOLIA_API_KEY") or self.DEFAULT_ALGOLIA_API_KEY
        )
        self.algolia_index = (
            algolia_index or os.getenv("ALGOLIA_INDEX") or self.DEFAULT_ALGOLIA_INDEX
        )

        # Directory configuration
        self.metadata_dir = metadata_dir or os.getenv("METADATA_DIR") or self.DEFAULT_METADATA_DIR
        self.content_dir = content_dir or os.getenv("CONTENT_DIR") or self.DEFAULT_CONTENT_DIR

        # Content validation
        try:
            self.min_content_length = int(
                min_content_length
                or os.getenv("YCLIB_EXTRACT_MIN_CONTENT_LENGTH")
                or self.DEFAULT_MIN_CONTENT_LENGTH
            )
        except (ValueError, TypeError):
            self.min_content_length = self.DEFAULT_MIN_CONTENT_LENGTH

        # Transcript fallback
        self.invidious_instances = (
            invidious_instances
            or os.getenv("INVIDIOUS_INSTANCES")
            or self.DEFAULT_INVIDIOUS_INSTANCES
        ).split(",")
        self.invidious_instances = [s.strip() for s in self.invidious_instances if s.strip()]

    def to_dict(self) -> Dict[str, any]:
        """Return config as dictionary for inspection/logging."""
        return {
            "algolia_app_id": (
                self.algolia_app_id[:20] + "..."
                if len(self.algolia_app_id) > 20
                else self.algolia_app_id
            ),
            "algolia_api_key": "***" if self.algolia_api_key else None,
            "algolia_index": self.algolia_index,
            "metadata_dir": self.metadata_dir,
            "content_dir": self.content_dir,
            "min_content_length": self.min_content_length,
            "invidious_instances": self.invidious_instances,
        }

    def save_to_env_file(self, path: str = ".env") -> None:
        """Write current config to .env file.

        Args:
            path: Path to .env file (default: .env)
        """
        env_content = f"""# Algolia credentials (public data from YC Library)
ALGOLIA_APP_ID={self.algolia_app_id}
ALGOLIA_API_KEY={self.algolia_api_key}
ALGOLIA_INDEX={self.algolia_index}

# Directory configuration
METADATA_DIR={self.metadata_dir}
CONTENT_DIR={self.content_dir}

# Content validation
YCLIB_EXTRACT_MIN_CONTENT_LENGTH={self.min_content_length}

# Invidious instances for transcript fallback
INVIDIOUS_INSTANCES={','.join(self.invidious_instances)}
"""
        Path(path).write_text(env_content)

    @classmethod
    def from_env(cls, load_env: bool = True) -> "Config":
        """Create Config from environment variables.

        Args:
            load_env: Whether to load .env file first (default True)

        Returns:
            Config instance with all values from environment
        """
        return cls(load_env=load_env)


class YCLibraryConfig:
    """YC Library-specific configuration and extraction tracking."""

    def __init__(self, base_config=None):
        self.base_config = base_config or {}
        self.quality_thresholds = {
            "min_content_length": 100,
            "target_content_length": 500,
            "allow_short_content": False,
        }
        self.extraction_tracking = {
            "track_quality": True,
            "store_metrics": True,
            "quality_db_path": "artifacts/extraction_jobs.db",
        }

    def should_extract(self, metadata: dict, force=False) -> bool:
        """Determine if resource should be extracted.

        Args:
            metadata: Resource metadata
            force: Force extraction even if exists

        Returns:
            True if should extract
        """
        if force:
            return True

        # Check if already extracted
        if metadata.get("extraction_status") == "done":
            return False

        # Check if previously failed
        if metadata.get("extraction_status") in ("error", "failed"):
            # Can retry based on config
            return self.base_config.get("retry_failed", False)

        return True

    def get_quality_config(self) -> dict:
        """Get quality tracking configuration."""
        return {
            "thresholds": self.quality_thresholds,
            "tracking": self.extraction_tracking,
        }
