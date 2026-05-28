#!/usr/bin/env python3
"""
fetch_altman_essays.py — Fetch Sam Altman's essays from blog.samaltman.com.

This script downloads all essays from Sam Altman's blog (via Atom feed) and
converts them to Markdown files, following the same pattern as PG essays.

Behavior:
- Append-only by default: existing essays are skipped (idempotent)
- Use --force to re-fetch all essays (dev mode)
- Creates altman_essays_audit.json with fetch statistics

Usage:
    python scripts/resources/fetch_altman_essays.py [--force] [--output-dir PATH]

Examples:
    # Append-only mode (default): skip existing essays
    python scripts/resources/fetch_altman_essays.py

    # Force refresh: re-fetch all essays
    python scripts/resources/fetch_altman_essays.py --force

    # Custom output directory
    python scripts/resources/fetch_altman_essays.py --output-dir /custom/path
"""

import os
import sys
from pathlib import Path

# Add project root to sys.path before imports
_project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(_project_root))
sys.path.insert(0, str(_project_root / "src"))

from scripts.shared import ResourceFetcherCLI
from yclib_extract.pipeline import PipelineOrchestrator


class AltmanEssaysFetcher(ResourceFetcherCLI):
    """Fetcher for Sam Altman essays."""

    def __init__(self):
        super().__init__("Sam Altman essays")
        self.orch = None

    def get_default_output_dir_env(self) -> str:
        return "SA_ESSAYS_DIR"

    def setup_parser(self):
        """Override to handle output-dir env var."""
        parser = super().setup_parser()
        # Note: output-dir is handled by PipelineOrchestrator
        return parser

    def run_fetch(self, force: bool = False) -> dict:
        """Fetch Altman essays using PipelineOrchestrator."""
        # Create orchestrator (uses env variables or defaults)
        self.orch = PipelineOrchestrator()
        return self.orch.fetch_sa_essays(force=force)


def main():
    fetcher = AltmanEssaysFetcher()
    return fetcher.main()


if __name__ == "__main__":
    sys.exit(main())
